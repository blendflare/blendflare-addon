import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from .bl_ui_widget import BL_UI_Widget
from .bl_ui_image import BL_UI_Image


class BL_UI_Card(BL_UI_Widget):
    """Card widget for displaying project preview with image and title."""

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self._title = ""
        self._image_url = None
        self._project_data = None
        self._is_hovered = False

        # Colors
        self._bg_color = (0.12, 0.12, 0.12, 0.95)
        self._hover_bg_color = (0.15, 0.15, 0.15, 0.95)
        self._title_bg_color = (0.08, 0.08, 0.08, 0.9)
        self._text_color = (0.95, 0.95, 0.95, 1.0)
        self._border_color = (0.3, 0.3, 0.3, 0.6)
        self._hover_border_color = (0.4, 0.6, 1.0, 0.8)

        # Progress bar colors
        self._progress_bg_color = (0.1, 0.1, 0.1, 0.9)
        self._progress_fill_color = (0.3, 0.6, 1.0, 1.0)  # Blue

        # Download state
        self._is_downloading = False
        self._download_progress = 0.0  # 0.0 to 1.0

        # Layout
        self._title_height = 30
        self._padding = 4
        self._progress_bar_height = 4

        # Image widget (square)
        image_size = width - (self._padding * 2)
        self._image = BL_UI_Image(
            x + self._padding,
            y + self._title_height + self._padding,
            image_size,
            image_size
        )
        self._image.aspect_ratio = 1.0

        # Callbacks
        self.on_click = None
        self.on_hover = None

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def image_url(self):
        return self._image_url

    @image_url.setter
    def image_url(self, value):
        if self._image_url != value:
            self._image_url = value
            self._image.image_url = value
            self._schedule_redraw()

    @property
    def project_data(self):
        return self._project_data

    @project_data.setter
    def project_data(self, value):
        self._project_data = value

    @property
    def is_downloading(self):
        return self._is_downloading

    @is_downloading.setter
    def is_downloading(self, value):
        self._is_downloading = value
        self._schedule_redraw()

    @property
    def download_progress(self):
        return self._download_progress

    @download_progress.setter
    def download_progress(self, value):
        self._download_progress = max(0.0, min(1.0, value))
        self._schedule_redraw()

    def update(self, x, y):
        """Update card and image positions."""
        super().update(x, y)

        image_size = self.width - (self._padding * 2)
        self._image.x_screen = x + self._padding
        self._image.y_screen = y + self._title_height + self._padding
        self._image.width = image_size
        self._image.height = image_size

    def handle_event(self, event):
        if not self._is_visible:
            return False

        x = event.mouse_region_x
        y = event.mouse_region_y

        was_hovered = self._is_hovered
        self._is_hovered = self.is_in_rect(x, y)

        if self._is_hovered != was_hovered:
            if self.on_hover and self._is_hovered:
                self.on_hover(self)
            return True

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self._is_hovered and self.on_click:
                self.on_click(self)
                return True

        return False

    def draw(self):
        if not self._is_visible:
            return

        bg = self._hover_bg_color if self._is_hovered else self._bg_color

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Background
        batch_bg = batch_for_shader(
            shader, 'TRI_FAN',
            {"pos": [
                (self.x_screen, self.y_screen),
                (self.x_screen + self.width, self.y_screen),
                (self.x_screen + self.width, self.y_screen + self.height),
                (self.x_screen, self.y_screen + self.height)
            ]},
        )
        shader.bind()
        shader.uniform_float("color", bg)
        batch_bg.draw(shader)

        # Image
        try:
            self._image.draw()
        except Exception:
            pass

        # Progress bar (drawn over the image at the bottom)
        if self._is_downloading:
            self._draw_progress_bar(shader)

        # Title background
        title_y = self.y_screen
        batch_title = batch_for_shader(
            shader, 'TRI_FAN',
            {"pos": [
                (self.x_screen, title_y),
                (self.x_screen + self.width, title_y),
                (self.x_screen + self.width, title_y + self._title_height),
                (self.x_screen, title_y + self._title_height)
            ]},
        )
        shader.uniform_float("color", self._title_bg_color)
        batch_title.draw(shader)

        # Title text
        if self._title:
            try:
                font_id = 0
                blf.size(font_id, 11)
                blf.color(font_id, *self._text_color)

                max_w = self.width - (self._padding * 2)
                text = self._truncate_text(self._title, max_w, font_id)

                _, text_h = blf.dimensions(font_id, text)
                text_x = self.x_screen + self._padding
                text_y = title_y + (self._title_height - text_h) / 2

                blf.position(font_id, text_x, text_y, 0)
                blf.draw(font_id, text)
            except Exception:
                pass

        # Border only on hover
        if self._is_hovered:
            x1, y1 = self.x_screen, self.y_screen
            x2, y2 = self.x_screen + self.width, self.y_screen + self.height
            batch_border = batch_for_shader(
                shader, 'LINES',
                {"pos": [
                    (x1, y1), (x2, y1),  # bottom
                    (x2, y1), (x2, y2),  # right
                    (x2, y2), (x1, y2),  # top
                    (x1, y2), (x1, y1),  # left
                ]},
            )
            shader.uniform_float("color", self._hover_border_color)
            batch_border.draw(shader)

    def _truncate_text(self, text, max_width, font_id):
        """Truncate text to fit within max_width."""
        width, _ = blf.dimensions(font_id, text)
        if width <= max_width:
            return text

        left, right = 0, len(text)
        result = text

        while left < right:
            mid = (left + right + 1) // 2
            truncated = text[:mid] + "..."
            w, _ = blf.dimensions(font_id, truncated)

            if w <= max_width:
                result = truncated
                left = mid
            else:
                right = mid - 1

        return result if result != text else text[:1] + "..."

    def _schedule_redraw(self):
        """Schedule redraw for image loading."""
        try:
            if bpy.context.area:
                bpy.context.area.tag_redraw()
                bpy.app.timers.register(
                    lambda: self._force_redraw(),
                    first_interval=0.1
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

    def _draw_progress_bar(self, shader):
        """Draw download progress bar at the bottom of the image area."""
        # Position: at the bottom of the image area
        image_bottom_y = self.y_screen + self._title_height + self._padding
        bar_y = image_bottom_y
        bar_x = self.x_screen + self._padding
        bar_width = self.width - (self._padding * 2)
        bar_height = self._progress_bar_height

        # Background bar (dark)
        batch_bg = batch_for_shader(
            shader, 'TRI_FAN',
            {"pos": [
                (bar_x, bar_y),
                (bar_x + bar_width, bar_y),
                (bar_x + bar_width, bar_y + bar_height),
                (bar_x, bar_y + bar_height)
            ]},
        )
        shader.uniform_float("color", self._progress_bg_color)
        batch_bg.draw(shader)

        # Progress fill (blue)
        if self._download_progress > 0:
            fill_width = bar_width * self._download_progress
            batch_fill = batch_for_shader(
                shader, 'TRI_FAN',
                {"pos": [
                    (bar_x, bar_y),
                    (bar_x + fill_width, bar_y),
                    (bar_x + fill_width, bar_y + bar_height),
                    (bar_x, bar_y + bar_height)
                ]},
            )
            shader.uniform_float("color", self._progress_fill_color)
            batch_fill.draw(shader)
