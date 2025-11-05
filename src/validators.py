"""
Input validation module for KotobaTranscriber.
Provides path validation and security checks with optional permission bypass.
"""

import os
import pathlib
from typing import List, Optional


class ValidationError(Exception):
    """Exception raised when validation fails."""
    pass


class Validator:
    """Validator class for input validation and security checks."""

    # Global flag to skip permission checks (dangerous!)
    _skip_permissions = False

    @classmethod
    def set_skip_permissions(cls, skip: bool):
        """
        Set whether to skip permission checks.

        WARNING: This should only be used in development or when the user
        explicitly accepts the security risks.

        Args:
            skip: If True, skip permission validation checks
        """
        cls._skip_permissions = skip

    @classmethod
    def validate_file_path(
        cls,
        file_path: str,
        allowed_extensions: Optional[List[str]] = None,
        must_exist: bool = True,
        check_permissions: bool = True
    ) -> str:
        """
        Validate a file path with security checks.

        Args:
            file_path: Path to validate
            allowed_extensions: List of allowed extensions (e.g., [".txt", ".wav"])
            must_exist: If True, file must exist
            check_permissions: If True, check read/write permissions

        Returns:
            Validated absolute path

        Raises:
            ValidationError: If validation fails
        """
        if not file_path:
            raise ValidationError("File path cannot be empty")

        # Convert to absolute path and resolve symlinks
        try:
            resolved_path = os.path.realpath(file_path)
        except (OSError, ValueError) as e:
            raise ValidationError(f"Invalid file path: {e}")

        # Check for path traversal attempts
        if ".." in file_path:
            # Allow it if the resolved path is still valid
            pass

        # Check extension if specified
        if allowed_extensions:
            ext = os.path.splitext(resolved_path)[1].lower()
            if ext not in [e.lower() for e in allowed_extensions]:
                raise ValidationError(
                    f"File extension '{ext}' not allowed. "
                    f"Allowed extensions: {', '.join(allowed_extensions)}"
                )

        # Check if file exists (if required)
        if must_exist and not os.path.exists(resolved_path):
            raise ValidationError(f"File does not exist: {resolved_path}")

        # Check permissions (unless skipped)
        if check_permissions and not cls._skip_permissions:
            if must_exist:
                # For existing files, check read permission
                if not os.access(resolved_path, os.R_OK):
                    raise ValidationError(
                        f"No read permission for file: {resolved_path}"
                    )
            else:
                # For new files, check write permission in parent directory
                parent_dir = os.path.dirname(resolved_path)
                if parent_dir and os.path.exists(parent_dir):
                    if not os.access(parent_dir, os.W_OK):
                        raise ValidationError(
                            f"No write permission in directory: {parent_dir}"
                        )

        return resolved_path

    @classmethod
    def validate_directory_path(
        cls,
        dir_path: str,
        must_exist: bool = True,
        check_permissions: bool = True
    ) -> str:
        """
        Validate a directory path with security checks.

        Args:
            dir_path: Directory path to validate
            must_exist: If True, directory must exist
            check_permissions: If True, check read/write permissions

        Returns:
            Validated absolute directory path

        Raises:
            ValidationError: If validation fails
        """
        if not dir_path:
            raise ValidationError("Directory path cannot be empty")

        # Convert to absolute path and resolve symlinks
        try:
            resolved_path = os.path.realpath(dir_path)
        except (OSError, ValueError) as e:
            raise ValidationError(f"Invalid directory path: {e}")

        # Check if directory exists (if required)
        if must_exist:
            if not os.path.exists(resolved_path):
                raise ValidationError(f"Directory does not exist: {resolved_path}")
            if not os.path.isdir(resolved_path):
                raise ValidationError(f"Path is not a directory: {resolved_path}")

        # Check permissions (unless skipped)
        if check_permissions and not cls._skip_permissions and must_exist:
            if not os.access(resolved_path, os.R_OK | os.X_OK):
                raise ValidationError(
                    f"No read/execute permission for directory: {resolved_path}"
                )

        return resolved_path

    @classmethod
    def is_safe_path(cls, base_dir: str, target_path: str) -> bool:
        """
        Check if target_path is within base_dir (no path traversal).

        Args:
            base_dir: Base directory path
            target_path: Target path to check

        Returns:
            True if target_path is within base_dir, False otherwise
        """
        try:
            base = pathlib.Path(base_dir).resolve()
            target = pathlib.Path(target_path).resolve()
            return target.is_relative_to(base)
        except (ValueError, RuntimeError):
            return False
