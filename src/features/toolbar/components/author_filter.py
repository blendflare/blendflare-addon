"""Author filter toggle button for toolbar."""
import bpy
from bpy.types import Operator


def _get_nickname() -> str:
    """Get nickname from addon preferences."""
    try:
        from .... import addon_key
        prefs = bpy.context.preferences.addons[addon_key].preferences
        return getattr(prefs, 'blendflare_nickname', '') or ''
    except Exception:
        return ''


class BLENDFLARE_OT_toggle_author_filter(Operator):
    """Toggle filter by author (your assets only)"""
    bl_idname = "blendflare.toggle_author_filter"
    bl_label = "Toggle Author Filter"
    bl_description = "Filter results to show only your assets"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        props = context.scene.blendflare_props

        # Check if nickname is configured
        nickname = _get_nickname()
        if not nickname and not props.filter_by_author:
            self.report({'WARNING'}, "Please set your nickname in addon preferences first")
            return {'CANCELLED'}

        # Toggle the filter
        props.filter_by_author = not props.filter_by_author

        return {'FINISHED'}


def draw_author_filter_button(layout, context):
    """Draw the author filter toggle button."""
    props = context.scene.blendflare_props
    nickname = _get_nickname()

    # Don't show button if no nickname configured
    if not nickname:
        return

    row = layout.row(align=True)

    # Button appearance based on state
    if props.filter_by_author:
        icon = 'CHECKBOX_HLT'
        text = f"My Assets"
    else:
        icon = 'CHECKBOX_DEHLT'
        text = "My Assets"

    op = row.operator(
        "blendflare.toggle_author_filter",
        text=text,
        icon=icon,
        depress=props.filter_by_author
    )
