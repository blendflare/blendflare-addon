import os
import tempfile

import bpy
from bpy.types import AddonPreferences
from bpy.props import BoolProperty, StringProperty


CACHE_FOLDER_NAME = "blendflare"


def _get_default_cache_path() -> str:
    """Get default cache path in system temp directory."""
    return os.path.join(tempfile.gettempdir(), CACHE_FOLDER_NAME)


class BlendflareAddonPreferences(AddonPreferences):
    """Global addon preferences for Blendflare."""
    # When defined inside a submodule of a package, use __package__ as bl_idname
    # so Blender associates these preferences with the add-on package.
    bl_idname = __package__

    show_blendflare_header: BoolProperty(
        name="Show Blendflare Header",
        description="Toggle between Blendflare Header and Standard/BlenderKit Header",
        default=False,
    )

    blendflare_nickname: StringProperty(
        name="Blendflare Nickname",
        description="Your Blendflare nickname for filtering your assets",
        default="",
    )

    blendflare_api_key: StringProperty(
        name="Blendflare API Key",
        description="Your Blendflare API key for accessing blendflare services",
        subtype='PASSWORD',
        default="",
    )

    blendflare_cache_path: StringProperty(
        name="Cache Directory",
        description="Base directory for Blendflare cache (a 'blendflare' folder will be created inside)",
        subtype='DIR_PATH',
        default="",
    )

    debug_console: BoolProperty(
        name="Debug Console",
        description="Enable verbose logging to Blender's console for debugging purposes",
        default=False,
    )

    def get_cache_path(self) -> str:
        """Get the effective cache path, always inside a 'blendflare' subfolder.

        If user sets path to 'F:/mycache/', actual cache will be 'F:/mycache/blendflare/'
        This prevents cluttering the user's selected directory with multiple folders.
        """
        if self.blendflare_cache_path and os.path.isabs(self.blendflare_cache_path):
            base_path = self.blendflare_cache_path.rstrip(os.sep).rstrip('/')
            # Always add 'blendflare' subfolder unless it already ends with it
            if not base_path.lower().endswith(CACHE_FOLDER_NAME):
                return os.path.join(base_path, CACHE_FOLDER_NAME)
            return base_path
        return _get_default_cache_path()

    def draw(self, context):
        layout = self.layout

        # API Settings
        box = layout.box()
        box.label(text="API Settings", icon='WORLD')
        box.prop(self, "blendflare_api_key")
        box.prop(self, "blendflare_nickname")

        # Cache Settings
        box = layout.box()
        box.label(text="Cache Settings", icon='FILE_FOLDER')
        box.prop(self, "blendflare_cache_path")
        # Show effective path
        effective_path = self.get_cache_path()
        box.label(text=f"Cache location: {effective_path}", icon='INFO')

        # UI Settings
        box = layout.box()
        box.label(text="UI Settings", icon='WINDOW')
        box.prop(self, "show_blendflare_header")

        # Developer Settings
        box = layout.box()
        box.label(text="Developer", icon='CONSOLE')
        box.prop(self, "debug_console")