"""Panel operators relocated into panel/components for modularity."""
import bpy
from bpy.types import Operator
from ..manager import BlendflarePanelManager


class BLENDFLARE_OT_toggle_panel(Operator):
    """Toggle Blendflare asset panel visibility"""
    bl_idname = "blendflare.toggle_panel"
    bl_label = "Toggle Asset Panel"
    bl_description = "Show/Hide Blendflare asset browser panel"

    def execute(self, context):
        manager = BlendflarePanelManager.initialize()
        manager.toggle()

        # Start modal if showing
        if manager._is_visible:
            bpy.ops.blendflare.panel_modal('INVOKE_DEFAULT')

        # Tag for redraw
        try:
            context.area.tag_redraw()
        except Exception:
            pass

        return {'FINISHED'}


class BLENDFLARE_OT_panel_modal(Operator):
    """Modal operator for handling panel events"""
    bl_idname = "blendflare.panel_modal"
    bl_label = "Blendflare Panel Modal"

    def modal(self, context, event):
        manager = BlendflarePanelManager()

        # Let panel handle the event
        if manager.handle_event(context, event):
            try:
                context.area.tag_redraw()
            except Exception:
                pass
            return {'RUNNING_MODAL'}

        # ESC to close panel
        if event.type == 'ESC' and event.value == 'PRESS':
            manager.hide()
            try:
                context.area.tag_redraw()
            except Exception:
                pass
            return {'CANCELLED'}

        # Check if panel is still visible
        if not manager._is_visible:
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        manager = BlendflarePanelManager()
        if manager._is_visible:
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        return {'CANCELLED'}
