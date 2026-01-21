# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "blendflare_asset_browser",
    "author": "Blendflare Team",
    "description": "Search and import assets from Blendflare directly within Blender",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Generic",
}

from . import auto_load

addon_key = __package__

auto_load.init()


def register():
    auto_load.register()


def unregister():
    auto_load.unregister()

    try:
        from .features.query import get_cache
        get_cache().clear()
    except Exception:
        pass

    try:
        from .widgets.bl_ui_button import BL_UI_Button
        from .widgets.bl_ui_image import BL_UI_Image
        BL_UI_Button.cleanup_textures()
        BL_UI_Image.cleanup_cache()
    except Exception:
        pass

    try:
        from .features.toast import ToastManager
        ToastManager.cleanup()
    except Exception:
        pass
