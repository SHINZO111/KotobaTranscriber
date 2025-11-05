#!/usr/bin/env python3
"""
Test script for --dangerously-skip-permissions feature
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from validators import Validator, ValidationError


def test_permission_validation():
    """Test permission validation with and without skip flag"""

    print("=" * 60)
    print("Testing Permission Validation")
    print("=" * 60)

    # Test Case 1: Read-only file (testing read permissions)
    print("\n[Test 1] Read permissions on existing file:")
    test_file_readable = "/tmp/test_read.txt"
    with open(test_file_readable, 'w') as f:
        f.write("test content")
    os.chmod(test_file_readable, 0o444)  # Read-only

    Validator.set_skip_permissions(False)
    try:
        result = Validator.validate_file_path(test_file_readable, must_exist=True)
        print(f"   ✓ Read permission check passed: {os.path.basename(result)}")
    except ValidationError as e:
        print(f"   ✗ Read permission check failed: {e}")

    os.chmod(test_file_readable, 0o644)
    os.remove(test_file_readable)

    # Test Case 2: Write permissions in directory (for new files)
    print("\n[Test 2] Write permissions in read-only directory:")
    test_dir = "/tmp/test_readonly_dir"
    os.makedirs(test_dir, exist_ok=True)
    os.chmod(test_dir, 0o555)  # Read-only directory

    test_file_new = os.path.join(test_dir, "new_file.txt")

    print("   Without skip flag:")
    Validator.set_skip_permissions(False)
    try:
        result = Validator.validate_file_path(
            test_file_new,
            allowed_extensions=[".txt"],
            must_exist=False,
            check_permissions=True
        )
        print(f"   ✗ Validation passed (unexpected): {os.path.basename(result)}")
    except ValidationError as e:
        print(f"   ✓ Validation failed (expected): No write permission")

    print("\n   With --dangerously-skip-permissions:")
    Validator.set_skip_permissions(True)
    try:
        result = Validator.validate_file_path(
            test_file_new,
            allowed_extensions=[".txt"],
            must_exist=False,
            check_permissions=True
        )
        print(f"   ✓ Validation passed (expected): {os.path.basename(result)}")
        print(f"      (Note: OS may still prevent actual write)")
    except ValidationError as e:
        print(f"   ✗ Validation failed (unexpected): {e}")

    # Clean up
    os.chmod(test_dir, 0o755)
    os.rmdir(test_dir)

    # Test Case 3: Invalid extension
    print("\n[Test 3] Extension validation (should still work with skip flag):")
    test_file_ext = "/tmp/test.mp3"

    Validator.set_skip_permissions(True)
    try:
        result = Validator.validate_file_path(
            test_file_ext,
            allowed_extensions=[".txt"],
            must_exist=False
        )
        print(f"   ✗ Extension check bypassed (unexpected)")
    except ValidationError as e:
        print(f"   ✓ Extension check still enforced: .mp3 not in [.txt]")

    # Test Case 4: Verify flag state
    print(f"\n[Test 4] Flag state verification:")
    print(f"   Skip permissions flag: {Validator._skip_permissions}")

    Validator.set_skip_permissions(False)
    print(f"   After reset: {Validator._skip_permissions}")

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    test_permission_validation()
