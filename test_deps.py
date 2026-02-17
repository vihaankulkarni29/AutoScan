#!/usr/bin/env python
"""Quick test of dependency check."""
from autoscan.utils.dependency_check import ensure_dependencies
try:
    ensure_dependencies()
    print('✅ Dependency check PASSED')
except RuntimeError as e:
    print(f'❌ Dependency check FAILED: {e}')
