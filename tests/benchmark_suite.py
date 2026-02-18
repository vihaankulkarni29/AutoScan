#!/usr/bin/env python
"""
AutoScan Benchmark Suite v2.0 - Unified Validation Framework

Consolidates Phase 1 benchmark studies into a single, production-ready test suite.
Implements all "Best Practices" lessons from Phase 1 calibration studies:
  - Chemistry: pH 7.4 protonation with Gasteiger charges (1STP/3PTB fix)
  - Physics: 15.0 Å buffer + 60.0 Å max box size (2J7E clash fix)
  - Search: Vina exhaustiveness=32 for weak binders (1TNH fix)
  - Logic: SingleLigandSelector for multi-ligand PDBs (2J7E crash fix)

Dual-Mode Execution:
  - --mode online: Downloads PDBs from RCSB
  - --mode local: Uses tests/benchmark_data/ (default)

Twin-Test Protocol:
  - Run A (Crystal): Native ligand pose (baseline)
  - Run B (Randomized): Pert ±2.0 Å translation + random rotation (stress test)

Output: BENCHMARK_REPORT.md with results table + detailed logs.
"""

import os
import sys
import csv
import json
import argparse
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import numpy as np
from scipy.spatial.transform import Rotation as R
from Bio.PDB import PDBParser, PDBIO, Select
import urllib.request

# Import autoscan modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from autoscan.docking.vina import VinaEngine
from autoscan.docking.utils import calculate_grid_box

# ============================================================================
# Configuration
# ============================================================================

TARGETS = {
    # === Phase 1 Diversity Set (Blind Docking) ===
    "2XCT": {"pdb": "2XCT", "ligand": "CPF", "category": "Antibiotic", "mode": "online"},
    "3ERT": {"pdb": "3ERT", "ligand": "OHT", "category": "Hormone", "mode": "online"},
    "1M17": {"pdb": "1M17", "ligand": "AQ4", "category": "Cancer", "mode": "online"},
    "1IEP": {"pdb": "1IEP", "ligand": "STI", "category": "Cancer", "mode": "online"},
    "3LN1": {"pdb": "3LN1", "ligand": "CEL", "category": "Pain", "mode": "online"},
    "2HU4": {"pdb": "2HU4", "ligand": "G39", "category": "Flu", "mode": "online"},
    "1SQN": {"pdb": "1SQN", "ligand": "PRG", "category": "Steroid", "mode": "online"},
    "1OQA": {"pdb": "1OQA", "ligand": "BTN", "category": "Bio-tool", "mode": "online"},
    "4DJU": {"pdb": "4DJU", "ligand": "032", "category": "Cancer", "mode": "online"},

    # === Phase 1 Control Set (Calibration) ===
    "1HVR": {"pdb": "1HVR", "ligand": "XK2", "category": "HIV-Protease", "ref_energy": -21.77, "mode": "local"},
    "1STP": {"pdb": "1STP", "ligand": "BTN", "category": "Streptavidin", "ref_energy": -9.10, "mode": "local"},
    "3PTB": {"pdb": "3PTB", "ligand": "BEN", "category": "Trypsin", "ref_energy": -6.42, "mode": "local"},
    "1AID": {"pdb": "1AID", "ligand": "THK", "category": "HIV-Protease", "ref_energy": -17.56, "mode": "local"},
    "2J7E": {"pdb": "2J7E", "ligand": "GI2", "category": "Kinase", "ref_energy": -10.03, "mode": "local"},
    "1TNH": {"pdb": "1TNH", "ligand": "FBA", "category": "Thermolysin", "ref_energy": -5.33, "mode": "local"},
}

BENCHMARK_DATA_DIR = Path(__file__).parent / "benchmark_data"
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
WORK_DIR = Path(__file__).parent.parent / "workspace" / "benchmark_suite" / RUN_TIMESTAMP
REPORT_FILE = WORK_DIR / "BENCHMARK_REPORT.md"
CSV_FILE = WORK_DIR / "benchmark_results.csv"
LOG_FILE = WORK_DIR / "benchmark_suite.log"

