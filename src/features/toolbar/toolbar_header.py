"""
Main Toolbar Header - Monkey patches the 3D View header
"""
import bpy
import os
import bpy.utils.previews
from bpy.props import PointerProperty

from ..panel import BlendflarePanelManager
from .properties import BlendflareProperties
from .utils import get_show_blendflare_header as _get_show_blendflare_header
from blendflare.types import Category


# UI DRAWING FUNCTIONS - delegated to components to keep file small
from .components import (
    draw_logo_and_toggle,
    draw_category_buttons,
    draw_search_box,
    draw_filters_button,
    draw_panel_toggle,
    draw_subcategory_dropdown,
    draw_pagination_controls,
    draw_author_filter_button
)


def draw_blendflare_toolbar(layout, context):
    """Draw the complete Blendflare toolbar content (composed from components)."""
    pcoll = preview_collections.get("main")
    logo_icon = pcoll["bf_logo"].icon_id if pcoll and "bf_logo" in pcoll else 0

    # Logo + toggle
    draw_logo_and_toggle(layout, context, logo_icon, _get_show_blendflare_header(context))

    # Category buttons
    draw_category_buttons(layout, context)
    
    # Subcategory dropdown
    draw_subcategory_dropdown(layout, context)

    # Search box
    draw_search_box(layout, context)

    # Author filter toggle (only shows if nickname is configured)
    draw_author_filter_button(layout, context)

    # Panel toggle button
    draw_panel_toggle(layout, context)
    
    # Filters button
    draw_filters_button(layout, context)
    
    # ============== NUEVO: Pagination controls ==============
    draw_pagination_controls(layout, context)
    # ========================================================


# ============================================================================
# GLOBAL PREVIEWS (Logo icon storage)
# ============================================================================
preview_collections = {}

# Store original draw function
_original_tool_header_draw = None


# ============================================================================
# HEADER WRAPPER FUNCTION
# ============================================================================

def blendflare_header_wrapper(self, context):
    """
    Main header wrapper - Monkey patches VIEW3D_HT_tool_header
    """
    layout = self.layout
    props = context.scene.blendflare_props
    
    # Get logo icon
    pcoll = preview_collections.get("main")
    logo_icon = pcoll["bf_logo"].icon_id if pcoll and "bf_logo" in pcoll else 0
    
    # -----------------------------------------------------------
    # LOGO + TOGGLE BUTTON (Always shown on left)
    # -----------------------------------------------------------
    draw_logo_and_toggle(layout, context, logo_icon, _get_show_blendflare_header(context))
    
    # -----------------------------------------------------------
    # CONTENT BASED ON MODE
    # -----------------------------------------------------------
    
    if _get_show_blendflare_header(context):
        # === BLENDFLARE MODE ===
        self.draw_tool_settings(context)
        layout.separator_spacer()
        
        # Draw Blendflare toolbar
        draw_blendflare_toolbar(layout, context)
        
        layout.separator_spacer()
        self.draw_mode_settings(context)
        
    else:
        # === STANDARD/BLENDERKIT MODE ===
        if _original_tool_header_draw:
            try:
                _original_tool_header_draw(self, context)
            except Exception as e:
                print(f"Error drawing original header: {e}")
                # Fallback to basic header
                self.draw_tool_settings(context)
                self.draw_mode_settings(context)


# ============================================================================
# REGISTER / UNREGISTER
# ============================================================================

def register():
    global _original_tool_header_draw

    print("🚀 Registering Blendflare toolbar...")

    # 1. Clean up any existing previews first (prevents ResourceWarning on re-register)
    if preview_collections:
        for pcoll in preview_collections.values():
            try:
                bpy.utils.previews.remove(pcoll)
            except Exception:
                pass
        preview_collections.clear()

    # 2. Load Icons
    pcoll = bpy.utils.previews.new()
    dir_path = os.path.dirname(__file__)
    icons_dir = os.path.join(dir_path, "../../icons")

    print(f"📁 Loading Blendflare icons from: {icons_dir}")

    try:
        logo_path = os.path.join(icons_dir, "logo.png")
        if os.path.exists(logo_path):
            pcoll.load("bf_logo", logo_path, 'IMAGE')
            print("✓ Logo loaded successfully")
        else:
            print(f"⚠ Logo not found at: {logo_path}")
    except Exception as e:
        print(f"❌ Error loading logo: {e}")

    preview_collections["main"] = pcoll
    
    # 2. Add PointerProperty to Scene
    if not hasattr(bpy.types.Scene, "blendflare_props"):
        bpy.types.Scene.blendflare_props = PointerProperty(type=BlendflareProperties)
        print("✓ Properties registered")
        # Sanitize existing scene values across all scenes to ensure enum
        # properties have valid identifiers (use 'ANY' as the unassigned id).
        try:
            enum_props = ("license_type", "materials", "uv_mapping", "render_engine", "style", "game_engines")
            for scene in getattr(bpy.data, 'scenes', []):
                try:
                    if not hasattr(scene, 'blendflare_props'):
                        continue
                    sp = scene.blendflare_props
                    for name in enum_props:
                        prop_def = sp.bl_rna.properties.get(name)
                        if not prop_def:
                            continue
                        valid = [it.identifier for it in prop_def.enum_items]
                        cur = getattr(sp, name, None)
                        if cur not in valid:
                            if "ANY" in valid:
                                setattr(sp, name, "ANY")
                            elif valid:
                                setattr(sp, name, valid[0])
                except Exception:
                    pass
        except Exception:
            pass
    
    # 3. UI Manager register (solo handlers)
    from ..panel import register as panel_register
    panel_register()
    print("✓ UI Manager registered")


    # 4. Monkey Patch Header
    if getattr(bpy.types.VIEW3D_HT_tool_header, "draw", None) != blendflare_header_wrapper:
        _original_tool_header_draw = bpy.types.VIEW3D_HT_tool_header.draw
        bpy.types.VIEW3D_HT_tool_header.draw = blendflare_header_wrapper
        print("✓ Header monkey-patched successfully")
    
    print("✅ Blendflare toolbar registered successfully!")


def unregister():
    global _original_tool_header_draw
    
    print("🧹 Unregistering Blendflare toolbar...")
    
    # 1. Restore original header
    if _original_tool_header_draw is not None:
        bpy.types.VIEW3D_HT_tool_header.draw = _original_tool_header_draw
        _original_tool_header_draw = None
        print("✓ Original header restored")
    
    # 2. Unregister UI Manager
    from ..panel import unregister as panel_unregister
    panel_unregister()

    # 3. Remove PointerProperty from Scene
    if hasattr(bpy.types.Scene, "blendflare_props"):
        del bpy.types.Scene.blendflare_props
        print("✓ Properties unregistered")
    
    # 4. Clean up icons
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
    print("✓ Icons cleaned up")
    
    print("✅ Blendflare toolbar unregistered successfully!")