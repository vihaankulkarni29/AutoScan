#!/usr/bin/env python
"""
AutoScan Phase 1.4 Final: pH-Corrected Control Benchmark

Fixes multi-ligand clash by selecting a single ligand instance and
standardizes docking box size to 20.0 A buffer for all targets.

Data Source: Local benchmark_data PDB files
Protocol: Baseline (crystal) vs. Stress (randomized ±1.0 A) docking
"""

import os
import sys
import csv
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import numpy as np
from Bio.PDB import PDBParser, PDBIO, Select
from scipy.spatial.transform import Rotation as R

# Import autoscan modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from autoscan.docking.vina import VinaEngine

# ============================================================================
# Configuration
# ============================================================================

CONTROLS = {
    "1HVR": "XK2",  # PASS
    "1STP": "BTN",  # PASS
    "3PTB": "BEN",  # PASS
    "1AID": "THK",  # PASS
    "2J7E": "GI2",  # FIX: Will now select only 1 instance
    "1TNH": "FBA",  # OPTIMIZE: Larger box might help
    "1OYT": "G39"   # Neuraminidase
}

BENCHMARK_DATA_DIR = Path(__file__).parent / "benchmark_data"
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
WORK_DIR = Path(__file__).parent.parent / "workspace" / "control_test_final" / RUN_TIMESTAMP
WORK_DIR.mkdir(parents=True, exist_ok=True)  # Create before logging setup
RESULTS_CSV = WORK_DIR / "benchmark_control_final_results.csv"
LOG_FILE = WORK_DIR / "calibration_control_final.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(name)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Helper Functions
# ============================================================================

class SingleLigandSelector(Select):
    """Select a single ligand residue by chain id and residue id."""
    def __init__(self, chain_id, residue_id):
        self.chain_id = chain_id
        self.residue_id = residue_id

    def accept_residue(self, residue):
        chain_id = residue.get_parent().id
        return chain_id == self.chain_id and residue.id == self.residue_id


class ReceptorSelector(Select):
    """Select all atoms except ligand residue name and water/ions."""
    def __init__(self, lig_resname):
        self.lig_resname = lig_resname.strip()

    def accept_residue(self, residue):
        resname = residue.get_resname().strip()
        if resname == self.lig_resname:
            return False
        if resname in ["HOH", "WAT", "CL", "NA", "MG", "CA", "ZN"]:
            return False
        return True


def find_first_ligand_residue(structure, lig_resname):
    """Find the first matching ligand residue and return (chain_id, residue_id)."""
    lig_resname = lig_resname.strip()
    for model in structure:
        for chain in model:
            for residue in chain:
                if residue.get_resname().strip() == lig_resname:
                    return chain.id, residue.id
    return None


def smart_randomize(input_pdbqt: Path, output_pdbqt: Path, trans: float = 1.0) -> bool:
    """
    Conservative randomization: random rotation + ±trans translation.
    Keeps ligand close to original pocket.
    """
    try:
        with open(input_pdbqt, "r") as f:
            lines = f.readlines()

        coords = []
        indices = []
        for i, line in enumerate(lines):
            if line.startswith(("ATOM", "HETATM")):
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    coords.append([x, y, z])
                    indices.append(i)
                except ValueError:
                    continue

        if not coords:
            logger.warning(f"No coordinates found in {input_pdbqt}")
            return False

        coords = np.array(coords)
        centroid = np.mean(coords, axis=0)

        # Center, rotate, translate
        coords -= centroid
        rotation_matrix = R.random().as_matrix()
        coords = np.dot(coords, rotation_matrix)
        translation = np.random.uniform(-trans, trans, size=3)
        coords += centroid + translation

        # Write modified PDBQT
        with open(output_pdbqt, "w") as f:
            for i, line in enumerate(lines):
                if i in indices:
                    coord_idx = indices.index(i)
                    x, y, z = coords[coord_idx]
                    new_line = (
                        line[:30]
                        + f"{x:8.3f}{y:8.3f}{z:8.3f}"
                        + line[54:]
                    )
                    f.write(new_line)
                else:
                    f.write(line)

        return True
    except Exception as e:
        logger.warning(f"Error randomizing pose: {e}")
        return False


