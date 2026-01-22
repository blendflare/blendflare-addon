"""Pagination component for toolbar header."""
import bpy
from bpy.types import Operator
from bpy.props import IntProperty
from ..utils import safe_get_props
from ....logger import toolbar_logger


class BLENDFLARE_OT_next_page(Operator):
    """Go to next page of results"""
    bl_idname = "blendflare.next_page"
    bl_label = "Next Page"
    bl_description = "Load next page of results"
    
    @classmethod
    def poll(cls, context):
        props = safe_get_props(context)
        return props is not None and props.has_next_page
    
    def execute(self, context):
        props = safe_get_props(context)
        if props is None:
            return {'CANCELLED'}
        
        # Increment page
        props.page += 1

        toolbar_logger(f"Next page: {props.page}")
        
        # Force redraw
        try:
            context.area.tag_redraw()
        except Exception:
            pass
        
        return {'FINISHED'}


class BLENDFLARE_OT_prev_page(Operator):
    """Go to previous page of results"""
    bl_idname = "blendflare.prev_page"
    bl_label = "Previous Page"
    bl_description = "Load previous page of results"
    
    @classmethod
    def poll(cls, context):
        props = safe_get_props(context)
        return props is not None and props.page > 1
    
    def execute(self, context):
        props = safe_get_props(context)
        if props is None:
            return {'CANCELLED'}
        
        # Decrement page (min 1)
        props.page = max(1, props.page - 1)

        toolbar_logger(f"Previous page: {props.page}")
        
        # Force redraw
        try:
            context.area.tag_redraw()
        except Exception:
            pass
        
        return {'FINISHED'}


class BLENDFLARE_OT_first_page(Operator):
    """Go to first page of results"""
    bl_idname = "blendflare.first_page"
    bl_label = "First Page"
    bl_description = "Go to first page"
    
    @classmethod
    def poll(cls, context):
        props = safe_get_props(context)
        return props is not None and props.page > 1
    
    def execute(self, context):
        props = safe_get_props(context)
        if props is None:
            return {'CANCELLED'}
        
        props.page = 1

        toolbar_logger("First page")
        
        try:
            context.area.tag_redraw()
        except Exception:
            pass
        
        return {'FINISHED'}


class BLENDFLARE_OT_last_page(Operator):
    """Go to last page of results"""
    bl_idname = "blendflare.last_page"
    bl_label = "Last Page"
    bl_description = "Go to last page"
    
    @classmethod
    def poll(cls, context):
        props = safe_get_props(context)
        return props is not None and props.total_pages > 1 and props.page < props.total_pages
    
    def execute(self, context):
        props = safe_get_props(context)
        if props is None:
            return {'CANCELLED'}
        
        props.page = props.total_pages

        toolbar_logger(f"Last page: {props.page}")
        
        try:
            context.area.tag_redraw()
        except Exception:
            pass
        
        return {'FINISHED'}


def draw_pagination_controls(layout, context):
    """Draw pagination controls in toolbar."""
    props = safe_get_props(context)
    if props is None:
        return
    
    # Only show if there are results
    if props.total_pages < 1:
        return
    
    row = layout.row(align=True)
    
    # First page button
    sub = row.row(align=True)
    sub.enabled = props.page > 1
    sub.operator("blendflare.first_page", text="", icon='REW')
    
    # Previous button
    sub = row.row(align=True)
    sub.enabled = props.page > 1
    sub.operator("blendflare.prev_page", text="", icon='TRIA_LEFT')
    
    # Current page indicator
    if props.total_pages > 1:
        row.label(text=f"{props.page}/{props.total_pages}")
    else:
        row.label(text=f"Page {props.page}")
    
    # Next button
    sub = row.row(align=True)
    sub.enabled = props.has_next_page
    sub.operator("blendflare.next_page", text="", icon='TRIA_RIGHT')
    
    # Last page button
    sub = row.row(align=True)
    sub.enabled = props.page < props.total_pages
    sub.operator("blendflare.last_page", text="", icon='FF')


# Export operators for registration
__all__ = [
    'BLENDFLARE_OT_next_page',
    'BLENDFLARE_OT_prev_page',
    'BLENDFLARE_OT_first_page',
    'BLENDFLARE_OT_last_page',
    'draw_pagination_controls',
]