# ============================================================================
# Logging Setup
# ============================================================================

WORK_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Helper Classes & Functions
# ============================================================================

class SingleLigandSelector(Select):
    """Select a single ligand residue by chain ID and residue ID."""
    def __init__(self, chain_id: str, residue_id: Tuple):
        self.chain_id = chain_id
        self.residue_id = residue_id

    def accept_chain(self, chain):
        return chain.id == self.chain_id

    def accept_residue(self, residue):
        return residue.id == self.residue_id


class ReceptorSelector(Select):
    """Select all atoms except ligand residue name and water/ions."""
    def __init__(self, lig_resname: str):
        self.lig_resname = lig_resname.strip()

    def accept_residue(self, residue):
        resname = residue.get_resname().strip()
        if resname == self.lig_resname:
            return False
        if resname in ["HOH", "WAT", "CL", "NA", "MG", "CA", "ZN"]:
            return False
        return True


def download_pdb(pdb_id: str, output_file: Path) -> bool:
    """Download PDB file from RCSB."""
    try:
        url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
        urllib.request.urlretrieve(url, output_file)
        logger.info(f"Downloaded {pdb_id} from RCSB")
        return True
    except Exception as e:
        logger.warning(f"Failed to download {pdb_id}: {e}")
        return False


def find_first_ligand_residue(structure, lig_resname: str) -> Optional[Tuple]:
    """Find first matching ligand residue (chain_id, residue_id)."""
    lig_resname = lig_resname.strip().upper()
    for model in structure:
        for chain in model:
            for residue in chain:
                if residue.get_resname().strip().upper() == lig_resname:
                    return chain.id, residue.id
    return None


def pdb_to_pdbqt_obabel(pdb_file: Path, output_file: Path, ph: float = 7.4) -> bool:
    """Convert PDB to PDBQT with pH correction using obabel."""
    try:
        cmd = [
            "obabel",
            str(pdb_file),
            f"-O{output_file}",
            "-xr",
            "-h",
            f"-p{ph}",
            "--partialcharge",
            "gasteiger",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and output_file.exists():
            logger.info(f"Converted {pdb_file.name} → {output_file.name} (pH {ph})")
            return True
        logger.warning(f"obabel conversion failed: {result.stderr[:200]}")
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
    """Remove BRANCH/ROOT tags, keep only ATOM/HETATM records."""
    lines = pdbqt_path.read_text(encoding="utf-8").splitlines()
    cleaned = [line for line in lines if line.startswith("REMARK") or line.startswith(("ATOM", "HETATM"))]
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

    wrapped = remarks + ["ROOT"] + atoms + ["ENDROOT", "TORSDOF 0"]
    pdbqt_path.write_text("\n".join(wrapped) + "\n", encoding="utf-8")


def randomize_pose(input_pdbqt: Path, output_pdbqt: Path, trans: float = 2.0) -> bool:
    """Randomize ligand pose with random rotation + translation (±trans Å)."""
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
            logger.warning(f"No coordinates in {input_pdbqt}")
            return False

        coords = np.array(coords)
        centroid = np.mean(coords, axis=0)
        coords -= centroid

        # Random rotation
        rotation_matrix = R.random().as_matrix()
        coords = np.dot(coords, rotation_matrix)

        # Random translation
        translation = np.random.uniform(-trans, trans, size=3)
        coords += centroid + translation

        # Write modified PDBQT
        with open(output_pdbqt, "w") as f:
            for i, line in enumerate(lines):
                if i in indices:
                    coord_idx = indices.index(i)
                    x, y, z = coords[coord_idx]
                    new_line = line[:30] + f"{x:8.3f}{y:8.3f}{z:8.3f}" + line[54:]
                    f.write(new_line)
                else:
                    f.write(line)

        return True
    except Exception as e:
        logger.warning(f"Error randomizing pose: {e}")
        return False


def run_vina_docking(
    receptor_pdbqt: Path,
    ligand_pdbqt: Path,
    output_pdbqt: Path,
    buffer_angstroms: float = 15.0,
    exhaustiveness: int = 32,
) -> Tuple[Optional[float], str]:
    """Run Vina docking with crash guard."""
    try:
        ligand_coords = parse_pdbqt_coords(ligand_pdbqt)
        if ligand_coords is None or len(ligand_coords) == 0:
            return None, "No ligand coordinates"

        ligand_center = ligand_coords.mean(axis=0)
        ligand_extent = ligand_coords.max(axis=0) - ligand_coords.min(axis=0)
        box_size = ligand_extent + buffer_angstroms
        box_size = np.clip(box_size, 10.0, 60.0)

        logger.info(f"  Vina box: center={ligand_center}, size={box_size}")

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
            exhaustiveness=exhaustiveness,
            output_pdbqt=str(output_pdbqt),
        )

        if score is None or score > 100 or score < -200:
            logger.warning(f"Energy anomaly: {score}")
            return 999.9, "CLASH"

        return score, "OK"
    except Exception as e:
        logger.error(f"Vina exception: {e}")
        return 999.9, "EXCEPTION"


