"""Panel toggle component"""
from ...panel.manager import BlendflarePanelManager

def draw_panel_toggle(layout, context):
    """Draw the panel visibility toggle button."""
    manager = BlendflarePanelManager()
    is_visible = manager._is_visible if manager else False

    icon = 'HIDE_OFF' if is_visible else 'HIDE_ON'
    layout.operator("blendflare.toggle_panel", text="", icon=icon, emboss=True, depress=is_visible)
