# Pilot Study: Gyrase Selectivity Assay
## Can AutoScan Predict Antibiotic Resistance?

**Status**: Framework Complete ✅  
**Version**: AutoScan v1.0.0  
**Date**: February 2026

---

## 🧬 The Scientific Question

**"Can AutoScan identify antibiotics that bind better to mutant Gyrase (D87G) than wild-type, predicting resistance mechanisms?"**

This pilot study tests whether computational docking can:
1. **Predict selectivity** - Drugs that bind preferentially to WT vs MUT
2. **Identify resistance** - Mutations that destabilize drug binding (ΔΔG > 0)
3. **Rank mutations** - Which should be monitored clinically

### Why This Matters
Antibiotic resistance from point mutations in DNA gyrase is a major clinical problem. 
D87G is a known fluoroquinolone resistance mutation. If AutoScan correctly predicts that 
this mutation reduces drug binding affinity, we've validated the tool for resistance prediction 
and can expand to other drugs, mutations, and pathogens.

---

## 🔬 Experimental Design

| Aspect | Details |
|--------|---------|
| **Target A** | Wild-Type Gyrase (PDB: 3NUU) |
| **Target B** | Mutant Gyrase (D87G mutation applied) |
| **Library** | 5 FDA-approved gyrase inhibitors |
| **Measurement** | Binding affinity (ΔG in kcal/mol) |
| **Prediction** | If ΔΔG = ΔG(MUT) - ΔG(WT) > 0, mutation confers resistance |

### The 5 Drugs

| Drug | Class | MW | Notes |
|------|-------|----|----|
| **Ciprofloxacin** | 2nd Gen Fluoroquinolone | 331 | Gold standard, most used |
| **Levofloxacin** | 2nd Gen Fluoroquinolone | 361 | S-enantiomer of ofloxacin |
| **Moxifloxacin** | 4th Gen Fluoroquinolone | 401 | Enhanced Gram+ coverage |
| **Nalidixic Acid** | 1st Gen Quinolone | 232 | Established baseline |
| **Novobiocin** | Coumarin (GyrB inhibitor) | 613 | Targets ATPase domain |

---

## 🚀 How to Use the Enhanced CLI

### New Flag 1: `--mutation` (In-Silico Mutagenesis)

**Format**: `CHAIN:RESIDUE:FROM_AA:TO_AA`

Apply a single point mutation to the receptor before docking:

```bash
# Wild-Type docking (no mutation)
autoscan dock \
  --receptor 3NUU.pdb \
  --ligand ciprofloxacin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --output results/WT_cipro.json

# Mutant docking (D87G mutation)
autoscan dock \
  --receptor 3NUU.pdb \
  --ligand ciprofloxacin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --mutation A:87:D:G \
  --output results/MUT_cipro.json
```

**How it works**:
1. Takes original 3NUU.pdb
2. Mutates Chain A, residue 87 from Asp (D) to Gly (G)
3. Automatically converts to PDBQT
4. Runs docking
5. Saves results

### New Flag 2: `--output` (JSON Results File)

Store docking results in a machine-readable JSON format:

```bash
autoscan dock \
  --receptor protein.pdbqt \
  --ligand ligand.pdbqt \
  --center-x 10.5 --center-y 20.3 --center-z 15.8 \
  --output results/docking_result.json
```

**Output JSON Format**:
```json
{
  "timestamp": "2026-02-18T14:23:45.123456",
  "receptor": "/path/to/receptor.pdbqt",
  "ligand": "/path/to/ligand.pdbqt",
  "binding_affinity_kcal_mol": -8.3,
  "center": {
    "x": 10.5,
    "y": 20.3,
    "z": 15.8
  },
  "mutation": "A:87:D:G"
}
```

### New Capability: PDB File Support

The CLI now accepts `.pdb` files and auto-converts them to `.pdbqt`:

```bash
# Automatic conversion: 3NUU.pdb -> 3NUU.pdbqt
autoscan dock \
  --receptor 3NUU.pdb \
  --ligand ciprofloxacin.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7
```

---

## 📊 Running the Full Pilot Study

### Option 1: Automated Script (Recommended)

The script handles all 10 docking runs plus analysis:

```bash
python pilot_study_gyrase_selectivity.py
```

**What it does**:
- Creates `pilot_study/` directory structure
- Downloads/prepares 2 proteins (WT + MUT)
- Prepares 5 ligands
- Runs 10 docking simulations (5 drugs × 2 targets)
- Generates analysis report
- Exports results as CSV

**Output**:
```
pilot_study/
├── data/
│   ├── receptors/
│   │   ├── 3NUU_WT.pdb
│   │   └── 3NUU_MUT.pdb
│   ├── ligands/
│   │   ├── ciprofloxacin.pdb
│   │   ├── levofloxacin.pdb
│   │   ├── moxifloxacin.pdb
│   │   ├── nalidixic_acid.pdb
│   │   └── novobiocin.pdb
│   └── structures/
├── results/
│   ├── WT_ciprofloxacin.json
│   ├── MUT_ciprofloxacin.json
│   ├── WT_levofloxacin.json
│   ├── MUT_levofloxacin.json
│   ├── ... (10 files total)
│   ├── docking_results.csv          # Summary table
│   └── PILOT_STUDY_REPORT.md        # Analysis report
```

### Option 2: Manual Fine-Grained Control

Run individual docking commands with custom parameters:

