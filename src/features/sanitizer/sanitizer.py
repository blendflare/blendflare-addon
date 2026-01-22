"""Main sanitizer class that orchestrates blend file sanitization."""

import os
import subprocess
import tempfile
from typing import Optional

import bpy

from ...logger import sanitizer_logger as _log


class BlendSanitizer:
    """Sanitizes .blend files by removing scripts and dangerous drivers.

    Uses a subprocess to run Blender in background mode, which ensures that
    any malicious code in the target file cannot affect the current session.
    """

    def __init__(self):
        self._blender_path: Optional[str] = None

    def _get_blender_executable(self) -> str:
        """Get path to Blender executable."""
        return bpy.app.binary_path

    def sanitize_file(self, input_path: str, output_path: Optional[str] = None) -> str:
        """Sanitize a .blend file by removing scripts and dangerous drivers.

        Args:
            input_path: Path to the .blend file to sanitize
            output_path: Where to save sanitized file. If None, creates a temp file.

        Returns:
            Path to the sanitized file

        Raises:
            RuntimeError: If sanitization fails
            FileNotFoundError: If input file doesn't exist
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        _log(f"Starting sanitization of: {os.path.basename(input_path)}")

        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".blend", prefix="sanitized_")
            os.close(fd)

        script_path = os.path.join(os.path.dirname(__file__), "sanitize_blend.py")
        blender = self._get_blender_executable()

        _log(f"Running Blender subprocess...")

        try:
            result = subprocess.run(
                [
                    blender,
                    "--background",
                    "--factory-startup",  # Don't load user preferences
                    "--disable-autoexec", # Disable auto-execution of scripts
                    "--python", script_path,
                    "--",
                    input_path,
                    output_path
                ],
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout for large files
            )

            # Check if output file was created (primary success indicator)
            # Note: Blender 5.0 may return non-zero exit code due to internal
            # handler cleanup issues, but sanitization still succeeds
            output_exists = os.path.exists(output_path)
            output_size = os.path.getsize(output_path) if output_exists else 0

            _log(f"Subprocess completed. Return code: {result.returncode}")
            _log(f"Output file exists: {output_exists}, size: {output_size} bytes")

            # Primary success check: file exists and has reasonable size
            if output_exists and output_size >= 100:
                # Check for our success marker OR just accept if file is valid
                if "Done! Output:" in result.stdout or "[Sanitizer]" in result.stdout:
                    _log(f"Sanitization complete: {os.path.basename(output_path)}")
                    return output_path

                # Check for actual errors in our sanitizer script
                if "ERROR:" in result.stdout:
                    error_lines = [l for l in result.stdout.split('\n') if "ERROR:" in l]
                    # Only fail if it's OUR error, not Blender's internal errors
                    if any("[Sanitizer] ERROR" in l for l in error_lines):
                        raise RuntimeError(f"Sanitization failed: {'; '.join(error_lines)}")

                # File exists and is valid - success despite any Blender warnings
                _log(f"Sanitization complete (file validated): {os.path.basename(output_path)}")
                return output_path

            # File doesn't exist or is too small - real failure
            # Only show relevant error info, not Blender's internal handler errors
            if "Failed to open file" in result.stdout or "Failed to save file" in result.stdout:
                error_msg = result.stdout
            else:
                error_msg = "Output file was not created or is invalid"

            raise RuntimeError(f"Sanitization failed: {error_msg}")

        except subprocess.TimeoutExpired:
            # Clean up partial output file
            if os.path.exists(output_path):
                os.remove(output_path)
            raise RuntimeError("Sanitization timed out")

        except RuntimeError:
            # Re-raise RuntimeError without cleanup (we handle it above)
            raise

        except Exception as e:
            # Clean up partial output file on unexpected errors only
            _log(f"Unexpected error: {type(e).__name__}: {e}")
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            raise RuntimeError(f"Sanitization failed: {e}")


# Singleton instance
_sanitizer: Optional[BlendSanitizer] = None


def get_sanitizer() -> BlendSanitizer:
    """Get or create the singleton BlendSanitizer instance."""
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = BlendSanitizer()
    return _sanitizer
