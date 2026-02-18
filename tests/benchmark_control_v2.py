#!/usr/bin/env python
"""
AutoScan Calibration Control Study (v2)
=========================================
Compares Baseline Docking (Crystal Pose) vs. Stress Docking (Randomized Pose)
to isolate physics errors from search errors across 7 gold standard systems.

Date: 2026-02-17
Author: AutoScan Validation Suite
"""

import os
import sys
import csv
import subprocess
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional
import tempfile
import shutil

import numpy as np
from Bio.PDB import PDBParser, PDBIO, Select, PPBuilder

# Import autoscan modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from autoscan.docking.vina import VinaEngine
from autoscan.engine.vina import VinaWrapper

# ============================================================================
# Configuration
# ============================================================================

CONTROLS = {
    "1STP": {"ligand": "BTN", "name": "Streptavidin", "ref_energy": -18.3},
    "3PTB": {"ligand": "BEN", "name": "Trypsin", "ref_energy": -6.4},
    "1HVR": {"ligand": "XK2", "name": "HIV Protease", "ref_energy": -12.3},
    "1AID": {"ligand": "BEA", "name": "HIV Protease (Ref)", "ref_energy": -9.7},
    "2J7E": {"ligand": "PUZ", "name": "HSP90", "ref_energy": -8.2},
    "1TNH": {"ligand": "BEN", "name": "Thrombin", "ref_energy": -7.3},
}

BENCHMARK_DATA_DIR = Path(__file__).parent / "benchmark_data"
WORK_DIR = Path(__file__).parent.parent / "workspace" / "control_test_v2"
WORK_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_CSV = WORK_DIR / "benchmark_control_results.csv"
LOG_FILE = WORK_DIR / "calibration_control.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Helper Functions
# ============================================================================

def resolve_executable(name: str, override: str) -> Tuple[str, Optional[str]]:
    """Resolve executable path, checking override first then PATH."""
    if override and (Path(override).exists() or shutil.which(override)):
        return override, None
    resolved = shutil.which(name)
    if resolved:
        return resolved, None
    return override or name, f"Missing required tool: {name}"


def get_pdb_file(pdb_id: str) -> Optional[Path]:
    """Get local PDB file from benchmark_data directory."""
    pdb_file = BENCHMARK_DATA_DIR / f"{pdb_id}.pdb"
    if pdb_file.exists():
        logger.info(f"Using local PDB file: {pdb_file}")
        return pdb_file
    logger.warning(f"PDB file not found: {pdb_file}")
    return None


def check_ligand_exists(pdb_file: Path, ligand_code: str) -> bool:
    """Check if ligand exists in PDB file."""
    try:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("pdb", str(pdb_file))
        
        for model in structure:
            for chain in model:
                for residue in chain:
                    if residue.get_resname().strip() == ligand_code.strip():
                        return True
        return False
    except Exception as e:
        logger.warning(f"Error checking ligand {ligand_code} in {pdb_file}: {e}")
        return False


def extract_ligand(pdb_file: Path, ligand_code: str, output_pdb: Path) -> bool:
    """Extract ligand residue from PDB file."""
    try:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("pdb", str(pdb_file))
        
        class LigandSelector(Select):
            def accept_residue(self, residue):
                return residue.get_resname().strip() == ligand_code.strip()
        
        io = PDBIO()
        io.set_structure(structure)
        io.save(str(output_pdb), LigandSelector())
        
        # Verify file was created and has content
        if output_pdb.stat().st_size > 0:
            return True
        return False
    except Exception as e:
        logger.warning(f"Error extracting ligand: {e}")
        return False


def extract_receptor(pdb_file: Path, ligand_code: str, output_pdb: Path) -> bool:
    """Extract receptor (everything except ligand) from PDB file."""
    try:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("pdb", str(pdb_file))
        
        class ReceptorSelector(Select):
            def accept_residue(self, residue):
                # Exclude the ligand residue
                if residue.get_resname().strip() == ligand_code.strip():
                    return False
                # Exclude water and other unwanted residues
                if residue.get_resname().strip() in ["HOH", "WAT"]:
                    return False
                return True
        
        io = PDBIO()
        io.set_structure(structure)
        io.save(str(output_pdb), ReceptorSelector())
        
        if output_pdb.stat().st_size > 0:
            return True
        return False
    except Exception as e:
        logger.warning(f"Error extracting receptor: {e}")
        return False


