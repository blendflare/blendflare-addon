"""Dropdown/selects component for toolbar header.
Draws EnumProperty dropdowns for several Blendflare filters.
"""
import bpy
from ..utils import safe_get_props
from bpy.props import StringProperty


class BLENDFLARE_OT_clear_filter(bpy.types.Operator):
    """Clear a Blendflare filter property (set to empty / Any)."""
    bl_idname = "blendflare.clear_filter"
    bl_label = "Clear filter"
    bl_description = "Reset this filter to 'Any'"

    prop_name: StringProperty()

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "blendflare_props")

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        try:
            props = context.scene.blendflare_props
        except Exception:
            props = safe_get_props(context)

        if not props:
            return {'CANCELLED'}
        if not hasattr(props, self.prop_name):
            return {'CANCELLED'}

        try:
            prop_def = props.bl_rna.properties.get(self.prop_name)

            # Handle StringProperty (like blender_version)
            if prop_def and prop_def.type == 'STRING':
                setattr(props, self.prop_name, "")
                props.page = 1
                try:
                    if context.area:
                        context.area.tag_redraw()
                except Exception:
                    pass
                return {'FINISHED'}

            # Handle EnumProperty
            if prop_def and getattr(prop_def, 'enum_items', None):
                valid = [it.identifier for it in prop_def.enum_items]
            else:
                valid = []

            reset_value = None
            if "ANY" in valid:
                reset_value = "ANY"
            elif valid:
                reset_value = valid[0]

            if reset_value is None:
                return {'CANCELLED'}

            setattr(props, self.prop_name, reset_value)

            # Reset to page 1 when clearing filter
            props.page = 1

            try:
                if context.area:
                    context.area.tag_redraw()
            except Exception:
                pass
            return {'FINISHED'}
        except Exception as e:
            print(f"[Blendflare] clear_filter failed: {e}")
            return {'CANCELLED'}

def draw_filters_button(layout, context):
    """Draw a compact Filters button that opens a popover with filter options."""
    row = layout.row(align=True)
    row.popover(panel="BLENDFLARE_PT_filters_panel", text="", icon='FILTER')


class BLENDFLARE_PT_filters_panel(bpy.types.Panel):
    """Popover panel to expose filter selects."""
    bl_idname = "BLENDFLARE_PT_filters_panel"
    bl_label = "Filters"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 18

    def draw(self, context):
        layout = self.layout
        props = safe_get_props(context)
        if props is None:
            layout.label(text="No properties available")
            return
        # Ensure enum properties don't contain invalid values (prevents RNA warnings)
        def _sanitize_enum(prop_name):
            try:
                prop = props.bl_rna.properties.get(prop_name)
                if not prop:
                    return
                valid = [it.identifier for it in prop.enum_items]
                cur = getattr(props, prop_name, None)
                if cur not in valid:
                    # Reset to stable 'ANY' identifier if present,
                    # otherwise the first valid identifier.
                    if "ANY" in valid:
                        new = "ANY"
                    elif valid:
                        new = valid[0]
                    else:
                        return
                    setattr(props, prop_name, new)
            except Exception:
                pass

        for _p in ("license_type", "materials", "uv_mapping", "render_engine", "style", "game_engines"):
            _sanitize_enum(_p)

        col = layout.column(align=True)

        # Draw each filter with an inline clear button to set it back to "Any"
        def prop_with_clear(prop_name, label):
            row = col.row(align=True)
            row.prop(props, prop_name, text=label)
            op = row.operator("blendflare.clear_filter", text="", icon='CANCEL')
            op.prop_name = prop_name

        prop_with_clear("license_type", "License")
        prop_with_clear("materials", "Material")
        prop_with_clear("uv_mapping", "UV Mapping")
        prop_with_clear("render_engine", "Render Engine")
        prop_with_clear("style", "Style")
        prop_with_clear("game_engines", "Game Engine")

        col.separator()

        # Blender version input (string, e.g., "4", "4.2", "4.2.0")
        row = col.row(align=True)
        row.prop(props, "blender_version", text="Blender")
        op = row.operator("blendflare.clear_filter", text="", icon='CANCEL')
        op.prop_name = "blender_version"

        col.separator()
        # Keep sort_by as a normal prop (no clear needed for sorting)
        col.prop(props, "sort_by", text="Order")