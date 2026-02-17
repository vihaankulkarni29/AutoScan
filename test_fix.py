#!/usr/bin/env python
"""Test the dependency check fix."""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from autoscan.utils.dependency_check import (
    _in_conda_environment,
    _check_obabel,
    _check_pdbfixer,
    ensure_dependencies,
)

print("=" * 60)
print("Test 1: Check if in conda environment")
print("=" * 60)
in_conda = _in_conda_environment()
print(f"In conda environment: {in_conda}")
print(f"CONDA_PREFIX: {os.environ.get('CONDA_PREFIX', 'NOT SET')}")
print()

print("=" * 60)
print("Test 2: Check OpenBabel")
print("=" * 60)
obabel_issues = _check_obabel()
if obabel_issues:
    print("❌ OpenBabel issues:")
    for issue in obabel_issues:
        print(f"  - {issue}")
else:
    print("✅ OpenBabel check PASSED")
print()

print("=" * 60)
print("Test 3: Check PDBFixer")
print("=" * 60)
pdbfixer_issues = _check_pdbfixer()
if pdbfixer_issues:
    print("❌ PDBFixer issues:")
    for issue in pdbfixer_issues:
        print(f"  - {issue}")
else:
    print("✅ PDBFixer check PASSED")
print()

print("=" * 60)
print("Test 4: Ensure dependencies (full check)")
print("=" * 60)
try:
    ensure_dependencies()
    print("✅ All dependencies: PASSED")
except RuntimeError as e:
    print(f"❌ Error: {e}")
