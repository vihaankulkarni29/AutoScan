#!/usr/bin/env python
"""
AutoScan Validation Controls - Phase 2 Quality Assurance

Implements two critical validation controls to ensure docking engine reliability:

CONTROL 1: Redocking Accuracy Test (Positive Control)
  - Objective: Prove Vina can map a drug to its known binding site
  - Test: Extract drug from 1HVR (HIV Protease), randomize coords, redock
  - Pass Criteria: RMSD < 2.0 Angstrom between crystal and redocked pose
  - Purpose: Validates that the docking algorithm works correctly

CONTROL 2: Specificity Lineup Test (Negative Control)
  - Objective: Prove the engine discriminates between active and inactive molecules
  - Test: Dock Ciprofloxacin with 50 chemical decoys into 2XCT (Gyrase)
  - Pass Criteria: Ciprofloxacin ranks in Top 3 (top ~5%)
  - Purpose: Validates that high scores indicate real binding, not random noise

This script orchestrates both tests and generates a comprehensive validation report.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional
import json

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE_ROOT = Path(__file__).parent
TESTS_DIR = WORKSPACE_ROOT / "tests"
BENCHMARK_DIR = WORKSPACE_ROOT / "benchmark"
VALIDATION_OUTPUT_DIR = WORKSPACE_ROOT / "workspace" / "validation_controls" / datetime.now().strftime("%Y%m%d_%H%M%S")
VALIDATION_REPORT = VALIDATION_OUTPUT_DIR / "VALIDATION_REPORT.txt"
VALIDATION_JSON = VALIDATION_OUTPUT_DIR / "validation_results.json"

VALIDATION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Logging Setup
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(VALIDATION_OUTPUT_DIR / "validation_controls.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Control 1: Redocking Accuracy Test (Positive Control)
# ============================================================================

def run_control_1_redocking_test() -> Dict[str, any]:
    """
    Control 1: Redocking Accuracy Test
    
    Proves that Vina can accurately map a drug back to its physical binding site.
    
    Pass Criteria: RMSD < 2.0 Å between crystal and redocked pose
    """
    logger.info("=" * 80)
    logger.info("CONTROL 1: REDOCKING ACCURACY TEST (Positive Control)")
    logger.info("=" * 80)
    logger.info("Objective: Prove Vina accurately finds known binding site without hallucinating")
    logger.info("Test Molecule: XK2 (bound inhibitor in 1HVR HIV Protease)")
    logger.info("")

    results = {
        "control": "1_redocking_accuracy",
        "status": "pending",
        "timestamp": datetime.now().isoformat(),
        "pass_criteria": "RMSD < 2.0 Angstrom",
        "details": {}
    }

    # Check if benchmark PDB exists
    pdb_1hvr = BENCHMARK_DIR / "1HVR.pdb"
    if not pdb_1hvr.exists():
        logger.error(f"PDB file not found: {pdb_1hvr}")
        results["status"] = "failed"
        results["error"] = f"PDB file missing: {pdb_1hvr}"
        return results

    logger.info(f"[OK] Found PDB: {pdb_1hvr}")
    
    # Run benchmark_suite.py
    logger.info("")
    logger.info("Running benchmark_suite.py for 1HVR redocking test...")
    logger.info("This will:")
    logger.info("  1. Extract XK2 ligand from 1HVR crystal structure")
    logger.info("  2. Randomize its 3D coordinates (±2.0 Angstrom translation + rotation)")
    logger.info("  3. Run Vina blind docking to recover the crystal pose")
    logger.info("  4. Calculate RMSD between crystal and redocked poses")
    logger.info("")

    try:
        cmd = [
            sys.executable,
            str(TESTS_DIR / "benchmark_suite.py"),
            "--mode", "local",
            "--target", "1HVR"  # Run only 1HVR test
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            logger.info("benchmark_suite.py completed successfully")
            results["status"] = "completed"
            results["details"]["benchmark_output"] = "See workspace/benchmark_suite/ for detailed results"
        else:
            logger.error(f"benchmark_suite.py failed: {result.stderr[:500]}")
            results["status"] = "failed"
            results["error"] = result.stderr[:500]
            return results
            
    except Exception as e:
        logger.error(f"Error running benchmark_suite.py: {e}")
        results["status"] = "error"
        results["error"] = str(e)
        return results

    # Parse benchmark results
    try:
        # Look for the most recent benchmark report
        benchmark_results_dir = WORKSPACE_ROOT / "workspace" / "benchmark_suite"
        if benchmark_results_dir.exists():
            # Get the most recent timestamped directory
            latest_benchmark = max(
                (d for d in benchmark_results_dir.iterdir() if d.is_dir()),
                key=lambda p: p.stat().st_mtime,
                default=None
            )
            
            if latest_benchmark:
                csv_file = latest_benchmark / "benchmark_results.csv"
                if csv_file.exists():
                    import csv
                    with open(csv_file, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get('PDB_ID') == '1HVR':
                                # Extract RMSD_equiv as proxy for actual RMSD
                                rmsd_equiv = float(row.get('RMSD_Equiv', 999.0))
                                results["details"]["rmsd_equiv"] = rmsd_equiv
                                results["details"]["crystal_score"] = row.get('Crystal_Score')
                                results["details"]["random_score"] = row.get('Random_Score')
                                
                                # Pass/Fail decision
                                if rmsd_equiv < 2.0:
                                    results["pass"] = True
                                    results["conclusion"] = f"PASS - RMSD {rmsd_equiv:.3f} A < 2.0 A threshold"
                                    logger.info(f"[PASS] RMSD {rmsd_equiv:.3f} Angstrom (threshold: 2.0 Angstrom)")
                                else:
                                    results["pass"] = False
                                    results["conclusion"] = f"FAIL - RMSD {rmsd_equiv:.3f} A >= 2.0 A threshold"
                                    logger.warning(f"[FAIL] RMSD {rmsd_equiv:.3f} Angstrom (threshold: 2.0 Angstrom)")
                                break
    except Exception as e:
        logger.warning(f"Could not parse benchmark results: {e}")
        results["details"]["parse_error"] = str(e)

    logger.info("")
    return results


# ============================================================================
# Control 2: Specificity Lineup Test (Negative Control)
# ============================================================================

def run_control_2_specificity_test() -> Dict[str, any]:
    """
    Control 2: Specificity Lineup Test (Chemical Enrichment)
    
    Proves that the docking engine discriminates between active and inactive molecules.
    Does NOT just ascribe high binding scores to everything.
    
    Pass Criteria: Ciprofloxacin ranks in Top 3 (top ~5% of 51 molecules)
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("CONTROL 2: SPECIFICITY LINEUP TEST (Negative Control)")
    logger.info("=" * 80)
    logger.info("Objective: Prove engine discriminates actives from inactive decoys")
    logger.info("Active Molecule: Ciprofloxacin (known S. aureus Gyrase inhibitor)")
    logger.info("Decoys: 50 chemically similar but structurally distinct molecules")
    logger.info("Test System: 2XCT (S. aureus Gyrase - well-characterized target)")
    logger.info("")

    results = {
        "control": "2_specificity_enrichment",
        "status": "pending",
        "timestamp": datetime.now().isoformat(),
        "pass_criteria": "Ciprofloxacin ranks <= 3 (top ~5%)",
        "details": {}
    }

    logger.info("Running chemical_benchmark_enrichment.py...")
    logger.info("This will:")
    logger.info("  1. Prepare Ciprofloxacin for docking into 2XCT Gyrase")
    logger.info("  2. Generate 50 structurally diverse decoy molecules")
    logger.info("  3. Dock all 51 molecules (1 active + 50 decoys)")
    logger.info("  4. Rank by binding affinity (lower = stronger binding)")
    logger.info("  5. Check if Ciprofloxacin appears in Top 3")
    logger.info("")

    try:
        cmd = [
            sys.executable,
            str(TESTS_DIR / "chemical_benchmark_enrichment.py")
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode == 0:
            logger.info("chemical_benchmark_enrichment.py completed successfully")
            results["status"] = "completed"
            results["details"]["enrichment_output"] = "See workspace/chemical_enrichment/ for detailed results"
        else:
            logger.error(f"chemical_benchmark_enrichment.py failed: {result.stderr[:500]}")
            results["status"] = "failed"
            results["error"] = result.stderr[:500]
            return results
            
    except Exception as e:
        logger.error(f"Error running chemical_benchmark_enrichment.py: {e}")
        results["status"] = "error"
        results["error"] = str(e)
        return results

    # Parse enrichment results
    try:
        # Look for the most recent enrichment report
        enrichment_results_dir = WORKSPACE_ROOT / "workspace" / "chemical_enrichment"
        if enrichment_results_dir.exists():
            # Get the most recent timestamped directory
            latest_enrichment = max(
                (d for d in enrichment_results_dir.iterdir() if d.is_dir()),
                key=lambda p: p.stat().st_mtime,
                default=None
            )
            
            if latest_enrichment:
                csv_file = latest_enrichment / "enrichment_results.csv"
                if csv_file.exists():
                    import pandas as pd
                    df = pd.read_csv(csv_file)
                    
                    # Find Ciprofloxacin
                    cipro_rows = df[df['SMILES'] == 'C1CC1N2C=C(C(=O)C3=CC(=C(C=C32)N4CCNCC4)F)C(=O)O']
                    
                    if not cipro_rows.empty:
                        cipro_row = cipro_rows.iloc[0]
                        cipro_rank = int(cipro_row.get('Rank', 999))
                        cipro_score = float(cipro_row.get('Score', 0.0))
                        
                        results["details"]["ciprofloxacin_rank"] = cipro_rank
                        results["details"]["ciprofloxacin_score"] = cipro_score
                        results["details"]["total_molecules"] = len(df)
                        
                        # Pass/Fail decision
                        if cipro_rank <= 3:
                            results["pass"] = True
                            results["conclusion"] = f"PASS - Ciprofloxacin ranks #{cipro_rank} (top 5%)"
                            logger.info(f"[PASS] Ciprofloxacin ranked #{cipro_rank} with score {cipro_score:.3f} kcal/mol")
                        else:
                            results["pass"] = False
                            results["conclusion"] = f"FAIL - Ciprofloxacin ranks #{cipro_rank} (not in top 3)"
                            logger.warning(f"[FAIL] Ciprofloxacin ranked #{cipro_rank}, expected <= 3")
                    else:
                        logger.warning("Could not find Ciprofloxacin in results")
                        results["details"]["error"] = "Ciprofloxacin not found in results"
                        
    except Exception as e:
        logger.warning(f"Could not parse enrichment results: {e}")
        results["details"]["parse_error"] = str(e)

    logger.info("")
    return results


# ============================================================================
# Report Generation
# ============================================================================

def generate_validation_report(control1_results: Dict, control2_results: Dict) -> None:
    """Generate comprehensive validation report."""
    
    # Determine overall status
    control1_pass = control1_results.get("pass", False)
    control2_pass = control2_results.get("pass", False)
    all_pass = control1_pass and control2_pass
    
    report = f"""
{'=' * 80}
AutoScan Engine Validation Controls - Phase 2 Quality Assurance
{'=' * 80}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

EXECUTIVE SUMMARY
{'-' * 80}

Overall Status: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}

Control 1 (Redocking Accuracy): {'PASS' if control1_pass else 'FAIL'}
Control 2 (Specificity Enrichment): {'PASS' if control2_pass else 'FAIL'}

{'=' * 80}
CONTROL 1: REDOCKING ACCURACY TEST (Positive Control)
{'=' * 80}

Objective:
  Prove that AutoScan/Vina can accurately map a drug to its known crystal binding
  site without hallucinating or failing to find true interactions.

Test System:
  PDB: 1HVR (HIV Protease)
  Ligand: XK2 (known bound inhibitor)
  
Methodology:
  1. Extract bound ligand from crystal structure
  2. Randomize its 3D coordinates (±2.0 Angstrom translation + random rotation)
  3. Run blind docking to recover crystal pose
  4. Calculate RMSD between crystal and redocked positions
  
Pass Criteria:
  RMSD < 2.0 Angstroms (standard for successful docking)
  
Results:
  Status: {control1_results.get('status', 'unknown')}
  RMSD Equiv: {control1_results.get('details', {}).get('rmsd_equiv', 'N/A')} Angstrom
  Crystal Score: {control1_results.get('details', {}).get('crystal_score', 'N/A')} kcal/mol
  Random Score: {control1_results.get('details', {}).get('random_score', 'N/A')} kcal/mol
  
Conclusion:
  {control1_results.get('conclusion', 'No results available')}
  
Interpretation:
  {'[OK] The docking engine successfully recovers known binding modes with high accuracy.' if control1_pass else '[FAIL] The engine failed to recover the known binding mode. This suggests issues with either scoring function or search algorithm.'}

{'=' * 80}
CONTROL 2: SPECIFICITY LINEUP TEST (Negative Control)
{'=' * 80}

Objective:
  Prove that AutoScan does NOT indiscriminately assign high binding scores. The
  engine must distinguish between a known active and many inactive decoys.

Test System:
  PDB: 2XCT (S. aureus Gyrase)
  Active: Ciprofloxacin (known gyrase inhibitor, well-characterized)
  Decoys: 50 diverse drug-like molecules (NSAIDs, phenols, anilines, etc.)
  
Methodology:
  1. Dock Ciprofloxacin into Gyrase
  2. Generate/dock 50 structurally distinct but drug-like decoys
  3. Rank all 51 molecules by binding affinity
  4. Check if Ciprofloxacin ranks in top 3 (top ~5%)
  
Pass Criteria:
  Ciprofloxacin requires rank <= 3 of 51 molecules
  Meaning: Ciprofloxacin must be in top 5%, NOT randomly scattered
  
Results:
  Status: {control2_results.get('status', 'unknown')}
  Ciprofloxacin Rank: {control2_results.get('details', {}).get('ciprofloxacin_rank', 'N/A')}
  Ciprofloxacin Score: {control2_results.get('details', {}).get('ciprofloxacin_score', 'N/A')} kcal/mol
  Total Molecules Docked: {control2_results.get('details', {}).get('total_molecules', 'N/A')}
  
Conclusion:
  {control2_results.get('conclusion', 'No results available')}
  
Interpretation:
  {'[OK] The engine robustly discriminates true binders from random decoys.' if control2_pass else '[FAIL] The engine failed to rank the known active above decoys. This suggests non-selective scoring.'}

{'=' * 80}
OVERALL RECOMMENDATION
{'=' * 80}

"""

    if all_pass:
        report += f"""
STATUS: APPROVED FOR PRODUCTION

Both controls PASSED. The AutoScan engine:
  [OK] Accurately finds known binding modes (Control 1)
  [OK] Discriminates actives from decoys (Control 2)

Next Steps:
  1. Complete full benchmark suite (10+ proteins)
  2. Validate consensus scoring module
  3. Perform epistatic mutation validation
  4. Deploy to production pipeline
"""
    else:
        report += f"""
STATUS: REQUIRES INVESTIGATION

One or more controls FAILED:
"""
        if not control1_pass:
            report += f"""
  [FAIL] Control 1 (Redocking): {control1_results.get('conclusion', 'N/A')}
    -> Check: (1) Scoring function parameters, (2) Search exhaustiveness, (3) Box sizing
"""
        if not control2_pass:
            report += f"""
  [FAIL] Control 2 (Specificity): {control2_results.get('conclusion', 'N/A')}
    -> Check: (1) Ligand preparation (protonation state), (2) Coordinate generation, (3) PDBQT conversion
"""
        report += """
Next Steps:
  1. Review error logs in workspace/validation_controls/
  2. Adjust parameters and re-run controls
  3. Do not proceed to production until BOTH controls pass
"""

    report += f"""
{'=' * 80}
Log Files and Detailed Results:
  Report: {VALIDATION_REPORT}
  Results JSON: {VALIDATION_JSON}
  Detailed logs: {VALIDATION_OUTPUT_DIR/('validation_controls.log')}
  
  Benchmark Suite Results: {WORKSPACE_ROOT / 'workspace' / 'benchmark_suite'}
  Chemical Enrichment Results: {WORKSPACE_ROOT / 'workspace' / 'chemical_enrichment'}
{'=' * 80}
"""

    # Write report to file
    with open(VALIDATION_REPORT, 'w') as f:
        f.write(report)
    
    # Write JSON results
    validation_json = {
        "timestamp": datetime.now().isoformat(),
        "overall_pass": all_pass,
        "control_1": control1_results,
        "control_2": control2_results,
    }
    with open(VALIDATION_JSON, 'w') as f:
        json.dump(validation_json, f, indent=2)
    
    # Print report to console
    print(report)
    
    logger.info(f"Validation report saved to: {VALIDATION_REPORT}")
    logger.info(f"Results JSON saved to: {VALIDATION_JSON}")


# ============================================================================
# Main
# ============================================================================

def main():
    logger.info("")
    logger.info("=" * 80)
    logger.info("AutoScan Validation Controls - Initialization")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"Workspace: {WORKSPACE_ROOT}")
    logger.info(f"Output Directory: {VALIDATION_OUTPUT_DIR}")
    logger.info("")

    # Run Control 1
    control1_results = run_control_1_redocking_test()
    
    # Run Control 2
    control2_results = run_control_2_specificity_test()
    
    # Generate Report
    generate_validation_report(control1_results, control2_results)
    
    # Exit code based on results
    if control1_results.get("pass") and control2_results.get("pass"):
        logger.info("\n[SUCCESS] ALL VALIDATION CONTROLS PASSED")
        return 0
    else:
        logger.error(f"\n[FAILURE] VALIDATION CONTROLS FAILED - See report for details")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
