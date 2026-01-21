import bpy
import blf
import gpu
import time
from gpu_extras.batch import batch_for_shader
from .bl_ui_widget import BL_UI_Widget
from .bl_ui_card import BL_UI_Card
from .bl_ui_hover_card import BL_UI_Hover_Card


class BL_UI_Grid(BL_UI_Widget):
    """Single-row grid container for displaying project cards."""

    # Grid states
    STATE_IDLE = 'idle'
    STATE_LOADING = 'loading'
    STATE_EMPTY = 'empty'
    STATE_ERROR = 'error'
    STATE_NO_API_KEY = 'no_api_key'

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)

        # Grid settings - compact layout
        self._card_width = 110
        self._card_height = 140
        self._spacing = 4
        self._padding = 4

        # Cards and data
        self._cards = []
        self._hover_card = None
        self._projects = []

        # Card mapping for download progress updates: key -> card
        self._card_map = {}

        # State
        self._state = self.STATE_IDLE
        self._error_message = ""
        self._anim_start = 0
        self._anim_timer = None

        # Colors
        self._bg_color = (0.08, 0.08, 0.08, 1.0)
        self._skeleton_color = (0.15, 0.15, 0.15, 1.0)
        self._skeleton_highlight = (0.22, 0.22, 0.22, 1.0)
        self._text_color = (0.6, 0.6, 0.6, 1.0)
        self._spinner_color = (0.4, 0.6, 1.0, 0.8)

        # Callbacks
        self.on_card_click = None

        # Register with download tracker for progress updates
        self._register_download_tracker()

    @property
    def projects(self):
        return self._projects

    @projects.setter
    def projects(self, value):
        """Set projects and rebuild grid."""
        self._projects = value if value else []
        if self._projects:
            self._state = self.STATE_IDLE
            self._rebuild_grid()
        else:
            self._state = self.STATE_EMPTY
            self._cards.clear()
        self._schedule_redraws(3)

    @property
    def card_width(self):
        return self._card_width

    @card_width.setter
    def card_width(self, value):
        self._card_width = max(100, value)
        self._rebuild_grid()

    @property
    def card_height(self):
        return self._card_height

    @card_height.setter
    def card_height(self, value):
        self._card_height = max(120, value)
        self._rebuild_grid()

    def set_loading(self, loading: bool) -> None:
        """Set loading state."""
        if loading:
            self._state = self.STATE_LOADING
            self._anim_start = time.time()
            self._cards.clear()
            self._start_anim_timer()
        elif self._state == self.STATE_LOADING:
            self._stop_anim_timer()
            if not self._projects:
                self._state = self.STATE_EMPTY
            else:
                self._state = self.STATE_IDLE
        self._force_redraw()

    def _start_anim_timer(self):
        """Start animation timer for spinner."""
        if self._anim_timer is not None:
            return

        def timer_tick():
            if self._state != self.STATE_LOADING:
                self._anim_timer = None
                return None  # Stop timer
            self._force_redraw()
            return 0.033  # ~30 FPS

        self._anim_timer = True
        bpy.app.timers.register(timer_tick, first_interval=0.033)

    def _stop_anim_timer(self):
        """Stop animation timer."""
        self._anim_timer = None

    def set_error(self, message: str = "Error loading results") -> None:
        """Set error state with message."""
        self._state = self.STATE_ERROR
        self._error_message = message
        self._cards.clear()
        self._force_redraw()

    def set_no_api_key(self) -> None:
        """Set no API key state."""
        self._state = self.STATE_NO_API_KEY
        self._cards.clear()
        self._force_redraw()

    def _calculate_cards_per_row(self) -> int:
        """Calculate how many cards fit in one row."""
        available = self.width - (self._padding * 2)
        return max(1, int((available + self._spacing) / (self._card_width + self._spacing)))

    def _rebuild_grid(self):
        """Rebuild grid layout."""
        self._cards.clear()
        self._card_map.clear()

        if not self._projects:
            return

        cards_per_row = self._calculate_cards_per_row()
        visible = self._projects[:cards_per_row]

        for i, project in enumerate(visible):
            card_x = self._padding + i * (self._card_width + self._spacing)
            card_y = (self.height - self._card_height) // 2

            card = BL_UI_Card(card_x, card_y, self._card_width, self._card_height)

            try:
                card.title = project.project_info.title
                card.image_url = project.preview_image
                card.project_data = project

                # Register card for download progress tracking
                nickname = project.author.nickname
                slug = project.slug
                key = f"{nickname}/{slug}"
                self._card_map[key] = card

                # Check if this asset is currently downloading
                self._update_card_download_state(card, nickname, slug)
            except Exception:
                card.title = "Unknown"

            card.on_click = lambda c, p=project: self._on_card_clicked(c, p)
            card.on_hover = lambda c: self._on_card_hovered(c)

            self._cards.append(card)

        self.update(self.x_screen, self.y_screen)

    def _on_card_clicked(self, _card, project):
        if self.on_card_click:
            self.on_card_click(project)

    def _on_card_hovered(self, card):
        if not card.project_data:
            return

        if not self._hover_card:
            self._hover_card = BL_UI_Hover_Card(0, 0, 320, 280)

        # Position below the card (bottom-start aligned)
        hover_x = card.x_screen
        hover_y = card.y_screen - self._hover_card.height - 10

        # Check if it goes below viewport, if so show above the card
        if hover_y < 0:
            hover_y = card.y_screen + card.height + 10

        # Check horizontal bounds
        try:
            viewport_w = bpy.context.area.width if bpy.context.area else 1920
        except Exception:
            viewport_w = 1920

        if hover_x + self._hover_card.width > viewport_w:
            hover_x = viewport_w - self._hover_card.width - 10

        self._hover_card.show_at(int(hover_x), int(hover_y), card.project_data)
        self._force_redraw()

    def update(self, x, y):
        super().update(x, y)
        for i, card in enumerate(self._cards):
            card_x = x + self._padding + i * (self._card_width + self._spacing)
            card_y = y + (self.height - self._card_height) // 2
            card.update(int(card_x), int(card_y))

    def handle_event(self, event):
        if not self._is_visible:
            return False

        x = event.mouse_region_x
        y = event.mouse_region_y

        if self._hover_card and self._hover_card._is_visible:
            over_card = any(c.is_in_rect(x, y) for c in self._cards)
            over_hover = self._hover_card.is_in_rect(x, y)

            if not over_card and not over_hover:
                self._hover_card.hide()
                self._force_redraw()

        for card in self._cards:
            if card.handle_event(event):
                self._force_redraw()
                return True

        return False

    def draw(self):
        if not self._is_visible:
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Draw background
        self._draw_rect(shader, self.x_screen, self.y_screen,
                       self.width, self.height, self._bg_color)

        # Draw based on state
        if self._state == self.STATE_LOADING:
            self._draw_skeleton_cards(shader)
        elif self._state == self.STATE_EMPTY:
            self._draw_message("No results found")
        elif self._state == self.STATE_ERROR:
            self._draw_message(self._error_message or "Error loading results")
        elif self._state == self.STATE_NO_API_KEY:
            self._draw_message("API key not configured")
        else:
            for card in self._cards:
                try:
                    card.draw()
                except Exception:
                    pass

        # Draw hover card on top
        if self._hover_card and self._hover_card._is_visible:
            try:
                self._hover_card.draw()
            except Exception:
                pass

    def _draw_rect(self, shader, x, y, w, h, color):
        """Draw a filled rectangle."""
        batch = batch_for_shader(
            shader, 'TRI_FAN',
            {"pos": [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]},
        )
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    def _draw_message(self, text: str):
        """Draw centered message in grid."""
        try:
            font_id = 0
            blf.size(font_id, 14)
            blf.color(font_id, *self._text_color)

            text_w, text_h = blf.dimensions(font_id, text)
            text_x = self.x_screen + (self.width - text_w) / 2
            text_y = self.y_screen + (self.height - text_h) / 2

            blf.position(font_id, text_x, text_y, 0)
            blf.draw(font_id, text)
        except Exception:
            pass

    def _draw_skeleton_cards(self, shader):
        """Draw skeleton loading cards with loading text."""
        cards_per_row = self._calculate_cards_per_row()

        for i in range(cards_per_row):
            card_x = self.x_screen + self._padding + i * (self._card_width + self._spacing)
            card_y = self.y_screen + (self.height - self._card_height) // 2

            # Card background
            self._draw_rect(shader, card_x, card_y, self._card_width, self._card_height, self._skeleton_color)

            # Image area
            img_y = card_y + 30
            img_size = self._card_width - 8
            darker = (self._skeleton_color[0] * 0.7, self._skeleton_color[1] * 0.7, self._skeleton_color[2] * 0.7, 1.0)
            self._draw_rect(shader, card_x + 4, img_y + 4, img_size, img_size, darker)

            # Loading text in center of image area
            self._draw_loading_text(card_x + 4 + img_size / 2, img_y + 4 + img_size / 2)

    def _draw_loading_text(self, cx, cy):
        """Draw loading text at position."""
        font_id = 0
        text = "Loading..."

        blf.size(font_id, 10)
        text_w, text_h = blf.dimensions(font_id, text)

        blf.color(font_id, 0.5, 0.5, 0.5, 1.0)
        blf.position(font_id, cx - text_w / 2, cy - text_h / 2, 0)
        blf.draw(font_id, text)

    def clear(self):
        """Clear all cards and reset state."""
        self._cards.clear()
        self._projects.clear()
        self._state = self.STATE_IDLE
        if self._hover_card:
            self._hover_card.hide()

    def _schedule_redraws(self, count=3):
        intervals = [0.05, 0.1, 0.2]
        for i in range(min(count, len(intervals))):
            try:
                bpy.app.timers.register(
                    lambda: self._force_redraw(),
                    first_interval=intervals[i]
                )
            except Exception:
                pass

    def _force_redraw(self):
        try:
            if bpy.context.area:
                bpy.context.area.tag_redraw()
        except Exception:
            pass
        return None

    def _register_download_tracker(self):
        """Register with the download tracker for progress updates."""
        try:
            from ..features.cache.download_tracker import get_download_tracker
            tracker = get_download_tracker()
            tracker.register_global_callback(self._on_download_progress)
        except Exception:
            pass

    def _on_download_progress(self, key: str, state):
        """Callback for download progress updates from tracker."""
        if key in self._card_map:
            card = self._card_map[key]
            card.is_downloading = state.is_active
            card.download_progress = state.progress
            self._force_redraw()

    def _update_card_download_state(self, card, nickname: str, slug: str):
        """Update card's download state from tracker."""
        try:
            from ..features.cache.download_tracker import get_download_tracker
            tracker = get_download_tracker()
            state = tracker.get_state(nickname, slug)
            card.is_downloading = state.is_active
            card.download_progress = state.progress
        except Exception:
            pass