def pdb_to_pdbqt_with_ph(pdb_file: Path, pdbqt_file: Path, ph: float = 7.4) -> bool:
    """Convert PDB to PDBQT with pH correction using obabel."""
    try:
        cmd = [
            "obabel",
            str(pdb_file),
            f"-O{pdbqt_file}",
            "-xr",
            "-h",
            f"-p{ph}",
            "--partialcharge",
            "gasteiger",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0 and pdbqt_file.exists():
            logger.info(f"Converted {pdb_file.name} → {pdbqt_file.name} (pH {ph})")
            return True

        logger.warning(f"obabel conversion failed: {result.stderr[:200]}")
        return False
    except subprocess.TimeoutExpired:
        logger.warning(f"obabel timeout for {pdb_file}")
        return False
    except Exception as e:
        logger.warning(f"Error converting to PDBQT: {e}")
        return False


def parse_pdbqt_coords(pdbqt_file: Path) -> Optional[np.ndarray]:
    """Extract heavy atom coordinates from PDBQT file."""
    try:
        coords = []
        with open(pdbqt_file, "r") as f:
            for line in f:
                if line.startswith(("ATOM", "HETATM")):
                    atom_type = line[77:79].strip()
                    if atom_type != "H":
                        try:
                            x = float(line[30:38])
                            y = float(line[38:46])
                            z = float(line[46:54])
                            coords.append([x, y, z])
                        except ValueError:
                            continue
        return np.array(coords) if coords else None
    except Exception as e:
        logger.warning(f"Error parsing PDBQT: {e}")
        return None


def strip_pdbqt_receptor(pdbqt_path: Path) -> None:
    """Remove BRANCH/ROOT tags and keep only ATOM/HETATM records."""
    lines = pdbqt_path.read_text(encoding="utf-8").splitlines()
    cleaned = []
    for line in lines:
        if line.startswith("REMARK") or line.startswith(("ATOM", "HETATM")):
            cleaned.append(line)
    pdbqt_path.write_text("\n".join(cleaned) + "\n", encoding="utf-8")


def ensure_pdbqt_ligand(pdbqt_path: Path) -> None:
    """Wrap ligand PDBQT with ROOT/ENDROOT tags."""
    lines = pdbqt_path.read_text(encoding="utf-8").splitlines()
    if any(line.startswith("ROOT") for line in lines):
        return

    remarks = [line for line in lines if line.startswith("REMARK")]
    atoms = [line for line in lines if line.startswith(("ATOM", "HETATM"))]
    if not atoms:
        return

    wrapped = []
    wrapped.extend(remarks)
    wrapped.append("ROOT")
    wrapped.extend(atoms)
    wrapped.append("ENDROOT")
    wrapped.append("TORSDOF 0")
    pdbqt_path.write_text("\n".join(wrapped) + "\n", encoding="utf-8")


def run_vina_docking(
    receptor_pdbqt: Path,
    ligand_pdbqt: Path,
    output_pdbqt: Path,
    buffer_angstroms: float = 20.0,
) -> Tuple[Optional[float], str]:
    """Run Vina docking with crash guard."""
    try:
        ligand_coords = parse_pdbqt_coords(ligand_pdbqt)
        if ligand_coords is None or len(ligand_coords) == 0:
            return None, "No ligand coordinates"

        ligand_center = ligand_coords.mean(axis=0)
        ligand_extent = ligand_coords.max(axis=0) - ligand_coords.min(axis=0)
        box_size = ligand_extent + buffer_angstroms

        logger.info(f"  Box: center={ligand_center}, size={box_size}")

        engine = VinaEngine(
            receptor_pdbqt=str(receptor_pdbqt),
            ligand_pdbqt=str(ligand_pdbqt),
            vina_executable="tools/vina.exe",
        )

        score = engine.run(
            center=ligand_center.tolist(),
            buffer_angstroms=buffer_angstroms,
            cpu=4,
            num_modes=9,
            output_pdbqt=str(output_pdbqt),
        )

        if score is None or score > 100 or score < -200:
            logger.warning(f"Energy explosion: {score}")
            return 999.9, "EXPLOSION"

        return score, "OK"
    except Exception as e:
        logger.error(f"Vina crash: {e}")
        return 999.9, "EXCEPTION"


# ============================================================================
# Main Execution
# ============================================================================

def main():
    logger.info("=" * 80)
    logger.info("AutoScan Phase 1.4 Final: pH-Corrected Control Benchmark")
    logger.info(f"Workspace: {WORK_DIR}")
    logger.info("=" * 80)

    results = []
    parser = PDBParser(QUIET=True)
    io = PDBIO()

    print("\n" + "=" * 100)
    print(f"{'Target':<12} {'Ligand':<8} {'Baseline':<12} {'Random':<12} {'Status':<15}")
    print("=" * 100)

    for pdb_id, ligand_code in CONTROLS.items():
        logger.info(f"\nProcessing {pdb_id} ({ligand_code})")

        target_dir = WORK_DIR / pdb_id
        target_dir.mkdir(exist_ok=True)

        pdb_file = BENCHMARK_DATA_DIR / f"{pdb_id}.pdb"
        if not pdb_file.exists():
            logger.warning(f"SKIP: {pdb_id} - PDB file not found")
            print(f"{pdb_id:<12} {ligand_code:<8} {'SKIP':<12} {'SKIP':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Baseline_Score": "SKIP",
                "Random_Score": "SKIP",
                "Status": "ERROR",
            })
            continue

        try:
            structure = parser.get_structure(pdb_id, str(pdb_file))
            selection = find_first_ligand_residue(structure, ligand_code)
            if selection is None:
                logger.warning(f"SKIP: {pdb_id} - Ligand {ligand_code} not found in PDB")
                print(f"{pdb_id:<12} {ligand_code:<8} {'SKIP':<12} {'SKIP':<12} {'ERROR':<15}")
                results.append({
                    "PDB_ID": pdb_id,
                    "Ligand": ligand_code,
                    "Baseline_Score": "SKIP",
                    "Random_Score": "SKIP",
                    "Status": "ERROR_LIGAND_NOT_FOUND",
                })
                continue
        except Exception as e:
            logger.error(f"Error checking ligand: {e}")
            continue

        chain_id, residue_id = selection
        logger.info(f"Selected ligand instance: chain={chain_id} residue={residue_id}")

        ligand_pdb = target_dir / "ligand.pdb"
        receptor_pdb = target_dir / "receptor.pdb"

        try:
            io.set_structure(structure)
            io.save(str(ligand_pdb), SingleLigandSelector(chain_id, residue_id))
            io.save(str(receptor_pdb), ReceptorSelector(ligand_code))
        except Exception as e:
            logger.error(f"Failed to extract ligand/receptor: {e}")
            print(f"{pdb_id:<12} {ligand_code:<8} {'ERROR':<12} {'ERROR':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Baseline_Score": "ERROR",
                "Random_Score": "ERROR",
                "Status": "ERROR",
            })
            continue

        logger.info("Converting PDB → PDBQT (pH 7.4 correction)")
        ligand_pdbqt = target_dir / "ligand_native.pdbqt"
        ligand_rand_pdbqt = target_dir / "ligand_rand.pdbqt"
        receptor_pdbqt = target_dir / "receptor.pdbqt"

        if not pdb_to_pdbqt_with_ph(ligand_pdb, ligand_pdbqt, ph=7.4):
            logger.error("Failed to convert ligand to PDBQT")
            print(f"{pdb_id:<12} {ligand_code:<8} {'ERROR':<12} {'ERROR':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Baseline_Score": "ERROR",
                "Random_Score": "ERROR",
                "Status": "ERROR",
            })
            continue

        if not pdb_to_pdbqt_with_ph(receptor_pdb, receptor_pdbqt, ph=7.4):
            logger.error("Failed to convert receptor to PDBQT")
            print(f"{pdb_id:<12} {ligand_code:<8} {'ERROR':<12} {'ERROR':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Baseline_Score": "ERROR",
                "Random_Score": "ERROR",
                "Status": "ERROR",
            })
            continue

        ensure_pdbqt_ligand(ligand_pdbqt)
        strip_pdbqt_receptor(receptor_pdbqt)

        if not smart_randomize(ligand_pdbqt, ligand_rand_pdbqt, trans=1.0):
            logger.error("Failed to randomize ligand pose")
            print(f"{pdb_id:<12} {ligand_code:<8} {'ERROR':<12} {'ERROR':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Baseline_Score": "ERROR",
                "Random_Score": "ERROR",
                "Status": "ERROR",
            })
            continue

        ensure_pdbqt_ligand(ligand_rand_pdbqt)

        logger.info("TEST A: Baseline Docking (Crystal Pose)")
        baseline_output = target_dir / "output_baseline.pdbqt"
        baseline_score, baseline_err = run_vina_docking(
            receptor_pdbqt, ligand_pdbqt, baseline_output, buffer_angstroms=20.0
        )

        if baseline_score is None:
            logger.error(f"Baseline docking failed: {baseline_err}")
            baseline_score = 999.9
        else:
            logger.info(f"Baseline affinity: {baseline_score:.3f} kcal/mol")

        logger.info("TEST B: Stress Docking (Randomized Pose)")
        random_output = target_dir / "output_random.pdbqt"
        random_score, random_err = run_vina_docking(
            receptor_pdbqt, ligand_rand_pdbqt, random_output, buffer_angstroms=20.0
        )

        if random_score is None:
            logger.error(f"Stress docking failed: {random_err}")
            random_score = 999.9
        else:
            logger.info(f"Random affinity: {random_score:.3f} kcal/mol")

        if baseline_score == 999.9 or random_score == 999.9:
            status = "CLASH"
        elif random_score < -6.0 and baseline_score < -6.0:
            status = "PASS"
        else:
            status = "FAIL"

        logger.info(f"Result: {status}")

        results.append({
            "PDB_ID": pdb_id,
            "Ligand": ligand_code,
            "Baseline_Score": f"{baseline_score:.3f}" if baseline_score != 999.9 else "999.9",
            "Random_Score": f"{random_score:.3f}" if random_score != 999.9 else "999.9",
            "Status": status,
        })

        baseline_str = f"{baseline_score:.3f}" if baseline_score != 999.9 else "999.9"
        random_str = f"{random_score:.3f}" if random_score != 999.9 else "999.9"
        print(f"{pdb_id:<12} {ligand_code:<8} {baseline_str:<12} {random_str:<12} {status:<15}")

    print("=" * 100 + "\n")

    if results:
        with open(RESULTS_CSV, "w", newline="") as csvfile:
            fieldnames = ["PDB_ID", "Ligand", "Baseline_Score", "Random_Score", "Status"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        logger.info(f"Results saved to {RESULTS_CSV}")

    passed = sum(1 for r in results if r["Status"] == "PASS")
    clash = sum(1 for r in results if r["Status"] == "CLASH")
    failed = sum(1 for r in results if r["Status"] == "FAIL")
    error = sum(1 for r in results if r["Status"] in ["ERROR", "ERROR_LIGAND_NOT_FOUND"])

    logger.info(f"\n{'='*60}")
    logger.info("Summary Statistics")
    logger.info(f"{'='*60}")
    logger.info(f"Total Targets: {len(results)}")
    logger.info(f"PASS:  {passed}")
    logger.info(f"CLASH: {clash}")
    logger.info(f"FAIL:  {failed}")
    logger.info(f"ERROR: {error}")
    if len(results) > 0:
        logger.info(f"Success Rate: {(passed / len(results) * 100):.1f}%")
    logger.info(f"{'='*60}\n")

    print("\nSummary Statistics:")
    print(f"  Total Targets: {len(results)}")
    print(f"  PASS:  {passed}")
    print(f"  CLASH: {clash}")
    print(f"  FAIL:  {failed}")
    print(f"  ERROR: {error}")
    if len(results) > 0:
        print(f"  Success Rate: {(passed / len(results) * 100):.1f}%\n")


if __name__ == "__main__":
    main()
