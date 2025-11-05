"""
Runtime Configuration
Global runtime settings that can be set via CLI arguments
"""

class RuntimeConfig:
    """Global runtime configuration"""

    # Set to True to skip all permission and security checks
    # WARNING: This should only be used for development/debugging
    skip_permissions: bool = False

    @classmethod
    def set_skip_permissions(cls, value: bool):
        """Enable or disable permission skipping"""
        cls.skip_permissions = value

    @classmethod
    def should_skip_permissions(cls) -> bool:
        """Check if permissions should be skipped"""
        return cls.skip_permissions
