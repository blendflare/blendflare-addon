"""Category buttons component including operator."""
from bpy.types import Operator
from bpy.props import StringProperty
from ..utils import safe_get_props


# Icon mapping for toolbar category groups
CATEGORY_ICONS = {
    'all': 'OUTLINER_OB_GROUP_INSTANCE',  # Search all categories
    '3d_models': 'MESH_CUBE',
    'materials': 'MATERIAL',
    'scenes': 'SCENE_DATA',
    'hdris': 'WORLD',
}

CATEGORY_TOOLTIPS = {
    'all': 'All Categories',
    '3d_models': '3D Models',
    'materials': 'Materials',
    'scenes': 'Scenes',
    'hdris': 'HDRIs',
}

def draw_category_buttons(layout, context):
    """Draw category group filter buttons in toolbar."""
    props = safe_get_props(context)
    if props is None:
        return

    row = layout.row(align=True)
    row.scale_x = 1.0

    for group, icon in CATEGORY_ICONS.items():
        # Determine active state based on group type
        if group == 'all':
            is_active = props.category_group == 'all'
        elif group == '3d_models':
            is_active = props.category_group == '3d_models'
        else:
            is_active = props.category == group

        op = row.operator("blendflare.set_category_group", text="", icon=icon, depress=is_active)
        op.group = group


class BLENDFLARE_OT_set_category_group(Operator):
    """Set category group."""
    bl_idname = "blendflare.set_category_group"
    bl_label = ""
    # bl_description (fallback)
    bl_description = "Switch between category groups" 

    group: StringProperty()

    @classmethod
    def description(cls, context, properties):
        
        if properties.group in CATEGORY_TOOLTIPS:
            return CATEGORY_TOOLTIPS[properties.group]
        
        # Fallback description
        if properties.group:
            return f"Switch to {properties.group.replace('_', ' ').title()}"
            
        return cls.bl_description
    # --------------------------

    def execute(self, context):
        props = safe_get_props(context)
        if props is None:
            return {'CANCELLED'}

        if self.group == 'all':
            # Set category to empty string to search all categories
            props.category = ''
            props['category_group'] = 'all'
        elif self.group == '3d_models':
            props.category = 'architecture'
        else:
            props.category = self.group

        return {'FINISHED'}


# Keep old operator name for compatibility
BLENDFLARE_OT_category_filter = BLENDFLARE_OT_set_category_group
