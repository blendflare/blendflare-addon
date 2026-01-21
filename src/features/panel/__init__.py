"""Panel package exports for Blendflare panel components.

Expose the new semantic `BlendflarePanelManager` class and registration
helpers. No compatibility shims are exported.
"""
from .manager import BlendflarePanelManager
from .register import register, unregister

__all__ = ["BlendflarePanelManager", "register", "unregister"]
