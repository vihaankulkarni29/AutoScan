"""
Test 3: Integrity Stress Test (Negative Testing / Fuzzing)

This test suite intentionally feeds garbage to the CLI to ensure
it fails gracefully with clean error messages instead of Python tracebacks.

Attack Vectors:
1. Ghost File: Providing a path that doesn't exist
2. Wrong Format: Providing a .txt file instead of .pdbqt
3. Zero State: Running with no arguments (or missing required args)
4. Physics Violation: Providing NaN coordinates
"""

import subprocess
import sys
from pathlib import Path

# --- CONFIG ---
STRESS_DATA_DIR = Path("tests/stress_data")
BAD_FILE = STRESS_DATA_DIR / "fake_structure.txt"
GHOST_FILE = STRESS_DATA_DIR / "ghost.pdbqt"


def setup_stress_data():
    """Create dummy test files."""
    STRESS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create a fake text file (wrong format)
    with open(BAD_FILE, "w") as f:
        f.write("This is not a protein structure. Just plain text.")
    
    print(f"✓ Created {BAD_FILE}")
    print(f"✓ Ghost file path ready (will not create): {GHOST_FILE}")


def run_cli(args):
    """
    Runs the autoscan CLI via subprocess using python -m.
    The dock command is the default, so no "dock" subcommand needed.
    Returns: (returncode, stdout, stderr)
    """
    # The Typer app makes 'dock' the default command
    cmd = [sys.executable, "-m", "autoscan.main"] + args
    print(f"\n  Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd="c:\\Users\\Vihaan\\Documents\\AutoDock")
    return result.returncode, result.stdout, result.stderr


# ============================================================================
# TEST CASES
# ============================================================================

def test_missing_file_handling():
    """
    Attack Vector: Ghost File
    Scenario: User provides a path that does not exist.
    Expected: Clean error message, no Python traceback.
    """
    print("\n" + "=" * 80)
    print("TEST 1: Missing File Handling (Ghost File)")
    print("=" * 80)
    
    returncode, stdout, stderr = run_cli([
        "--receptor", str(GHOST_FILE),
        "--ligand", str(BAD_FILE),
        "--center-x", "0", "--center-y", "0", "--center-z", "0"
    ])
    
    print(f"Return Code: {returncode}")
    print(f"STDERR:\n{stderr}")
    
    # Assertions
    try:
        assert returncode != 0, "Should fail with non-zero exit code"
        # Should contain user-friendly error, not python traceback
        assert "Traceback" not in stderr, "Should not contain Python traceback"
        assert (
            "does not exist" in stderr or 
            "not found" in stderr or 
            "cannot find" in stderr or
            "No such file" in stderr
        ), "Should mention file not found"
        print("✅ PASS: Caught missing file gracefully with clean error")
        return True
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        return False


def test_invalid_format_handling():
    """
    Attack Vector: Wrong Format
    Scenario: User provides a .txt file instead of .pdbqt.
    Expected: Error about file extension, not internal parsing error.
    """
    print("\n" + "=" * 80)
    print("TEST 2: Invalid Format Handling (Wrong Extension)")
    print("=" * 80)
    
    returncode, stdout, stderr = run_cli([
        "--receptor", str(BAD_FILE),
        "--ligand", str(BAD_FILE),
        "--center-x", "0", "--center-y", "0", "--center-z", "0"
    ])
    
    print(f"Return Code: {returncode}")
    print(f"STDERR:\n{stderr}")
    
    try:
        assert returncode != 0, "Should fail with non-zero exit code"
        assert "Traceback" not in stderr, "Should not contain Python traceback"
        assert (
            ".pdbqt" in stderr or 
            "extension" in stderr.lower() or 
            "format" in stderr.lower() or
            "PDBQT" in stderr
        ), "Should mention PDBQT file format requirement"
        print("✅ PASS: Caught invalid format gracefully")
        return True
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        return False


def test_missing_arguments():
    """
    Attack Vector: Zero State
    Scenario: Running dock command with no arguments.
    Expected: Typer displays help/usage, not a crash.
    """
    print("\n" + "=" * 80)
    print("TEST 3: Missing Arguments (Zero State)")
    print("=" * 80)
    
    returncode, stdout, stderr = run_cli([])
    
    print(f"Return Code: {returncode}")
    print(f"STDERR:\n{stderr}")
    print(f"STDOUT:\n{stdout}")
    
    try:
        assert returncode != 0, "Should fail with non-zero exit code"
        # Typer or argparse shows usage message (can be in stdout or stderr)
        combined = stdout + stderr
        assert (
            "required" in combined.lower() or 
            "usage" in combined.lower() or 
            "missing" in combined.lower() or
            "--help" in combined
        ), "Should show usage/help message for missing args"
        assert "Traceback" not in stderr, "Should not contain Python traceback"
        print("✅ PASS: Handled missing arguments gracefully")
        return True
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        return False


def test_nan_coordinates():
    """
    Attack Vector: Physics Violation
    Scenario: Providing NaN or invalid coordinate values.
    Expected: Should reject non-numeric input.
    """
    print("\n" + "=" * 80)
    print("TEST 4: NaN Coordinates (Physics Violation)")
    print("=" * 80)
    
    # Create a valid dummy receptor for this test
    dummy_receptor = STRESS_DATA_DIR / "dummy.pdbqt"
    dummy_receptor.write_text("ATOM      1  C   ALA A   1       0.000   0.000   0.000  1.00  0.00           C")
    
    returncode, stdout, stderr = run_cli([
        "--receptor", str(dummy_receptor),
        "--ligand", str(dummy_receptor),
        "--center-x", "nan",
        "--center-y", "0",
        "--center-z", "0"
    ])
    
    print(f"Return Code: {returncode}")
    print(f"STDERR:\n{stderr}")
    
    try:
        assert returncode != 0, "Should fail with non-zero exit code"
        # Typer validates types and shows error
        assert "Traceback" not in stderr, "Should not contain Python traceback"
        assert (
            "Invalid value" in stderr or
            "not a valid" in stderr or
            "float" in stderr.lower() or
            "number" in stderr.lower()
        ), "Should indicate invalid numeric input"
        print("✅ PASS: Rejected NaN coordinates gracefully")
        return True
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        return False


def test_both_files_missing():
    """
    Attack Vector: Multiple Failures
    Scenario: Both receptor and ligand files missing.
    Expected: Error on first check (receptor), clear message.
    """
    print("\n" + "=" * 80)
    print("TEST 5: Both Files Missing (Multiple Failures)")
    print("=" * 80)
    
    returncode, stdout, stderr = run_cli([
        "--receptor", str(STRESS_DATA_DIR / "missing_receptor.pdbqt"),
        "--ligand", str(STRESS_DATA_DIR / "missing_ligand.pdbqt"),
        "--center-x", "0", "--center-y", "0", "--center-z", "0"
    ])
    
    print(f"Return Code: {returncode}")
    print(f"STDERR:\n{stderr}")
    
    try:
        assert returncode != 0, "Should fail with non-zero exit code"
        assert "Traceback" not in stderr, "Should not contain Python traceback"
        assert (
            "does not exist" in stderr or 
            "not found" in stderr
        ), "Should mention missing file"
        print("✅ PASS: Caught multiple missing files gracefully")
        return True
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n" + "=" * 80)
    print("TEST SUITE 3: INTEGRITY STRESS TEST (NEGATIVE TESTING)")
    print("=" * 80)
    
    # Setup
    setup_stress_data()
    
    # Run tests
    results = []
    results.append(("Missing File Handling", test_missing_file_handling()))
    results.append(("Invalid Format Handling", test_invalid_format_handling()))
    results.append(("Missing Arguments", test_missing_arguments()))
    results.append(("NaN Coordinates", test_nan_coordinates()))
    results.append(("Both Files Missing", test_both_files_missing()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL INTEGRITY TESTS PASSED - Tool is robust!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - Validation needed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
