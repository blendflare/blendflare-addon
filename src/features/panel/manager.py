"""Panel manager for the Blendflare UI panel."""
import bpy
from ...widgets import BL_UI_Drag_Panel, RADIUS_MD


class BlendflarePanelManager:
    """Singleton manager for the Blendflare UI panel."""

    _instance = None
    _panel = None
    _draw_handler = None
    _is_visible = False
    _results_grid = None
    _is_recreating = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls):
        instance = cls()
        if instance._panel is None:
            instance._create_panel()
        return instance

    def _create_panel(self):
        width, height = self._compute_dimensions()

        self._panel = BL_UI_Drag_Panel(0, 0, width, height)
        self._panel.bg_color = (0.12, 0.12, 0.12, 0.95)
        self._panel.border_radius = RADIUS_MD 
        self._panel.title = "" 
        self._panel._title_height = 0

        from .components.header import add_header_controls, add_close_button
        from .components.body import add_body_content

        add_header_controls(self._panel, width, height, self.hide, self._on_category_click)

        # Set initial category button visibility based on category_group
        try:
            props = bpy.context.scene.blendflare_props
            show_cats = props.category_group == '3d_models'
            for w in self._panel._widgets:
                tag = getattr(w, 'tag', '')
                if tag.startswith('category_'):
                    w._is_visible = show_cats
        except Exception:
            pass

        self._results_grid = add_body_content(self._panel, width, height)

        if self._results_grid:
            self._results_grid.on_card_click = self._on_card_click

        # Add close button LAST so it renders on top of everything
        add_close_button(self._panel, width, height, self.hide)

        self._place_panel()
        self._last_area_size = self._get_area_size()

        # Highlight the active category button
        try:
            props = bpy.context.scene.blendflare_props
            self._update_category_buttons(props.category)
        except Exception:
            self._update_category_buttons('architecture')

    def _on_category_click(self, category):
        """Handle category button click in panel."""
        cat_value = str(category).lower()
        try:
            props = bpy.context.scene.blendflare_props
            props.category = cat_value  # This triggers _on_category_change

            if self._results_grid:
                self._results_grid.set_loading(True)
        except Exception:
            pass

        # Update button colors
        self._update_category_buttons(cat_value)

    def _update_category_buttons(self, active_category):
        """Update category button colors based on selection."""
        if not self._panel:
            return

        for w in self._panel._widgets:
            tag = getattr(w, 'tag', '')
            if tag.startswith('category_'):
                cat_id = tag.replace('category_', '')
                if cat_id == active_category:
                    w.bg_color = (0.2, 0.4, 0.8, 0.9)  # Blue
                else:
                    w.bg_color = (0.2, 0.2, 0.2, 0.9)  # Gray

    def _on_card_click(self, project):
        """Handle card click - open download dialog."""
        try:
            from ..download_dialog import set_download_state

            # Set the project in download state
            set_download_state(project)

            # Open the download dialog (routes to appropriate dialog based on category)
            bpy.ops.blendflare.open_download_dialog('INVOKE_DEFAULT')
        except Exception as e:
            print(f"[Panel] Error opening download dialog: {e}")

    def update_results(self, response):
        """Update grid with search results."""
        if not self._results_grid:
            return

        try:
            if hasattr(response, 'items'):
                self._results_grid.projects = response.items
        except Exception as e:
            print(f"[Panel] Error updating results: {e}")

    def show(self):
        was_hidden = not self._is_visible

        if not self._is_visible:
            self._is_visible = True
            self._register_handlers()
            self._place_panel()

        if was_hidden:
            self._execute_query()

    def hide(self):
        if self._is_visible:
            self._is_visible = False
            self._unregister_handlers()

    def toggle(self):
        if self._is_visible:
            self.hide()
        else:
            self.show()

    def _place_panel(self):
        """Place panel with top margin."""
        if not self._panel:
            return

        area_w, area_h = self._get_area_size()

        # Get header heights
        header_h = tool_header_h = 0
        try:
            area = bpy.context.area
            if area:
                for r in area.regions:
                    if r.type == 'HEADER':
                        header_h = r.height
                    elif r.type == 'TOOL_HEADER':
                        tool_header_h = r.height
        except Exception:
            pass

        top_offset = header_h + tool_header_h + 2
        new_y = area_h - top_offset - self._panel.height
        new_x = (area_w - self._panel.width) // 2

        new_x = max(0, min(new_x, area_w - self._panel.width))
        new_y = max(0, min(new_y, area_h - self._panel.height))

        self._panel.update(new_x, new_y)

    def _register_handlers(self):
        if self._draw_handler is None:
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                self._draw_callback, (), 'WINDOW', 'POST_PIXEL'
            )
            self._force_redraw()

    def _unregister_handlers(self):
        if self._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
            self._force_redraw()

    def _draw_callback(self):
        if self._is_visible:
            try:
                self._check_resize()
                self._update_category_visibility()
                if self._panel:
                    self._panel.draw()
            except Exception as e:
                print(f"[Panel] Draw error: {e}")

    def handle_event(self, context, event):
        if self._is_visible and self._panel:
            return self._panel.handle_event(event)
        return False

    @classmethod
    def cleanup(cls):
        if cls._instance:
            cls._instance.hide()
            cls._instance._panel = None
            cls._instance._results_grid = None
            cls._instance = None

    def _get_area_size(self):
        try:
            if bpy.context and bpy.context.area:
                return bpy.context.area.width, bpy.context.area.height
        except Exception:
            pass
        return 800, 600

    def _compute_dimensions(self):
        """Calculate panel dimensions."""
        area_w, area_h = self._get_area_size()

        max_width = 1200  # Limit width for wide screens (fits ~10 cards)
        width = int(max(250, min(area_w - 40, area_w * 0.8, max_width)))

        # Height based on content
        title_h = 0  # No title bar
        show_cats = False
        try:
            props = bpy.context.scene.blendflare_props
            show_cats = props.category_group == '3d_models'
        except Exception:
            pass

        cats_h = 26 if show_cats else 0  # Category buttons height
        gap = 2 if show_cats else 0     # Minimal gap between cats and grid
        grid_h = 148  # card_height (140) + padding (8)
        bottom = 4

        height = title_h + cats_h + gap + grid_h + bottom
        height = int(min(area_h - 100, height))  # No minimum, let content dictate height

        return width, height

    def _check_resize(self):
        """Recreate panel if window size changed."""
        current = self._get_area_size()
        if hasattr(self, '_last_area_size') and self._last_area_size != current:
            self._recreate_panel()
        self._last_area_size = current

    def _recreate_panel(self):
        """Recreate panel preserving state."""
        if self._is_recreating:
            return
        self._is_recreating = True

        try:
            # Save state
            projects = None
            if self._results_grid and self._results_grid._projects:
                projects = self._results_grid._projects

            # Recreate
            self._panel = None
            self._results_grid = None
            self._create_panel()

            # Restore state
            if projects and self._results_grid:
                self._results_grid.projects = projects

            # Update button colors
            try:
                props = bpy.context.scene.blendflare_props
                self._update_category_buttons(props.category)
            except Exception:
                pass

        finally:
            self._is_recreating = False

    def _update_category_visibility(self):
        """Update category button visibility."""
        if self._is_recreating:
            return

        try:
            props = bpy.context.scene.blendflare_props
            should_show = props.category_group == '3d_models'
        except Exception:
            should_show = False

        if not self._panel:
            return

        # Check current visibility
        current = None
        for w in self._panel._widgets:
            tag = getattr(w, 'tag', '')
            if tag.startswith('category_'):
                current = w._is_visible
                break

        if current is not None and current != should_show:
            self._recreate_panel()
        else:
            for w in self._panel._widgets:
                tag = getattr(w, 'tag', '')
                if tag.startswith('category_'):
                    w._is_visible = should_show

    def _execute_query(self):
        """Execute query when panel is shown."""
        try:
            from ..query import build_query, do_search
            from ..query.cache import get_cache

            props = bpy.context.scene.blendflare_props
            query = build_query(props)

            # Build cache key
            cache_key = ('search',) + tuple(sorted(query.items()))
            cache = get_cache()
            cached = cache.get(*cache_key)

            if cached is None:
                if self._results_grid:
                    self._results_grid.set_loading(True)
                do_search(bpy.context.scene.name, use_cache=True)
            else:
                self.update_results(cached)

        except Exception as e:
            print(f"[Panel] Query error: {e}")

    def _force_redraw(self):
        """Force all 3D viewports and headers to redraw."""
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                        for region in area.regions:
                            region.tag_redraw()
        except Exception:
            pass
