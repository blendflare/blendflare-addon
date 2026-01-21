"""Registration helpers for the panel package.

Keep registration and load handlers separated so `toolbar` can call
`register()` / `unregister()` without importing heavy UI implementation.
"""
import bpy
from bpy.app.handlers import persistent
from .manager import BlendflarePanelManager


@persistent
def _load_post_handler(dummy):
    BlendflarePanelManager.cleanup()


def register():
    if _load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post_handler)


def unregister():
    BlendflarePanelManager.cleanup()
    if _load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post_handler)
