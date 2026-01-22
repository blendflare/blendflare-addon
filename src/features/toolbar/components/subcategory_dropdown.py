"""Subcategory dropdown component for toolbar header."""
import bpy
from bpy.types import Operator, Panel
from bpy.props import StringProperty
from blendflare import get_subcategories, Category
from ..utils import safe_get_props
from ....logger import toolbar_logger


def draw_subcategory_dropdown(layout, context):
    """Draw subcategory dropdown that updates based on active category."""
    props = safe_get_props(context)
    if props is None:
        return

    # Get current category
    current_cat = props.category

    # Try to get subcategories for current category
    try:
        cat_enum = Category(current_cat)
        subcategories = get_subcategories(cat_enum)
    except (ValueError, KeyError):
        return

    if not subcategories:
        return

    # Draw dropdown
    row = layout.row(align=True)

    # Get current subcategory text
    current_sub = props.subcategory
    sub_text = current_sub.replace('_', ' ').title() if current_sub else "All"

    # Popover button with current selection
    row.popover(
        panel="BLENDFLARE_PT_subcategory_panel",
        text=sub_text,
    )

    # Clear button if a subcategory is selected
    if props.subcategory:
        row.operator("blendflare.clear_subcategory", text="", icon='X')


class BLENDFLARE_OT_select_subcategory(Operator):
    """Select a subcategory filter"""
    bl_idname = "blendflare.select_subcategory"
    bl_label = "Select Subcategory"
    bl_description = "Filter by subcategory"

    subcategory: StringProperty()

    def execute(self, context):
        props = safe_get_props(context)
        if props is None:
            return {'CANCELLED'}

        props.subcategory = self.subcategory
        toolbar_logger(f"Subcategory filter: {self.subcategory or 'All'}")

        return {'FINISHED'}


class BLENDFLARE_OT_clear_subcategory(Operator):
    """Clear subcategory filter"""
    bl_idname = "blendflare.clear_subcategory"
    bl_label = "Clear Subcategory"
    bl_description = "Clear subcategory filter"

    def execute(self, context):
        props = safe_get_props(context)
        if props is None:
            return {'CANCELLED'}

        props.subcategory = ""
        toolbar_logger("Subcategory filter cleared")

        return {'FINISHED'}


class BLENDFLARE_PT_subcategory_panel(Panel):
    """Popover panel for subcategory selection"""
    bl_idname = "BLENDFLARE_PT_subcategory_panel"
    bl_label = "Subcategories"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 12

    def draw(self, context):
        layout = self.layout
        props = safe_get_props(context)
        if props is None:
            layout.label(text="No properties available")
            return

        # Get current category
        current_cat = props.category

        # Get subcategories
        try:
            cat_enum = Category(current_cat)
            subcategories = get_subcategories(cat_enum)
        except (ValueError, KeyError):
            layout.label(text="Unknown category")
            return

        if not subcategories:
            layout.label(text="No subcategories for this category")
            return

        # Draw "All" option
        col = layout.column(align=True)
        row = col.row()
        is_all = not props.subcategory
        row.operator(
            "blendflare.select_subcategory",
            text="All",
            depress=is_all
        ).subcategory = ""

        col.separator()

        # Draw subcategory buttons
        for sub in subcategories:
            row = col.row()
            sub_name = sub.value.replace('_', ' ').title()
            is_selected = (props.subcategory == sub.value)

            op = row.operator(
                "blendflare.select_subcategory",
                text=sub_name,
                depress=is_selected
            )
            op.subcategory = sub.value


# Export operators for registration
__all__ = [
    'BLENDFLARE_OT_select_subcategory',
    'BLENDFLARE_OT_clear_subcategory',
    'BLENDFLARE_PT_subcategory_panel',
    'draw_subcategory_dropdown',
]
