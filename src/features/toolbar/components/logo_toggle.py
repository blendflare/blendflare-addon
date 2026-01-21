"""Logo + header switch component"""
import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from ..utils import toggle_show_blendflare_header


def draw_logo_and_toggle(layout, context, icon_value, is_showing):
    """Draw the logo and header toggle. Receives `is_showing` to avoid cross-imports."""
    # Arrow icon based on state
    icon_arrow = 'TRIA_DOWN' if is_showing else 'TRIA_RIGHT'

    row = layout.row(align=True)

    # Logo button (also acts as toggle)
    if icon_value:
        row.operator("blendflare.switch_header", text="", icon_value=icon_value, emboss=False)
    else:
        row.operator("blendflare.switch_header", text="", icon='GHOST_ENABLED', emboss=False)

    # Arrow button
    row.operator("blendflare.switch_header", text="", icon=icon_arrow, emboss=False)


class BLENDFLARE_OT_switch_header(Operator):
    """Switch between Blendflare and standard header"""
    bl_idname = "blendflare.switch_header"
    bl_label = "Switch Header Mode"
    bl_description = "Toggle between Blendflare header and standard/BlenderKit header"

    def execute(self, context):
        if toggle_show_blendflare_header(context):
            return {'FINISHED'}
        return {'CANCELLED'}

