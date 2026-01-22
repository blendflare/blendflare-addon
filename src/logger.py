"""
Centralized logging utility for Blendflare addon.

All console output should go through this module to respect the user's
debug_console preference. By default, logging is disabled.
"""

import bpy


def is_debug_enabled() -> bool:
    """Check if debug console logging is enabled in addon preferences."""
    try:
        # Get addon preferences using the package name
        addon_prefs = bpy.context.preferences.addons.get(__package__)
        if addon_prefs and hasattr(addon_prefs, 'preferences'):
            return getattr(addon_prefs.preferences, 'debug_console', False)
    except Exception:
        pass
    return False


def log(message: str, prefix: str = "Blendflare") -> None:
    """
    Log a message to the console if debug logging is enabled.

    Args:
        message: The message to log
        prefix: The prefix to use (e.g., "Blendflare HDRI", "Blendflare Cache")
    """
    if is_debug_enabled():
        print(f"[{prefix}] {message}")


def log_info(message: str, prefix: str = "Blendflare") -> None:
    """Log an info message (alias for log)."""
    log(message, prefix)


def log_debug(message: str, prefix: str = "Blendflare") -> None:
    """Log a debug message."""
    log(message, prefix)


def log_warning(message: str, prefix: str = "Blendflare") -> None:
    """Log a warning message."""
    if is_debug_enabled():
        print(f"[{prefix}] WARNING: {message}")


def log_error(message: str, prefix: str = "Blendflare") -> None:
    """
    Log an error message. Errors are ALWAYS logged regardless of debug setting
    since they indicate problems that users should be aware of.

    Args:
        message: The error message to log
        prefix: The prefix to use
    """
    print(f"[{prefix}] ERROR: {message}")


# Module-specific loggers for convenience
class ModuleLogger:
    """A logger instance for a specific module with a fixed prefix."""

    def __init__(self, prefix: str):
        self.prefix = prefix

    def info(self, message: str) -> None:
        log_info(message, self.prefix)

    def debug(self, message: str) -> None:
        log_debug(message, self.prefix)

    def warning(self, message: str) -> None:
        log_warning(message, self.prefix)

    def error(self, message: str) -> None:
        log_error(message, self.prefix)

    def __call__(self, message: str) -> None:
        """Allow using logger(message) as shorthand for logger.info(message)."""
        self.info(message)


# Pre-configured loggers for common modules
cache_logger = ModuleLogger("Blendflare Cache")
asset_logger = ModuleLogger("Blendflare Asset")
material_logger = ModuleLogger("Blendflare Material")
hdri_logger = ModuleLogger("Blendflare HDRI")
scene_logger = ModuleLogger("Blendflare Scene")
model_logger = ModuleLogger("Blendflare Model")
sanitizer_logger = ModuleLogger("Blendflare Sanitizer")
toolbar_logger = ModuleLogger("Blendflare Toolbar")
panel_logger = ModuleLogger("Blendflare Panel")
toast_logger = ModuleLogger("Blendflare Toast")
widget_logger = ModuleLogger("Blendflare Widget")
download_logger = ModuleLogger("Blendflare")