def pdb_to_pdbqt(pdb_file: Path, pdbqt_file: Path, is_ligand: bool = True) -> bool:
    """Convert PDB to PDBQT using obabel."""
    try:
        cmd = ["obabel", str(pdb_file), f"-O{pdbqt_file}"]
        if is_ligand:
            cmd.extend(["-xh"])  # Add hydrogens for ligand
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and pdbqt_file.exists():
            return True
        logger.warning(f"obabel conversion failed: {result.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.warning(f"obabel timeout for {pdb_file}")
        return False
    except Exception as e:
        logger.warning(f"Error converting to PDBQT: {e}")
        return False


def smart_randomize(pdbqt_file: Path, output_file: Path, max_translation: float = 1.0) -> bool:
    """
    Randomize ligand pose with controlled perturbation.
    
    Args:
        pdbqt_file: Input PDBQT file
        output_file: Output PDBQT file with randomized pose
        max_translation: Maximum translation in Angstroms
    """
    try:
        with open(pdbqt_file, 'r') as f:
            lines = f.readlines()
        
        # Extract atomic coordinates
        coords = []
        atom_lines = []
        for line in lines:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    coords.append([x, y, z])
                    atom_lines.append(line)
                except ValueError:
                    continue
        
        if not coords:
            return False
        
        coords = np.array(coords)
        
        # Random rotation matrix (Rodrigues formula)
        axis = np.random.randn(3)
        axis = axis / np.linalg.norm(axis)
        angle = np.random.uniform(0, 2 * np.pi)
        
        K = np.array([
            [0, -axis[2], axis[1]],
            [axis[2], 0, -axis[0]],
            [-axis[1], axis[0], 0]
        ])
        R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
        
        # Center, rotate, translate
        centroid = coords.mean(axis=0)
        centered = coords - centroid
        rotated = (R @ centered.T).T
        translation = np.random.uniform(-max_translation, max_translation, 3)
        new_coords = rotated + centroid + translation
        
        # Write modified PDBQT
        with open(output_file, 'w') as f:
            coord_idx = 0
            for line in lines:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    if coord_idx < len(new_coords):
                        x, y, z = new_coords[coord_idx]
                        # Reconstruct line with new coordinates
                        new_line = (
                            line[:30] +
                            f"{x:8.3f}{y:8.3f}{z:8.3f}" +
                            line[54:]
                        )
                        f.write(new_line)
                        coord_idx += 1
                    else:
                        f.write(line)
                else:
                    f.write(line)
        
        return True
    except Exception as e:
        logger.warning(f"Error randomizing pose: {e}")
        return False


def parse_pdbqt_coords(pdbqt_file: Path) -> Optional[np.ndarray]:
    """Extract heavy atom coordinates from PDBQT file."""
    try:
        coords = []
        with open(pdbqt_file, 'r') as f:
            for line in f:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    atom_type = line[77:79].strip()
                    if atom_type != "H":  # Skip hydrogens
                        try:
                            x = float(line[30:38])
                            y = float(line[38:46])
                            z = float(line[46:54])
                            coords.append([x, y, z])
                        except ValueError:
                            continue
        return np.array(coords) if coords else None
    except Exception as e:
        logger.warning(f"Error parsing PDBQT coordinates: {e}")
        return None


def ensure_pdbqt_root(pdbqt_path: Path) -> None:
    """Wrap PDBQT file with ROOT and ENDROOT tags; keep only valid records."""
    lines = pdbqt_path.read_text(encoding="utf-8").splitlines()
    if any(line.startswith("ROOT") for line in lines):
        return

    remarks = [line for line in lines if line.startswith("REMARK")]
    atoms = [line for line in lines if line.startswith("ATOM") or line.startswith("HETATM")]
    if not atoms:
        logger.warning(f"No ATOM records found in {pdbqt_path}")
        return

    wrapped = []
    wrapped.extend(remarks)
    wrapped.append("ROOT")
    wrapped.extend(atoms)
    wrapped.append("ENDROOT")
    wrapped.append("TORSDOF 0")
    pdbqt_path.write_text("\n".join(wrapped) + "\n", encoding="utf-8")


def strip_pdbqt_root(pdbqt_path: Path) -> None:
    """Remove ROOT/ENDROOT tags and clean up invalid records from receptor PDBQT file."""
    lines = pdbqt_path.read_text(encoding="utf-8").splitlines()
    cleaned = []
    for line in lines:
        # Keep only REMARK and valid ATOM/HETATM records
        if line.startswith("REMARK") or line.startswith("ATOM") or line.startswith("HETATM"):
            cleaned.append(line)
    pdbqt_path.write_text("\n".join(cleaned) + "\n", encoding="utf-8")


def run_vina_docking(
    receptor_pdbqt: Path,
    ligand_pdbqt: Path,
    output_pdbqt: Path,
    buffer_angstroms: float = 15.0,
    vina_exe: str = "vina"
) -> Tuple[Optional[float], str]:
    """
    Run Vina docking with crash guard.
    
    Returns:
        (affinity_score, error_message)
    """
    try:
        # Calculate box from ligand coordinates
        ligand_coords = parse_pdbqt_coords(ligand_pdbqt)
        if ligand_coords is None or len(ligand_coords) == 0:
            return None, "No ligand coordinates found"
        
        ligand_center = ligand_coords.mean(axis=0)
        ligand_extent = ligand_coords.max(axis=0) - ligand_coords.min(axis=0)
        box_size = ligand_extent + buffer_angstroms
        
        logger.info(
            f"  Box: center={ligand_center}, size={box_size}, "
            f"buffer={buffer_angstroms}Å"
        )
        
        # Use VinaEngine to run docking
        engine = VinaEngine(
            receptor_pdbqt=str(receptor_pdbqt),
            ligand_pdbqt=str(ligand_pdbqt),
            vina_executable=vina_exe
        )
        
        score = engine.run(
            center=ligand_center.tolist(),
            buffer_angstroms=buffer_angstroms,
            cpu=4,
            num_modes=9,
            output_pdbqt=str(output_pdbqt)
        )
        
        # Crash guard: reject scores > 100 or < -200
        if score is None or score > 100 or score < -200:
            logger.warning(f"  Energy explosion detected: {score} kcal/mol")
            return 999.9, "EXPLOSION"
        
        return score, "OK"
    
    except Exception as e:
        logger.error(f"Vina crash: {e}")
        return 999.9, f"EXCEPTION: {str(e)}"


def assess_status(baseline_score: float, random_score: float) -> str:
    """Assess test status based on scores."""
    if baseline_score == 999.9 or random_score == 999.9:
        return "CLASH"
    elif random_score < -6.0 and baseline_score < -6.0:
        return "PASS"
    else:
        return "FAIL"


# ============================================================================
# Main Execution
# ============================================================================

def main():
    # Resolve vina executable
    vina_override = os.environ.get("VINA_EXE", "tools/vina.exe")
    vina_exe, vina_error = resolve_executable("vina", vina_override)
    if vina_error:
        logger.error(vina_error)
        print(f"ERROR: {vina_error}")
        return
    logger.info(f"Using Vina: {vina_exe}")
    
    logger.info("=" * 80)
    logger.info("AutoScan Calibration Control Study v2")
    logger.info(f"Workspace: {WORK_DIR}")
    logger.info("=" * 80)
    
    # Prepare CSV file
    results = []
    
    print("\n" + "=" * 100)
    print(f"{'Target':<12} {'Ligand':<8} {'Name':<20} {'Baseline':<12} {'Random':<12} {'Status':<15}")
    print("=" * 100)
    
    for pdb_id, metadata in CONTROLS.items():
        ligand_code = metadata["ligand"]
        name = metadata["name"]
        ref_energy = metadata["ref_energy"]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {pdb_id} ({ligand_code}) - {name}")
        logger.info(f"{'='*60}")
        
        # Create target directory
        target_dir = WORK_DIR / pdb_id
        target_dir.mkdir(exist_ok=True)
        
        # Get local PDB file
        pdb_file = get_pdb_file(pdb_id)
        if not pdb_file or not pdb_file.exists():
            logger.warning(f"SKIP: {pdb_id} - PDB file not found in benchmark_data")
            print(f"{pdb_id:<12} {ligand_code:<8} {name:<20} {'SKIP':<12} {'SKIP':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Name": name,
                "Baseline_Score": "SKIP",
                "Random_Score": "SKIP",
                "Status": "ERROR"
            })
            continue
        
        # Check if ligand exists
        if not check_ligand_exists(pdb_file, ligand_code):
            logger.warning(f"SKIP: {pdb_id} - Ligand {ligand_code} not found in PDB")
            print(f"{pdb_id:<12} {ligand_code:<8} {name:<20} {'SKIP':<12} {'SKIP':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Name": name,
                "Baseline_Score": "SKIP",
                "Random_Score": "SKIP",
                "Status": "ERROR_LIGAND_NOT_FOUND"
            })
            continue
        
        # Extract ligand and receptor
        ligand_pdb = target_dir / "ligand.pdb"
        receptor_pdb = target_dir / "receptor.pdb"
        
        if not extract_ligand(pdb_file, ligand_code, ligand_pdb):
            logger.error(f"Failed to extract ligand from {pdb_id}")
            print(f"{pdb_id:<12} {ligand_code:<8} {name:<20} {'ERROR':<12} {'ERROR':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Name": name,
                "Baseline_Score": "ERROR",
                "Random_Score": "ERROR",
                "Status": "ERROR"
            })
            continue
        
        if not extract_receptor(pdb_file, ligand_code, receptor_pdb):
            logger.error(f"Failed to extract receptor from {pdb_id}")
            print(f"{pdb_id:<12} {ligand_code:<8} {name:<20} {'ERROR':<12} {'ERROR':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Name": name,
                "Baseline_Score": "ERROR",
                "Random_Score": "ERROR",
                "Status": "ERROR"
            })
            continue
        
        # Convert to PDBQT
        ligand_pdbqt = target_dir / "ligand_native.pdbqt"
        ligand_rand_pdbqt = target_dir / "ligand_rand.pdbqt"
        receptor_pdbqt = target_dir / "receptor.pdbqt"
        
        if not pdb_to_pdbqt(ligand_pdb, ligand_pdbqt, is_ligand=True):
            logger.error(f"Failed to convert ligand to PDBQT")
            print(f"{pdb_id:<12} {ligand_code:<8} {name:<20} {'ERROR':<12} {'ERROR':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Name": name,
                "Baseline_Score": "ERROR",
                "Random_Score": "ERROR",
                "Status": "ERROR"
            })
            continue
        
        if not pdb_to_pdbqt(receptor_pdb, receptor_pdbqt, is_ligand=False):
            logger.error(f"Failed to convert receptor to PDBQT")
            print(f"{pdb_id:<12} {ligand_code:<8} {name:<20} {'ERROR':<12} {'ERROR':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Name": name,
                "Baseline_Score": "ERROR",
                "Random_Score": "ERROR",
                "Status": "ERROR"
            })
            continue
        
        # Wrap ligand PDBQT with ROOT tags; strip ROOT tags from receptor (Vina expects plain receptor)
        ensure_pdbqt_root(ligand_pdbqt)
        strip_pdbqt_root(receptor_pdbqt)
        
        # Create randomized ligand
        if not smart_randomize(ligand_pdbqt, ligand_rand_pdbqt, max_translation=1.0):
            logger.error(f"Failed to randomize ligand pose")
            print(f"{pdb_id:<12} {ligand_code:<8} {name:<20} {'ERROR':<12} {'ERROR':<12} {'ERROR':<15}")
            results.append({
                "PDB_ID": pdb_id,
                "Ligand": ligand_code,
                "Name": name,
                "Baseline_Score": "ERROR",
                "Random_Score": "ERROR",
                "Status": "ERROR"
            })
            continue
        
        # Wrap randomized ligand with ROOT tags (Vina requires ROOT for ligands)
        ensure_pdbqt_root(ligand_rand_pdbqt)
        
        # Test A: Baseline Docking (Crystal Pose)
        logger.info("TEST A: Baseline Docking (Crystal Pose)")
        baseline_output = target_dir / "output_baseline.pdbqt"
        baseline_score, baseline_err = run_vina_docking(
            receptor_pdbqt, ligand_pdbqt, baseline_output, vina_exe=vina_exe
        )
        
        if baseline_score is None:
            logger.error(f"Baseline docking failed: {baseline_err}")
            baseline_score = 999.9
        else:
            logger.info(f"Baseline affinity: {baseline_score:.3f} kcal/mol")
        
        # Test B: Stress Docking (Randomized Pose)
        logger.info("TEST B: Stress Docking (Randomized Pose)")
        random_output = target_dir / "output_random.pdbqt"
        random_score, random_err = run_vina_docking(
            receptor_pdbqt, ligand_rand_pdbqt, random_output, vina_exe=vina_exe
        )
        
        if random_score is None:
            logger.error(f"Stress docking failed: {random_err}")
            random_score = 999.9
        else:
            logger.info(f"Random affinity: {random_score:.3f} kcal/mol")
        
        # Assess status
        status = assess_status(baseline_score, random_score)
        
        logger.info(f"\nResult: {status}")
        logger.info(f"Reference energy: {ref_energy} kcal/mol")
        
        # Store result
        results.append({
            "PDB_ID": pdb_id,
            "Ligand": ligand_code,
            "Name": name,
            "Baseline_Score": f"{baseline_score:.3f}" if baseline_score != 999.9 else "999.9",
            "Random_Score": f"{random_score:.3f}" if random_score != 999.9 else "999.9",
            "Status": status
        })
        
        # Print table row
        baseline_str = f"{baseline_score:.3f}" if baseline_score != 999.9 else "CLASH"
        random_str = f"{random_score:.3f}" if random_score != 999.9 else "CLASH"
        print(f"{pdb_id:<12} {ligand_code:<8} {name:<20} {baseline_str:<12} {random_str:<12} {status:<15}")
    
    print("=" * 100 + "\n")
    
    # Write CSV results
    if results:
        with open(RESULTS_CSV, 'w', newline='') as csvfile:
            fieldnames = ["PDB_ID", "Ligand", "Name", "Baseline_Score", "Random_Score", "Status"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        logger.info(f"Results saved to {RESULTS_CSV}")
    
    # Summary statistics
    passed = sum(1 for r in results if r["Status"] == "PASS")
    clash = sum(1 for r in results if r["Status"] == "CLASH")
    failed = sum(1 for r in results if r["Status"] == "FAIL")
    error = sum(1 for r in results if r["Status"] == "ERROR" or r["Status"] == "ERROR_LIGAND_NOT_FOUND")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Summary Statistics")
    logger.info(f"{'='*60}")
    logger.info(f"Total Targets: {len(results)}")
    logger.info(f"PASS:  {passed}")
    logger.info(f"CLASH: {clash}")
    logger.info(f"FAIL:  {failed}")
    logger.info(f"ERROR: {error}")
    if len(results) > 0:
        logger.info(f"Success Rate: {(passed / len(results) * 100):.1f}%")
    logger.info(f"{'='*60}\n")
    
    print(f"\nSummary Statistics:")
    print(f"  Total Targets: {len(results)}")
    print(f"  PASS:  {passed}")
    print(f"  CLASH: {clash}")
    print(f"  FAIL:  {failed}")
    print(f"  ERROR: {error}")
    if len(results) > 0:
        print(f"  Success Rate: {(passed / len(results) * 100):.1f}%\n")


if __name__ == "__main__":
    main()
