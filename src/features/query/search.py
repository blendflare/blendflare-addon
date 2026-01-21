"""Search manager with caching and loading state."""
import os
import time
import threading
import bpy
from typing import Optional, Dict, Any

from .cache import get_cache
from ..toast import show_toast, ToastType


# Debounce tokens per scene
_debounce_tokens: Dict[str, float] = {}


def build_query(props) -> Dict[str, Any]:
    """Build query dict from BlendflareProperties."""
    q = {}

    # Search text
    text = getattr(props, 'search_text', '').strip()
    if text:
        q['q'] = text

    # Category (the actual API category)
    cat = getattr(props, 'category', '')
    if cat:
        q['category'] = cat

    # Subcategory filter
    subcat = getattr(props, 'subcategory', '')
    if subcat:
        q['subcategory'] = subcat

    # Sort
    sort = getattr(props, 'sort_by', None)
    if sort:
        q['sort_by'] = sort

    # Filters
    for name in ('license_type', 'materials', 'uv_mapping', 'render_engine', 'style', 'game_engines'):
        val = getattr(props, name, None)
        if val and str(val) != 'ANY':
            q[name] = val

    # Blender version filter
    blender_ver = getattr(props, 'blender_version', '').strip()
    if blender_ver:
        q['blender_version'] = blender_ver

    # Author filter (from preferences nickname)
    filter_by_author = getattr(props, 'filter_by_author', False)
    if filter_by_author:
        nickname = _get_nickname()
        if nickname:
            q['author'] = nickname

    # Pagination
    page = getattr(props, 'page', 1)
    if page > 1:
        q['page'] = page

    return q


def _make_cache_key(query: Dict[str, Any]) -> tuple:
    """Convert query dict to cache key."""
    return ('search',) + tuple(sorted(query.items()))


def _get_api_key() -> Optional[str]:
    """Get API key from preferences or environment."""
    try:
        from ... import addon_key
        prefs = bpy.context.preferences.addons[addon_key].preferences
        key = getattr(prefs, 'blendflare_api_key', '')
        if key:
            return key
    except Exception:
        pass
    return os.environ.get('BLENDFLARE_API_KEY')


def _get_nickname() -> Optional[str]:
    """Get nickname from addon preferences."""
    try:
        from ... import addon_key
        prefs = bpy.context.preferences.addons[addon_key].preferences
        nickname = getattr(prefs, 'blendflare_nickname', '')
        if nickname:
            return nickname
    except Exception:
        pass
    return None


def _get_grid():
    """Get the grid widget from panel manager."""
    try:
        from ..panel import BlendflarePanelManager
        manager = BlendflarePanelManager()
        if manager and manager._is_visible and manager._results_grid:
            return manager._results_grid
    except Exception:
        pass
    return None


def _notify_panel(response) -> None:
    """Notify panel manager of new results."""
    try:
        from ..panel import BlendflarePanelManager
        manager = BlendflarePanelManager()
        if manager and manager._is_visible:
            manager.update_results(response)
    except Exception:
        pass


def _update_pagination(scene_name: str, response) -> None:
    """Update pagination properties from response."""
    try:
        scene = bpy.data.scenes.get(scene_name)
        if scene and hasattr(scene, 'blendflare_props'):
            props = scene.blendflare_props
            pagination = getattr(response, 'pagination', None)
            if pagination:
                # Use internal dict to avoid triggering updates
                props['total_pages'] = getattr(pagination, 'total_pages', 1)
                props['has_next_page'] = getattr(pagination, 'has_next_page', False)

                # Clamp page if it exceeds total
                total = props['total_pages']
                if props.page > total:
                    props['page'] = max(1, total)
    except Exception:
        pass


def _force_redraw():
    """Force UI redraw including all regions."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                    for region in area.regions:
                        region.tag_redraw()
    except Exception:
        pass


def do_search(scene_name: str, use_cache: bool = True) -> None:
    """Execute search for scene."""
    scene = bpy.data.scenes.get(scene_name)
    if not scene or not hasattr(scene, 'blendflare_props'):
        return

    props = scene.blendflare_props
    query = build_query(props)
    cache_key = _make_cache_key(query)
    cache = get_cache()

    # Check cache first
    if use_cache:
        cached = cache.get(*cache_key)
        if cached is not None:
            def on_main():
                _update_pagination(scene_name, cached)
                _notify_panel(cached)
                _force_redraw()
                return None
            bpy.app.timers.register(on_main, first_interval=0.01)
            return

    # Check API key
    api_key = _get_api_key()
    if not api_key:
        def on_no_key():
            grid = _get_grid()
            if grid:
                grid.set_no_api_key()
            show_toast("API key not configured. Check addon preferences.", ToastType.WARNING, 5.0)
            _force_redraw()
            return None
        bpy.app.timers.register(on_no_key, first_interval=0.01)
        return

    # Show loading state
    grid = _get_grid()
    if grid:
        grid.set_loading(True)

    def worker():
        try:
            from blendflare import BlendflareClient
            client = BlendflareClient(api_key=api_key)

            # Build kwargs for SDK
            kwargs = {'page': query.get('page', 1), 'limit': 10}

            if 'q' in query:
                kwargs['q'] = query['q']
            if 'category' in query:
                kwargs['category'] = query['category']
            if 'subcategory' in query:
                kwargs['subcategory'] = query['subcategory']
            if 'sort_by' in query:
                kwargs['sort_by'] = query['sort_by']

            for name in ('license_type', 'materials', 'uv_mapping', 'render_engine', 'style', 'game_engines'):
                if name in query:
                    kwargs[name] = query[name]

            # Blender version filter
            if 'blender_version' in query:
                kwargs['blender_version'] = query['blender_version']

            # Author filter
            if 'author' in query:
                kwargs['author'] = query['author']

            response = client.search_projects(**kwargs)
            cache.set(response, *cache_key)

            def on_main():
                _update_pagination(scene_name, response)
                _notify_panel(response)
                _force_redraw()
                return None

            bpy.app.timers.register(on_main, first_interval=0.01)

        except Exception as e:
            error_msg = str(e)

            def on_error():
                grid = _get_grid()
                if grid:
                    grid.set_error(f"Error: {error_msg[:50]}")
                show_toast(f"Search failed: {error_msg[:40]}", ToastType.ERROR, 4.0)
                _force_redraw()
                return None

            bpy.app.timers.register(on_error, first_interval=0.01)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def schedule_search(scene_name: str, delay: float = 0.5, use_cache: bool = True) -> None:
    """Schedule debounced search."""
    token = time.time()
    _debounce_tokens[scene_name] = token

    def timer():
        if _debounce_tokens.get(scene_name) != token:
            return None
        do_search(scene_name, use_cache=use_cache)
        return None

    interval = max(0.01, delay)
    bpy.app.timers.register(timer, first_interval=interval)


def on_search_update(self, context):
    """Property update handler for search text (debounced)."""
    try:
        scene_name = context.scene.name
    except Exception:
        scene_name = 'Scene'
    schedule_search(scene_name, delay=0.5)


def on_filter_update(self, context):
    """Property update handler for filters (immediate)."""
    try:
        scene_name = context.scene.name
    except Exception:
        scene_name = 'Scene'
    schedule_search(scene_name, delay=0.0)


def invalidate_cache():
    """Clear the entire cache."""
    get_cache().clear()
