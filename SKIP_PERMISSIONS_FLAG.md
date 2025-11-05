# --dangerously-skip-permissions Flag

## Overview

The `--dangerously-skip-permissions` flag allows bypassing file permission validation checks in KotobaTranscriber. This is intended for development and testing purposes only.

## Usage

```bash
python src/main.py --dangerously-skip-permissions
```

## What It Does

When this flag is enabled:

1. **Skips permission validation** - The `Validator` class will not check read/write permissions before attempting file operations
2. **Logs a warning** - A clear warning is displayed in the logs indicating that permission checks are disabled
3. **Maintains other security checks** - File extension validation, path traversal protection, and other security measures remain active

## What It Does NOT Do

- Does **NOT** bypass OS-level permissions (the OS may still deny access)
- Does **NOT** disable extension validation
- Does **NOT** disable path traversal protection
- Does **NOT** grant elevated privileges

## Security Implications

⚠️ **WARNING**: This flag should ONLY be used in development/testing environments.

When enabled, the application will:
- Attempt file operations that would normally be blocked by permission checks
- Potentially expose the application to permission-related errors at runtime
- Reduce security by not pre-validating file access rights

## Implementation Details

### Files Modified

1. **src/validators.py** (NEW)
   - `Validator` class with `set_skip_permissions()` method
   - Global `_skip_permissions` flag
   - Permission checks in `validate_file_path()` respect the flag

2. **src/config_manager.py** (NEW)
   - Configuration management system
   - Supports YAML configuration files

3. **src/main.py** (MODIFIED)
   - Added `argparse` for CLI argument parsing
   - Added `--dangerously-skip-permissions` flag
   - Calls `Validator.set_skip_permissions(True)` when flag is set
   - Displays warning when flag is enabled

### Code Flow

```python
# In main.py
parser = argparse.ArgumentParser()
parser.add_argument('--dangerously-skip-permissions', action='store_true')
args = parser.parse_args()

if args.dangerously_skip_permissions:
    Validator.set_skip_permissions(True)

# Later in code
try:
    validated_path = Validator.validate_file_path(
        output_file,
        allowed_extensions=[".txt"],
        must_exist=False
    )
    # If skip_permissions is True, permission checks are skipped
except ValidationError as e:
    # Handle validation errors
```

## Testing

Run the test script to verify functionality:

```bash
python test_skip_permissions.py
```

Expected output:
- Test 1: Read permissions work normally
- Test 2: Skip flag allows validation in read-only directories
- Test 3: Extension checks still enforced
- Test 4: Flag state can be toggled

## Use Cases

### Valid Use Cases
- Development environments where file permissions are restrictive
- Testing error handling for permission-related issues
- Debugging file access problems
- Automated testing in containerized environments

### Invalid Use Cases
- Production deployments
- User-facing installations
- Any security-sensitive context
- As a workaround for proper permission configuration

## Related Files

- `src/validators.py` - Validator implementation
- `src/config_manager.py` - Configuration management
- `src/main.py` - Main application entry point
- `test_skip_permissions.py` - Test script

## Version

Added in: KotobaTranscriber v2.1.0
Branch: claude/skip-permissions-flag-011CUpaArtbAKXNTQbcxNc6B