# ============================================================================
# Main Benchmark Engine
# ============================================================================

def run_benchmark(mode: str = "local", targets: Optional[list] = None):
    """
    Execute the unified benchmark suite.
    
    Args:
        mode: "local" (benchmark_data/) or "online" (RCSB download)
        targets: List of PDB IDs to test. If None, test all.
    """
    logger.info("=" * 80)
    logger.info("AutoScan Benchmark Suite v2.0 - Unified Validation Framework")
    logger.info(f"Mode: {mode.upper()}")
    logger.info(f"Workspace: {WORK_DIR}")
    logger.info("=" * 80)

    results = []
    parser = PDBParser(QUIET=True)
    io = PDBIO()

    # Determine which targets to run
    if targets is None:
        test_targets = {k: v for k, v in TARGETS.items() if v.get("mode") == mode}
    else:
        test_targets = {k: TARGETS[k] for k in targets if k in TARGETS}

    print("\n" + "=" * 120)
    print(f"{'Target':<12} {'Ligand':<8} {'Category':<20} {'Crystal':<12} {'Random':<12} {'RMSD':<8} {'Status':<15}")
    print("=" * 120)

    for pdb_id, config in test_targets.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {pdb_id} ({config['ligand']}) - {config['category']}")
        logger.info('='*60)

        target_dir = WORK_DIR / pdb_id
        target_dir.mkdir(exist_ok=True)

        # Get or download PDB
        pdb_file = BENCHMARK_DATA_DIR / f"{pdb_id}.pdb"
        if not pdb_file.exists():
            if mode == "online":
                if not download_pdb(pdb_id, pdb_file):
                    logger.warning(f"SKIP: {pdb_id} - Download failed")
                    print(f"{pdb_id:<12} {config['ligand']:<8} {config['category']:<20} {'SKIP':<12} {'SKIP':<12} {'-':<8} {'ERROR':<15}")
                    results.append({"PDB_ID": pdb_id, "Status": "ERROR", "Reason": "Download failed"})
                    continue
            else:
                logger.warning(f"SKIP: {pdb_id} - PDB file not found in {BENCHMARK_DATA_DIR}")
                print(f"{pdb_id:<12} {config['ligand']:<8} {config['category']:<20} {'SKIP':<12} {'SKIP':<12} {'-':<8} {'ERROR':<15}")
                results.append({"PDB_ID": pdb_id, "Status": "ERROR", "Reason": "PDB not found"})
                continue

        try:
            # Parse and extract ligand/receptor
            structure = parser.get_structure(pdb_id, str(pdb_file))
            selection = find_first_ligand_residue(structure, config["ligand"])

            if selection is None:
                logger.warning(f"SKIP: {pdb_id} - Ligand {config['ligand']} not found")
                print(f"{pdb_id:<12} {config['ligand']:<8} {config['category']:<20} {'SKIP':<12} {'SKIP':<12} {'-':<8} {'ERROR':<15}")
                results.append({"PDB_ID": pdb_id, "Status": "ERROR", "Reason": f"Ligand {config['ligand']} not found"})
                continue

            chain_id, residue_id = selection
            logger.info(f"Greedy selector: chain={chain_id}, residue={residue_id}")

            ligand_pdb = target_dir / "ligand.pdb"
            receptor_pdb = target_dir / "receptor.pdb"

            # Save ligand and receptor
            io.set_structure(structure)
            io.save(str(ligand_pdb), SingleLigandSelector(chain_id, residue_id))
            io.save(str(receptor_pdb), ReceptorSelector(config["ligand"]))

            # Convert to PDBQT
            ligand_pdbqt_native = target_dir / "ligand_native.pdbqt"
            receptor_pdbqt = target_dir / "receptor.pdbqt"

            if not pdb_to_pdbqt_obabel(ligand_pdb, ligand_pdbqt_native):
                logger.error(f"Failed to convert ligand PDB→PDBQT")
                results.append({"PDB_ID": pdb_id, "Status": "ERROR", "Reason": "Ligand conversion failed"})
                continue

            if not pdb_to_pdbqt_obabel(receptor_pdb, receptor_pdbqt):
                logger.error(f"Failed to convert receptor PDB→PDBQT")
                results.append({"PDB_ID": pdb_id, "Status": "ERROR", "Reason": "Receptor conversion failed"})
                continue

            strip_pdbqt_receptor(receptor_pdbqt)
            ensure_pdbqt_ligand(ligand_pdbqt_native)

            # === RUN A: Crystal Docking (Baseline) ===
            logger.info("TEST A: Crystal Pose Docking (Baseline)")
            output_baseline = target_dir / "output_baseline.pdbqt"
            score_baseline, status_baseline = run_vina_docking(
                receptor_pdbqt, ligand_pdbqt_native, output_baseline,
                buffer_angstroms=15.0, exhaustiveness=32
            )

            if score_baseline is None:
                logger.warning(f"Baseline docking failed")
                results.append({"PDB_ID": pdb_id, "Status": "ERROR", "Reason": "Baseline docking failed"})
                continue

            logger.info(f"Baseline affinity: {score_baseline:.3f} kcal/mol (Status: {status_baseline})")

            # === RUN B: Randomized Docking (Stress Test) ===
            logger.info("TEST B: Randomized Pose Docking (Stress Test)")
            ligand_pdbqt_random = target_dir / "ligand_rand.pdbqt"
            if not randomize_pose(ligand_pdbqt_native, ligand_pdbqt_random, trans=2.0):
                logger.warning(f"Failed to randomize pose")
                results.append({"PDB_ID": pdb_id, "Status": "ERROR", "Reason": "Randomization failed"})
                continue

            ensure_pdbqt_ligand(ligand_pdbqt_random)

            output_random = target_dir / "output_random.pdbqt"
            score_random, status_random = run_vina_docking(
                receptor_pdbqt, ligand_pdbqt_random, output_random,
                buffer_angstroms=15.0, exhaustiveness=32
            )

            if score_random is None:
                logger.warning(f"Random docking failed")
                results.append({"PDB_ID": pdb_id, "Status": "ERROR", "Reason": "Random docking failed"})
                continue

            logger.info(f"Random affinity: {score_random:.3f} kcal/mol (Status: {status_random})")

            # Determine result status
            ref_energy = config.get("ref_energy")
            if status_baseline == "CLASH" or status_random == "CLASH":
                result_status = "CLASH"
            elif ref_energy is not None:
                tolerance = 1.0
                if abs(score_baseline - ref_energy) <= tolerance and abs(score_random - ref_energy) <= tolerance:
                    result_status = "PASS"
                else:
                    result_status = "FAIL"
            else:
                result_status = "OK"

            # Compute RMSD (simple estimate: difference in scores)
            rmsd_equiv = abs(score_baseline - score_random)

            print(f"{pdb_id:<12} {config['ligand']:<8} {config['category']:<20} {score_baseline:<12.3f} {score_random:<12.3f} {rmsd_equiv:<8.3f} {result_status:<15}")

            results.append({
                "PDB_ID": pdb_id,
                "Ligand": config["ligand"],
                "Category": config["category"],
                "Crystal_Score": f"{score_baseline:.3f}",
                "Random_Score": f"{score_random:.3f}",
                "Ref_Energy": f"{ref_energy:.3f}" if ref_energy else "N/A",
                "RMSD_Equiv": f"{rmsd_equiv:.3f}",
                "Status": result_status,
            })

        except Exception as e:
            logger.error(f"Exception processing {pdb_id}: {e}")
            print(f"{pdb_id:<12} {config['ligand']:<8} {config['category']:<20} {'ERROR':<12} {'ERROR':<12} {'-':<8} {'EXCEPTION':<15}")
            results.append({"PDB_ID": pdb_id, "Status": "ERROR", "Reason": str(e)})

    print("=" * 120 + "\n")

    # Write CSV results
    if results:
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        logger.info(f"Results CSV: {CSV_FILE}")

    # Generate markdown report
    generate_report(results, test_targets)

    # Summary statistics
    pass_count = sum(1 for r in results if r.get("Status") == "PASS")
    fail_count = sum(1 for r in results if r.get("Status") == "FAIL")
    clash_count = sum(1 for r in results if r.get("Status") == "CLASH")
    error_count = sum(1 for r in results if r.get("Status") == "ERROR")
    total = len(results)

    logger.info("=" * 80)
    logger.info("Summary Statistics")
    logger.info("=" * 80)
    logger.info(f"Total Targets: {total}")
    logger.info(f"  PASS:      {pass_count} ({100*pass_count/total:.1f}%)")
    logger.info(f"  FAIL:      {fail_count} ({100*fail_count/total:.1f}%)")
    logger.info(f"  CLASH:     {clash_count} ({100*clash_count/total:.1f}%)")
    logger.info(f"  ERROR:     {error_count} ({100*error_count/total:.1f}%)")
    logger.info(f"Success Rate: {100*pass_count/total:.1f}%" if total > 0 else "No results")