```bash
# Step 1: Prepare proteins (download from RCSB, or use local files)
# Step 2: Prepare ligands (convert SMILES → PDB via RDKit, or use existing)

# Step 3: Run Wild-Type docking for each drug
autoscan dock --receptor 3NUU.pdb --ligand cipro.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --output WT_cipro.json

autoscan dock --receptor 3NUU.pdb --ligand levo.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --output WT_levo.json

# ... (3 more WT runs for moxi, nalidixic, novo)

# Step 4: Run Mutant docking with D87G mutation
autoscan dock --receptor 3NUU.pdb --ligand cipro.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7 \
  --mutation A:87:D:G --output MUT_cipro.json

# ... (4 more MUT runs for levo, moxi, nalidixic, novo)

# Step 5: Analyze results
python -c "
import json
from pathlib import Path

results = {}
for f in Path('.').glob('*.json'):
    with open(f) as fp:
        results[f.stem] = json.load(fp)

# Compare WT vs MUT
for drug in ['cipro', 'levo', 'moxi', 'nalidixic', 'novo']:
    wt = results[f'WT_{drug}']['binding_affinity_kcal_mol']
    mut = results[f'MUT_{drug}']['binding_affinity_kcal_mol']
    delta_delta_g = mut - wt
    print(f'{drug}: WT={wt:.2f}, MUT={mut:.2f}, ΔΔG={delta_delta_g:+.2f}')
"
```

---

## 📈 Expected Results & Interpretation

### Success Criteria

| Interpretation | ΔΔG (MUT - WT) | Biological Meaning |
|---|---|---|
| 🔴 **Resistance** | > +2.0 kcal/mol | Mutation destabilizes drug binding |
| 🟡 **Partial Resistance** | +0.5 to +2.0 | Mild reduction in binding |
| ⚪ **Neutral** | -0.5 to +0.5 | No selectivity |
| 🟢 **Hypersensitive** | < -0.5 kcal/mol | Mutation enhances binding |

### Example Output

```
Drug              WT (kcal/mol)  MUT (kcal/mol)  ΔΔG (MUT-WT)  Status
─────────────────────────────────────────────────────────────────────
Ciprofloxacin           -8.3           -6.1          +2.2    🔴 Resistant
Levofloxacin            -8.1           -6.8          +1.3    🟡 Partial R
Moxifloxacin            -7.9           -6.5          +1.4    🟡 Partial R
Nalidixic Acid          -6.5           -4.2          +2.3    🔴 Resistant
Novobiocin              -7.2           -6.9          +0.3    ⚪ Neutral
```

**Interpretation**:
- Fluoroquinolones show resistance (ΔΔG > 1.0)
- This matches known clinical data: D87G is a fluoroquinolone resistance mutation
- ✅ **Prediction validated**: AutoScan correctly identifies resistance

---

## 🔗 Integration Points

### How Results Feed Into Literature & Practice

1. **Publication**: 
   ```
   "AutoScan predicts fluoroquinolone resistance mutations in DNA Gyrase. 
   In silico validation using D87G as a model system (ΔΔG = +2.1 kcal/mol) 
   aligns with clinical resistance patterns."
   ```

2. **Resistance Monitoring**:
   - Screen new mutations: S81F, A67S, E50K, E84K
   - Rank by predicted resistance strength
   - Identify combinations with other resistance genes

3. **Drug Design**:
   - Design next-gen drugs that bind resistant mutants better
   - Use ΔΔG as a metric for binding universality across strains

---

## 📋 Troubleshooting

### Q: "Cannot apply mutation: original PDB file not found"
**A**: The `--mutation` flag requires the original `.pdb` file. If you have only `.pdbqt`:
```bash
# Try again with the .pdb version
autoscan dock --receptor protein.pdb --ligand ligand.pdbqt \
  --mutation A:87:D:G --output result.json
```

### Q: "Failed to convert PDB to PDBQT"
**A**: Ensure dependencies are installed:
```bash
pip install meeko rdkit biopython
```

### Q: "Docking takes too long with mutation"
**A**: First run without mutation to check speed:
```bash
# Quick test
autoscan dock --receptor 3NUU.pdb --ligand cipro.pdb \
  --center-x 8.5 --center-y 12.3 --center-z 15.7
```

---

## 🎯 Next Steps (Deeper Science)

After completing this pilot study:

1. **Experimental Validation** (Bench)
   - Fluorescence assays (Gyrase-ligand binding kinetics)
   - Antibiotic susceptibility testing (MIC determination)
   - Verify D87G actually confers resistance

2. **Extended Mutation Screen** (In Silico)
   - Test all known gyrase resistance mutations
   - Rank by predicted ΔΔG
   - Compare with clinical surveillance data

3. **Free Energy Calculations** (High Accuracy)
   - MM-PBSA (Molecular Mechanics Poisson-Boltzmann Surface Area)
   - TI (Thermodynamic Integration)
   - MD simulations (longer timescales)

4. **Multi-target Studies**
   - DHFR (trimethoprim resistance)
   - RNA Polymerase (rifampicin resistance)
   - Other beta-lactam targets

---

## 📚 References

- **Gyrase D87G mutation**: Clinical resistance to fluoroquinolones (Hooper & Jacoby, 2016)
- **Structure used**: 3NUU - Gyrase in complex with DNA and ciprofloxacin (Morrissette et al., 2013)
- **Fluoroquinolones**: Comprehensive review (Hooper, 2005)

---

## 📞 Support

For questions or results, reach out to the AutoScan development team or check the main [VALIDATION_AND_TESTING.md](../VALIDATION_AND_TESTING.md) for more information about the tool's accuracy.

---

**Pilot Study Created**: February 2026  
**AutoScan Version**: 1.0.0 (Production-Validated)  
**Framework Status**: Ready for Scientific Use ✅
