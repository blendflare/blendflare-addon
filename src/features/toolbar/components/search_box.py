"""Search box component and search operator"""
import bpy
from bpy.types import Operator
from ..utils import safe_get_props


def draw_search_box(layout, context):
    """Draw search input field."""
    props = safe_get_props(context)
    if props is None:
        return

    row = layout.row(align=True)
    row.scale_x = 1.5
    row.prop(props, "search_text", text="", icon='VIEWZOOM')


class BLENDFLARE_OT_search(Operator):
    """Execute search query"""
    bl_idname = "blendflare.search"
    bl_label = "Search Assets"
    bl_description = "Search for Blendflare assets"

    def execute(self, context):
        props = safe_get_props(context)
        if props is None:
            return {'CANCELLED'}
        query = props.search_text
        
        # Reset to page 1 when searching
        props.page = 1

        try:
            from ...query import on_filter_update
            on_filter_update(self, context)
        except Exception:
            pass

        return {'FINISHED'}