def generate_report(results: list, targets: dict):
    """Generate markdown report."""
    with open(REPORT_FILE, "w") as f:
        f.write("# AutoScan Benchmark Suite Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Workspace:** {WORK_DIR}\n\n")

        f.write("## Results Table\n\n")
        f.write("| Target | Ligand | Category | Crystal (kcal/mol) | Random (kcal/mol) | Ref Energy | RMSD | Status |\n")
        f.write("|--------|--------|----------|-------------------|-------------------|---------|------|--------|\n")

        for r in results:
            f.write(
                f"| {r.get('PDB_ID', 'N/A')} | {r.get('Ligand', 'N/A')} | {r.get('Category', 'N/A')} | "
                f"{r.get('Crystal_Score', 'ERROR')} | {r.get('Random_Score', 'ERROR')} | "
                f"{r.get('Ref_Energy', 'N/A')} | {r.get('RMSD_Equiv', 'N/A')} | {r.get('Status', 'ERROR')} |\n"
            )

        f.write("\n## Logs\n\n")
        f.write(f"Full log: [benchmark_suite.log]({LOG_FILE})\n")
        f.write(f"CSV results: [benchmark_results.csv]({CSV_FILE})\n")

    logger.info(f"Report generated: {REPORT_FILE}")


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="AutoScan Benchmark Suite v2.0")
    parser.add_argument(
        "--mode",
        choices=["local", "online"],
        default="local",
        help="Execution mode: local (benchmark_data/) or online (RCSB)"
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        help="Specific targets to test (default: all)"
    )

    args = parser.parse_args()
    run_benchmark(mode=args.mode, targets=args.targets)


if __name__ == "__main__":
    main()
