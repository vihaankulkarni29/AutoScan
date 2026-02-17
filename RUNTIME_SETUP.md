# AutoScan Runtime Environment Setup

## Overview

AutoScan requires a **Zero-Trust Dependency Environment** with strict version pins to ensure reproducibility and correctness. We provide a pre-configured conda environment that users can activate to run AutoScan without manual dependency management.

## Prerequisites

1. **Conda/Miniconda** installed and on PATH.
   - Download from: https://docs.conda.io/projects/miniconda/en/latest/
   - Verify: `conda --version`

2. **AutoScan repository** cloned locally.
   ```bash
   git clone https://github.com/vihaankulkarni29/AutoScan.git
   cd AutoScan
   ```

## Quick Start (Recommended)

### Step 1: Create the Runtime Environment

Run this command to provision the `autoscan-runtime` environment with all dependencies pre-pinned:

```bash
conda create -y -n autoscan-runtime -c conda-forge \
  python=3.10 \
  openmm==8.0.0 \
  numpy==1.24.3 \
  biopython>=1.81 \
  scipy>=1.10 \
  pandas>=2.0 \
  typer>=0.9.0 \
  mdtraj>=1.9.9 \
  pyyaml>=6.0 \
  meeko>=0.5.0 \
  rdkit>=2023.9.1 \
  gemmi>=0.6.0 \
  pdbfixer>=1.8 \
  openbabel>=3.1.1
```

### Step 2: Download AutoDock Vina Binary

```bash
cd AutoScan
python setup_env.py
```

This downloads Vina 1.2.7+ into `tools/vina.exe` (Windows) or `tools/vina` (Linux/Mac).

### Step 3: Activate and Verify

```bash
conda activate autoscan-runtime
set CONDA_EXE=C:\path\to\conda.exe  # Windows
# export CONDA_EXE=/path/to/conda  # Linux/Mac
python -c "from autoscan.utils.dependency_check import ensure_dependencies; ensure_dependencies(); print('✅ All dependencies OK')"
```

If you see `✅ All dependencies OK`, you're ready to run AutoScan.

---

## Strict Dependency Manifest

| Dependency | Version | Purpose |
|---|---|---|
| **Python** | 3.10 | Base runtime |
| **openmm** | 8.0.0 | Molecular Dynamics engine (CUDA/CPU) |
| **numpy** | 1.24.3 | Matrix math for RMSD calculations |
| **biopython** | ≥1.81 | PDB parsing and structure manipulation |
| **scipy** | ≥1.10 | Spatial transforms (Kabsch algorithm) |
| **pandas** | ≥2.0 | Dataframe handling for results |
| **typer** | ≥0.9.0 | CLI interface |
| **mdtraj** | ≥1.9.9 | Trajectory analysis and RMSD |
| **pyyaml** | ≥6.0 | YAML config parsing |
| **meeko** | ≥0.5.0 | Ligand preparation |
| **rdkit** | ≥2023.9.1 | Chemistry toolkit |
| **gemmi** | ≥0.6.0 | Crystallographic utils |
| **pdbfixer** | ≥1.8 | Structure repair |
| **openbabel** | ≥3.1.1 | PDB ↔ PDBQT conversion |
| **AutoDock Vina** | 1.2.7+ | Docking engine (binary in `tools/`) |

---

## Running Tests

Once the environment is active, verify the setup with:

```bash
conda activate autoscan-runtime

# Structural validation test
pytest tests/test_structural.py -v

# Phase 1 benchmark (10 targets)
python tests/benchmark_phase1.py

# Phase 1.1 fixed benchmark
python tests/benchmark_phase1_fixed.py
```

---

## Troubleshooting

### "Conda not found"

Ensure conda is on PATH:

```bash
# Windows
where conda

# Linux/Mac
which conda
```

If not found, install Miniconda and add it to PATH.

### "OpenBabel/PDBFixer not found"

These are installed in the conda env. Ensure you've activated it:

```bash
conda activate autoscan-runtime
```

### "Vina binary missing"

Run:

```bash
python setup_env.py
```

### "Dependency check fails"

The `ensure_dependencies()` function performs zero-trust checks. To auto-repair:

```python
from autoscan.utils import build_dependencies
build_dependencies()
```

---

## Environment Details

- **OS**: Windows, Linux, macOS
- **Python**: 3.10 (pinned for openmm compatibility)
- **CUDA**: Included in openmm build; falls back to CPU if unavailable
- **Package Manager**: Conda-forge
- **Installation Size**: ~945 MB (including CUDA toolkit)

---

## Publishing Guide for Users

To distribute AutoScan to end-users:

1. **Provide the setup commands** above in your documentation/README.
2. **Environment name**: `autoscan-runtime` (standard across users)
3. **Activation**: `conda activate autoscan-runtime`
4. **First run**: `python setup_env.py` then run tests to validate.

Users should never need to manually manage dependencies—zero-trust checks will catch any issues.

---

**Last Updated**: February 17, 2026  
**Status**: Production Ready
