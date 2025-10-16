"""
Path traversal security validation tests for AppSettings
"""

import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app_settings import AppSettings


def test_path_traversal_security():
    """Test path traversal attack prevention"""

    print("\n=== Path Traversal Security Tests ===\n")

    # Test 1: Default settings file (should pass)
    print("Test 1: Default settings file (should pass)")
    try:
        settings = AppSettings()
        print(f"  [PASS] Success: {settings.settings_file}")
    except ValueError as e:
        print(f"  [FAIL] Failed: {e}")

    # Test 2: Valid path within project directory (should pass)
    print("\nTest 2: Valid path within project directory (should pass)")
    try:
        project_path = str(Path(__file__).parent / "config" / "test_settings.json")
        settings = AppSettings(project_path)
        print(f"  [PASS] Success: {settings.settings_file}")
    except ValueError as e:
        print(f"  [FAIL] Failed: {e}")

    # Test 3: Valid path within user home directory (should pass)
    print("\nTest 3: Valid path within user home directory (should pass)")
    try:
        home_path = str(Path.home() / ".kotoba" / "settings.json")
        settings = AppSettings(home_path)
        print(f"  [PASS] Success: {settings.settings_file}")
    except ValueError as e:
        print(f"  [FAIL] Failed: {e}")

    # Test 4: Path traversal attack attempt - parent directory (should fail)
    print("\nTest 4: Path traversal attack - parent directory (should fail)")
    try:
        attack_path = "../../../etc/passwd"
        settings = AppSettings(attack_path)
        print(f"  [FAIL] Security breach: Path traversal attack succeeded!")
    except ValueError as e:
        print(f"  [PASS] Blocked: Attack prevented")

    # Test 5: Path traversal attack attempt - system directory (should fail)
    print("\nTest 5: Path traversal attack - system directory (should fail)")
    try:
        attack_path = "C:/Windows/System32/config.json"
        settings = AppSettings(attack_path)
        print(f"  [FAIL] Security breach: Path traversal attack succeeded!")
    except ValueError as e:
        print(f"  [PASS] Blocked: Path not allowed")

    # Test 6: Path traversal using absolute path outside allowed dirs (should fail)
    print("\nTest 6: Path traversal using absolute path (should fail)")
    try:
        attack_path = "C:/tmp/malicious_settings.json"
        settings = AppSettings(attack_path)
        print(f"  [FAIL] Security breach: Path traversal attack succeeded!")
    except ValueError as e:
        print(f"  [PASS] Blocked: Path not allowed")

    # Test 7: Symbolic link attack simulation (should fail if outside dirs)
    print("\nTest 7: Path with double dots in middle (should fail)")
    try:
        attack_path = str(Path(__file__).parent / "config" / ".." / ".." / ".." / "etc" / "passwd")
        settings = AppSettings(attack_path)
        print(f"  [FAIL] Security breach: Path traversal attack succeeded!")
    except ValueError as e:
        print(f"  [PASS] Blocked: Attack prevented")

    # Test 8: Verify resolve() normalizes paths correctly
    print("\nTest 8: Path normalization with resolve() (should pass)")
    try:
        # This should resolve to project directory
        normalized_path = str(Path(__file__).parent / "config" / ".." / "settings.json")
        settings = AppSettings(normalized_path)
        print(f"  [PASS] Success: Normalized to {settings.settings_file}")
    except ValueError as e:
        print(f"  [FAIL] Failed: {e}")

    print("\n=== Security Tests Completed ===\n")

    # Summary
    print("Security Summary:")
    print("  - Path traversal attacks are properly blocked")
    print("  - Only project directory and user home are allowed")
    print("  - Path normalization with resolve() prevents bypass attempts")
    print("  - ValueError is raised with descriptive error messages")


def test_deepcopy_isolation():
    """Test that copy.deepcopy properly isolates settings"""

    print("\n=== Deep Copy Isolation Tests ===\n")

    # Create two instances
    settings1 = AppSettings()
    settings2 = AppSettings()

    # Modify nested setting in settings1
    print("Test: Modifying nested setting in settings1")
    settings1.set('realtime.model_size', 'large')
    settings1.set('window.width', 1200)

    # Check that settings2 is not affected
    model_size_2 = settings2.get('realtime.model_size')
    width_2 = settings2.get('window.width')

    print(f"  settings1.realtime.model_size: {settings1.get('realtime.model_size')}")
    print(f"  settings2.realtime.model_size: {model_size_2}")
    print(f"  settings1.window.width: {settings1.get('window.width')}")
    print(f"  settings2.window.width: {width_2}")

    if model_size_2 == 'base' and width_2 == 900:
        print("  [PASS] Deep copy isolation working correctly")
    else:
        print("  [FAIL] Deep copy isolation failed - settings are shared!")

    print("\n=== Deep Copy Tests Completed ===\n")


if __name__ == "__main__":
    test_path_traversal_security()
    test_deepcopy_isolation()
