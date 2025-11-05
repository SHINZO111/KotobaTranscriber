"""
Input validation module
Provides validation functions for file paths, text, and other inputs
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union
from runtime_config import RuntimeConfig

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised for validation errors"""
    pass


class Validator:
    """Static validation methods for various input types"""

    @staticmethod
    def validate_file_path(
        file_path: Union[str, Path],
        must_exist: bool = False,
        must_be_file: bool = False,
        must_be_dir: bool = False,
        allowed_extensions: Optional[list] = None
    ) -> Path:
        """
        Validate a file path

        Args:
            file_path: Path to validate
            must_exist: If True, path must exist
            must_be_file: If True, path must be a file
            must_be_dir: If True, path must be a directory
            allowed_extensions: List of allowed file extensions (e.g., ['.wav', '.mp3'])

        Returns:
            Path: Validated path object

        Raises:
            ValidationError: If validation fails
            PermissionError: If no permission to access the file
        """
        # Skip validation if flag is set
        if RuntimeConfig.should_skip_permissions():
            logger.warning(f"⚠️  Skipping file path validation for: {file_path}")
            return Path(file_path)

        try:
            path_obj = Path(file_path).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid file path: {file_path}") from e

        # Check if path exists
        if must_exist and not path_obj.exists():
            raise ValidationError(f"Path does not exist: {path_obj}")

        # Check if it's a file
        if must_be_file and path_obj.exists() and not path_obj.is_file():
            raise ValidationError(f"Path is not a file: {path_obj}")

        # Check if it's a directory
        if must_be_dir and path_obj.exists() and not path_obj.is_dir():
            raise ValidationError(f"Path is not a directory: {path_obj}")

        # Check file extension
        if allowed_extensions and path_obj.suffix.lower() not in allowed_extensions:
            raise ValidationError(
                f"Invalid file extension: {path_obj.suffix}. "
                f"Allowed: {', '.join(allowed_extensions)}"
            )

        # Check permissions
        if must_exist:
            try:
                # Try to access the file
                if path_obj.is_file():
                    with open(path_obj, 'rb'):
                        pass
                elif path_obj.is_dir():
                    os.listdir(path_obj)
            except PermissionError as e:
                raise PermissionError(f"No permission to access: {path_obj}") from e

        return path_obj

    @staticmethod
    def validate_text_length(
        text: str,
        min_length: int = 0,
        max_length: int = 1000000
    ) -> str:
        """
        Validate text length

        Args:
            text: Text to validate
            min_length: Minimum allowed length
            max_length: Maximum allowed length

        Returns:
            str: Validated text

        Raises:
            ValidationError: If validation fails
        """
        # Skip validation if flag is set (for length checks, we still validate basic type)
        if RuntimeConfig.should_skip_permissions():
            if not isinstance(text, str):
                raise ValidationError(f"Text must be a string, got {type(text)}")
            return text

        if not isinstance(text, str):
            raise ValidationError(f"Text must be a string, got {type(text)}")

        text_len = len(text)
        if text_len < min_length:
            raise ValidationError(
                f"Text too short: {text_len} < {min_length}"
            )
        if text_len > max_length:
            raise ValidationError(
                f"Text too long: {text_len} > {max_length}"
            )

        return text

    @staticmethod
    def validate_positive_integer(
        value: Union[int, str],
        min_value: int = 1,
        max_value: Optional[int] = None
    ) -> int:
        """
        Validate a positive integer

        Args:
            value: Value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value (None for no limit)

        Returns:
            int: Validated integer

        Raises:
            ValidationError: If validation fails
        """
        # Skip validation if flag is set (still validate basic type conversion)
        if RuntimeConfig.should_skip_permissions():
            try:
                return int(value)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid integer: {value}") from e

        try:
            int_value = int(value)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid integer: {value}") from e

        if int_value < min_value:
            raise ValidationError(
                f"Value too small: {int_value} < {min_value}"
            )
        if max_value is not None and int_value > max_value:
            raise ValidationError(
                f"Value too large: {int_value} > {max_value}"
            )

        return int_value

    @staticmethod
    def validate_model_name(
        model_name: str,
        model_type: str = "whisper"
    ) -> str:
        """
        Validate a model name

        Args:
            model_name: Model name to validate
            model_type: Type of model (e.g., "whisper")

        Returns:
            str: Validated model name

        Raises:
            ValidationError: If validation fails
        """
        # Skip validation if flag is set
        if RuntimeConfig.should_skip_permissions():
            logger.warning(f"⚠️  Skipping model name validation for: {model_name}")
            return model_name

        if not model_name or not isinstance(model_name, str):
            raise ValidationError(f"Invalid model name: {model_name}")

        # Whitelist of allowed model names for security
        if model_type == "whisper":
            allowed_models = [
                "kotoba-tech/kotoba-whisper-v2.2",
                "kotoba-tech/kotoba-whisper-v2.1",
                "kotoba-tech/kotoba-whisper-v2.0",
                "openai/whisper-large-v3",
                "openai/whisper-large-v2",
                "openai/whisper-medium",
                "openai/whisper-small",
                "openai/whisper-base",
                "openai/whisper-tiny"
            ]
            if model_name not in allowed_models:
                raise ValidationError(
                    f"Model name not in allowed list: {model_name}. "
                    f"Allowed: {', '.join(allowed_models)}"
                )

        return model_name

    @staticmethod
    def validate_chunk_length(
        chunk_length_s: Union[int, float]
    ) -> float:
        """
        Validate chunk length for audio processing

        Args:
            chunk_length_s: Chunk length in seconds

        Returns:
            float: Validated chunk length

        Raises:
            ValidationError: If validation fails
        """
        # Skip validation if flag is set (still validate basic type conversion)
        if RuntimeConfig.should_skip_permissions():
            try:
                return float(chunk_length_s)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid chunk length: {chunk_length_s}") from e

        try:
            chunk_float = float(chunk_length_s)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid chunk length: {chunk_length_s}") from e

        # Reasonable limits for chunk length
        if chunk_float <= 0:
            raise ValidationError(f"Chunk length must be positive: {chunk_float}")
        if chunk_float > 300:  # 5 minutes max
            raise ValidationError(f"Chunk length too large: {chunk_float} > 300")

        return chunk_float
