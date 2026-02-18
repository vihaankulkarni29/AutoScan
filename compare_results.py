import json
from pathlib import Path

print("\n" + "="*120)
print("PILOT STUDY RESULTS: VINA vs CONSENSUS SCORING COMPARISON")
print("="*120 + "\n")

results_dir = Path("pilot_study/results")

# Read new results (with consensus)
data = []
for json_file in sorted(results_dir.glob("*.json")):
    if "REPORT" not in json_file.name:
        with open(json_file, 'r') as f:
            result = json.load(f)
            parts = json_file.stem.split("_", 1)
            target = parts[0]
            drug = parts[1]
            
            data.append({
                "Drug": drug,
                "Target": target,
                "Vina (kcal/mol)": result.get("binding_affinity_kcal_mol", 0),
                "Consensus (kcal/mol)": result.get("consensus_affinity_kcal_mol", 0),
                "Uncertainty (±)": result.get("consensus_uncertainty_kcal_mol", 0),
            })

# Organize by drug
drugs_data = {}
for row in data:
    drug = row["Drug"]
    if drug not in drugs_data:
        drugs_data[drug] = {}
    drugs_data[drug][row["Target"]] = row

# Display comparison table
print("SELECTIVITY ANALYSIS (Consensus Scoring with Uncertainty)")
print("-" * 130)
print(f"{'Drug':<20} | {'WT Vina':<12} | {'WT Consensus':<17} | {'MUT Vina':<12} | {'MUT Consensus':<17} | {'ΔΔG':<8} | {'Unc':<6} | Status")
print("-" * 130)

for drug in sorted(drugs_data.keys()):
    wt = drugs_data[drug].get("WT", {})
    mut = drugs_data[drug].get("MUT", {})
    
    wt_vina = wt.get("Vina (kcal/mol)", 0)
    wt_cons = wt.get("Consensus (kcal/mol)", 0)
    mut_vina = mut.get("Vina (kcal/mol)", 0)
    mut_cons = mut.get("Consensus (kcal/mol)", 0)
    mut_unc = mut.get("Uncertainty (±)", 0)
    wt_unc = wt.get("Uncertainty (±)", 0)
    
    delta_delta_g = mut_cons - wt_cons
    avg_unc = (wt_unc + mut_unc) / 2
    
    if delta_delta_g > 2.0:
        status = "🔴 RESIS"
    elif delta_delta_g > 0.5:
        status = "🟡 PART-R"
    elif delta_delta_g < -0.5:
        status = "🟢 HYPER"
    else:
        status = "⚪ NEUTR"
    
    print(f"{drug:<20} | {wt_vina:>11.2f} | {wt_cons:>6.2f} ± {wt_unc:>5.2f} | {mut_vina:>11.2f} | {mut_cons:>6.2f} ± {mut_unc:>5.2f} | {delta_delta_g:>+7.2f} | {avg_unc:>5.2f} | {status}")

print("-" * 130)

print("\n✨ KEY OBSERVATIONS:\n")
print("  1. Consensus Scoring provides ± uncertainty estimates (confidence metrics)")
print("  2. Vina scores differ from Consensus (multi-engine weighted average)")
print("  3. Uncertainty bounds quantify prediction reliability")
print("  4. Smaller ± values = higher confidence in prediction")
print("  5. ΔΔG selectivity shows drug-specific patterns")

print("\n📊 FILES GENERATED:")
for f in sorted(results_dir.glob("*")):
    if f.is_file():
        print(f"  ✓ {f.name} ({f.stat().st_size:,} bytes)")

print("\n📋 REPORT CONTENTS:")
report_file = results_dir / "PILOT_STUDY_REPORT.md"
if report_file.exists():
    with open(report_file, 'r') as f:
        lines = f.readlines()
        print(f"  Generated report has {len(lines)} lines")
        # Show first 50 lines (table summary)
        print("\n" + "="*120)
        print("REPORT SUMMARY (First 50 lines):")
        print("-" * 120)
        for line in lines[:50]:
            print(line.rstrip())

print("\n" + "="*120)
print("STATUS: ✅ PILOT STUDY WITH CONSENSUS SCORING COMPLETE")
print("="*120 + "\n")
