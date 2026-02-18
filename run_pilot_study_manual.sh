#!/bin/bash
# Quick Reference: CLI Commands for Pilot Study
# Run manual docking experiments with the new --mutation and --output flags

# ============================================================================
# SETUP: Ensure you have test data
# ============================================================================
mkdir -p pilot_study/data/receptors pilot_study/data/ligands pilot_study/results

# For this demo, the script will create mock files. In production:
# - Download 3NUU.pdb from RCSB (https://www.rcsb.org/structure/3NUU)
# - Prepare ligands via RDKit: SMILES → PDB conversion
# - Adjust binding site coordinates to your target

# ============================================================================
# EXPERIMENT 1: WILD-TYPE DOCKING (No mutation)
# ============================================================================

echo "=== WILD-TYPE DOCKING ==="
echo "These commands dock 5 HIV-approved antibiotics into Wild-Type Gyrase"

# 1. Ciprofloxacin (2nd gen fluoroquinolone)
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/ciprofloxacin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --output pilot_study/results/WT_ciprofloxacin.json

# 2. Levofloxacin (S-enantiomer)
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/levofloxacin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --output pilot_study/results/WT_levofloxacin.json

# 3. Moxifloxacin (4th gen fluoroquinolone)
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/moxifloxacin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --output pilot_study/results/WT_moxifloxacin.json

# 4. Nalidixic Acid (1st gen quinolone, baseline)
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/nalidixic_acid.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --output pilot_study/results/WT_nalidixic_acid.json

# 5. Novobiocin (Coumarin, GyrB inhibitor)
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/novobiocin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --output pilot_study/results/WT_novobiocin.json

# ============================================================================
# EXPERIMENT 2: MUTANT DOCKING (D87G mutation applied)
# ============================================================================

echo ""
echo "=== MUTANT DOCKING (D87G) ==="
echo "Same 5 antibiotics, but now docked into Chain A, Residue 87: Asp→Gly"
echo "This mutation is a known fluoroquinolone resistance mechanism"

# 1. Ciprofloxacin + D87G
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/ciprofloxacin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --mutation A:87:D:G \
  --output pilot_study/results/MUT_D87G_ciprofloxacin.json

# 2. Levofloxacin + D87G
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/levofloxacin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --mutation A:87:D:G \
  --output pilot_study/results/MUT_D87G_levofloxacin.json

# 3. Moxifloxacin + D87G
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/moxifloxacin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --mutation A:87:D:G \
  --output pilot_study/results/MUT_D87G_moxifloxacin.json

# 4. Nalidixic Acid + D87G
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/nalidixic_acid.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --mutation A:87:D:G \
  --output pilot_study/results/MUT_D87G_nalidixic_acid.json

# 5. Novobiocin + D87G
python -m autoscan dock \
  --receptor pilot_study/data/receptors/3NUU_WT.pdb \
  --ligand pilot_study/data/ligands/novobiocin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --mutation A:87:D:G \
  --output pilot_study/results/MUT_D87G_novobiocin.json

# ============================================================================
# ANALYSIS: Compare WT vs MUT binding affinity
# ============================================================================

echo ""
echo "=== COMPARING RESULTS ==="
python3 << 'EOF'
import json
from pathlib import Path

results_dir = Path("pilot_study/results")
results = {}

# Parse JSON files
for json_file in results_dir.glob("*.json"):
    with open(json_file, 'r') as f:
        results[json_file.stem] = json.load(f)

# Extract drug names and compute ΔΔG
print("\nDrug            | WT (kcal/mol) | MUT (kcal/mol) | ΔΔG (MUT-WT) | Status")
print("─" * 75)

for drug in ["ciprofloxacin", "levofloxacin", "moxifloxacin", "nalidixic_acid", "novobiocin"]:
    wt_key = f"WT_{drug}"
    mut_key = f"MUT_D87G_{drug}"
    
    if wt_key in results and mut_key in results:
        wt_aff = results[wt_key]["binding_affinity_kcal_mol"]
        mut_aff = results[mut_key]["binding_affinity_kcal_mol"]
        delta_delta_g = mut_aff - wt_aff
        
        # Interpret result
        if delta_delta_g > 2.0:
            status = "🔴 Resistant"
        elif delta_delta_g > 0.5:
            status = "🟡 Partial R"
        elif delta_delta_g < -0.5:
            status = "🟢 Hypersens"
        else:
            status = "⚪ Neutral"
        
        print(f"{drug:15} | {wt_aff:13.2f} | {mut_aff:14.2f} | {delta_delta_g:+12.2f} | {status}")

EOF

# ============================================================================
# INTERPRETATION
# ============================================================================

echo ""
echo "=== INTERPRETATION ==="
echo "ΔΔG = Binding Affinity (MUT) - Binding Affinity (WT)"
echo ""
echo "🔴 ΔΔG > +2.0 kcal/mol  : RESISTANT (mutation destabilizes drug binding)"
echo "🟡 ΔΔG +0.5 to +2.0    : PARTIAL RESISTANCE"
echo "⚪ ΔΔG -0.5 to +0.5     : NEUTRAL (no selectivity)"
echo "🟢 ΔΔG < -0.5 kcal/mol  : HYPERSENSITIVE (mutation enhances binding)"
echo ""
echo "✓ If fluoroquinolones show ΔΔG > +2.0, AutoScan correctly predicts"
echo "  that D87G confers resistance (validates tool for resistance prediction)"
echo ""

# ============================================================================
# EXPORT RESULTS
# ============================================================================

echo "Results are in:"
echo "  • pilot_study/results/*.json       (Individual docking results)"
echo "  • pilot_study/results/docking_results.csv  (Summary table)"
echo "  • pilot_study/results/PILOT_STUDY_REPORT.md (Analysis report)"
