"""Toast notification widget for Blender GPU-based UI."""

import bpy
import blf
import gpu
import math
import os
import time
from gpu_extras.batch import batch_for_shader
from .bl_ui_widget import BL_UI_Widget
from .bl_ui_button import RADIUS_MD


class ToastType:
    """Toast type constants."""
    INFO = "info"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PROGRESS = "progress"


# Map toast types to icon file names (in src/icons/loaders/)
TOAST_ICONS = {
    ToastType.INFO: "info",
    ToastType.SUCCESS: "check",
    ToastType.ERROR: "x",
    ToastType.WARNING: "alert",
    ToastType.PROGRESS: "download",
}


# Color scheme for each toast type
TOAST_COLORS = {
    ToastType.INFO: {
        "bg": (0.12, 0.12, 0.12, 0.95),
        "accent": (0.5, 0.65, 0.9, 1.0),
        "text": (0.9, 0.9, 0.9, 1.0),
    },
    ToastType.SUCCESS: {
        "bg": (0.1, 0.14, 0.1, 0.95),
        "accent": (0.4, 0.75, 0.4, 1.0),
        "text": (0.9, 0.9, 0.9, 1.0),
    },
    ToastType.ERROR: {
        "bg": (0.16, 0.1, 0.1, 0.95),
        "accent": (0.9, 0.35, 0.35, 1.0),
        "text": (0.9, 0.9, 0.9, 1.0),
    },
    ToastType.WARNING: {
        "bg": (0.15, 0.13, 0.08, 0.95),
        "accent": (0.9, 0.7, 0.25, 1.0),
        "text": (0.9, 0.9, 0.9, 1.0),
    },
    ToastType.PROGRESS: {
        "bg": (0.12, 0.12, 0.12, 0.95),
        "accent": (0.4, 0.6, 0.9, 1.0),
        "text": (0.9, 0.9, 0.9, 1.0),
        "progress_bg": (0.06, 0.06, 0.06, 0.9),
        "progress_fill": (0.4, 0.6, 0.9, 1.0),
    },
}


class BL_UI_Toast(BL_UI_Widget):
    """Individual toast notification widget.

    Features:
    - Rounded corners
    - Type-based color scheme (info, success, error, warning, progress)
    - Optional progress bar for download toasts
    - Auto-calculated width based on text content
    """

    # Layout constants
    MIN_WIDTH = 180
    MAX_WIDTH = 500
    HEIGHT = 28
    PROGRESS_HEIGHT = 36
    PADDING_X = 10
    PADDING_Y = 6
    ICON_SIZE = 18
    ICON_MARGIN = 6
    PROGRESS_BAR_HEIGHT = 3
    BORDER_RADIUS = RADIUS_MD
    ACCENT_BAR_WIDTH = 3

    # Global texture cache for toast icons
    _texture_cache = {}

    @classmethod
    def _load_icon_texture(cls, icon_name):
        """Load PNG icon from loaders folder as GPU texture."""
        if icon_name in cls._texture_cache:
            return cls._texture_cache[icon_name]

        try:
            addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(addon_dir, "icons", "loaders", f"{icon_name}.png")

            if not os.path.exists(icon_path):
                print(f"⚠️  Toast icon not found: {icon_path}")
                cls._texture_cache[icon_name] = None
                return None

            img_name = f"__blendflare_toast_icon_{icon_name}__"

            if img_name in bpy.data.images:
                img = bpy.data.images[img_name]
            else:
                img = bpy.data.images.load(icon_path, check_existing=False)
                img.name = img_name
                img.colorspace_settings.name = 'Non-Color'

            texture = gpu.texture.from_image(img)
            cls._texture_cache[icon_name] = texture
            return texture

        except Exception as e:
            print(f"❌ Error loading toast icon {icon_name}: {e}")
            cls._texture_cache[icon_name] = None
            return None

    @classmethod
    def cleanup_textures(cls):
        """Clean up loaded textures (call on addon unregister)."""
        cls._texture_cache.clear()

        for img_name in list(bpy.data.images.keys()):
            if img_name.startswith("__blendflare_toast_icon_"):
                bpy.data.images.remove(bpy.data.images[img_name])

    def __init__(self, toast_id, message, toast_type=ToastType.INFO, duration=3.0):
        """Initialize toast widget.

        Args:
            toast_id: Unique identifier for this toast
            message: Text message to display
            toast_type: One of ToastType constants
            duration: Auto-dismiss time in seconds (0 = no auto-dismiss)
        """
        height = self.PROGRESS_HEIGHT if toast_type == ToastType.PROGRESS else self.HEIGHT
        super().__init__(0, 0, self.MIN_WIDTH, height)

        self._toast_id = toast_id
        self._message = message
        self._toast_type = toast_type
        self._duration = duration
        self._progress = 0.0
        self._created_at = time.time()
        self._opacity = 1.0

        self._calculate_width()

    @property
    def toast_id(self):
        return self._toast_id

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, value):
        self._message = value
        self._calculate_width()

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = max(0.0, min(1.0, value))

    @property
    def toast_type(self):
        return self._toast_type

    @toast_type.setter
    def toast_type(self, value):
        self._toast_type = value
        self.height = self.PROGRESS_HEIGHT if value == ToastType.PROGRESS else self.HEIGHT

    @property
    def is_expired(self):
        """Check if toast should be dismissed based on duration."""
        if self._duration <= 0:
            return False
        return (time.time() - self._created_at) >= self._duration

    @property
    def age(self):
        """Get toast age in seconds."""
        return time.time() - self._created_at

    def reset_timer(self):
        """Reset the auto-dismiss timer."""
        self._created_at = time.time()

    def _calculate_width(self):
        """Calculate toast width based on message length."""
        try:
            font_id = 0
            blf.size(font_id, 11)
            text_width, _ = blf.dimensions(font_id, self._message)

            # Width = accent + padding + icon + margin + text + padding
            width = self.ACCENT_BAR_WIDTH + self.PADDING_X + self.ICON_SIZE + self.ICON_MARGIN + text_width + self.PADDING_X
            self.width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, int(width)))
        except Exception:
            self.width = self.MIN_WIDTH

    def draw(self):
        """Draw the toast notification."""
        if not self._is_visible:
            return

        colors = TOAST_COLORS.get(self._toast_type, TOAST_COLORS[ToastType.INFO])

        # Apply opacity
        bg_color = (*colors["bg"][:3], colors["bg"][3] * self._opacity)
        accent_color = (*colors["accent"][:3], colors["accent"][3] * self._opacity)
        text_color = (*colors["text"][:3], colors["text"][3] * self._opacity)

        gpu.state.blend_set('ALPHA')

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Draw background
        self._draw_rounded_background(shader, bg_color)

        # Draw accent bar
        self._draw_accent_bar(shader, accent_color)

        # Draw icon
        self._draw_icon()

        # Draw text
        self._draw_text(text_color)

        # Draw progress bar if needed
        if self._toast_type == ToastType.PROGRESS:
            self._draw_progress_bar(shader, colors)

        gpu.state.blend_set('NONE')

    def _draw_rounded_background(self, shader, color):
        """Draw rounded rectangle background."""
        vertices = self._generate_rounded_rect_vertices(
            self.x_screen, self.y_screen,
            self.width, self.height,
            self.BORDER_RADIUS
        )
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    def _draw_accent_bar(self, shader, color):
        """Draw left accent bar."""
        bar_height = self.height - 6
        bar_x = self.x_screen + 3
        bar_y = self.y_screen + 3

        # Draw rounded accent bar
        vertices = self._generate_rounded_rect_vertices(
            bar_x, bar_y,
            self.ACCENT_BAR_WIDTH, bar_height,
            1
        )
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    def _draw_icon(self):
        """Draw icon from PNG texture based on toast type."""
        icon_name = TOAST_ICONS.get(self._toast_type, "info")
        texture = self._load_icon_texture(icon_name)

        if texture is None:
            return

        icon_x = self.x_screen + self.ACCENT_BAR_WIDTH + self.PADDING_X

        # Center icon vertically (adjust for progress bar)
        if self._toast_type == ToastType.PROGRESS:
            icon_y = self.y_screen + (self.height - self.PROGRESS_BAR_HEIGHT - self.ICON_SIZE) / 2 + self.PROGRESS_BAR_HEIGHT
        else:
            icon_y = self.y_screen + (self.height - self.ICON_SIZE) / 2

        try:
            img_shader = gpu.shader.from_builtin('IMAGE')

            batch = batch_for_shader(
                img_shader, 'TRI_FAN',
                {
                    "pos": [
                        (icon_x, icon_y),
                        (icon_x + self.ICON_SIZE, icon_y),
                        (icon_x + self.ICON_SIZE, icon_y + self.ICON_SIZE),
                        (icon_x, icon_y + self.ICON_SIZE)
                    ],
                    "texCoord": [(0, 0), (1, 0), (1, 1), (0, 1)]
                }
            )

            gpu.state.blend_set('ALPHA')
            img_shader.bind()
            img_shader.uniform_sampler("image", texture)
            batch.draw(img_shader)

        except Exception as e:
            print(f"❌ Error drawing toast icon: {e}")

    def _draw_text(self, color):
        """Draw toast message text."""
        font_id = 0
        blf.size(font_id, 11)
        blf.color(font_id, *color)

        # Calculate text position
        text_x = self.x_screen + self.ACCENT_BAR_WIDTH + self.PADDING_X + self.ICON_SIZE + self.ICON_MARGIN

        # Truncate text if needed
        max_text_width = self.width - self.ACCENT_BAR_WIDTH - self.PADDING_X - self.ICON_SIZE - self.ICON_MARGIN - self.PADDING_X
        display_text = self._truncate_text(self._message, max_text_width, font_id)

        _, text_height = blf.dimensions(font_id, display_text)

        if self._toast_type == ToastType.PROGRESS:
            text_y = self.y_screen + (self.height - self.PROGRESS_BAR_HEIGHT - text_height) / 2 + self.PROGRESS_BAR_HEIGHT
        else:
            text_y = self.y_screen + (self.height - text_height) / 2

        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, display_text)

    def _truncate_text(self, text, max_width, font_id):
        """Truncate text to fit within max_width."""
        width, _ = blf.dimensions(font_id, text)
        if width <= max_width:
            return text

        # Binary search for truncation point
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

        return result if result != text else text[:3] + "..."

    def _draw_progress_bar(self, shader, colors):
        """Draw progress bar at bottom of toast."""
        bar_margin = 8
        bar_x = self.x_screen + bar_margin
        bar_y = self.y_screen + 5
        bar_width = self.width - (bar_margin * 2)
        bar_height = self.PROGRESS_BAR_HEIGHT

        # Background
        bg_color = colors.get("progress_bg", (0.08, 0.08, 0.08, 0.9))
        bg_color = (*bg_color[:3], bg_color[3] * self._opacity)

        # Draw rounded background
        bg_vertices = self._generate_rounded_rect_vertices(bar_x, bar_y, bar_width, bar_height, 2)
        batch_bg = batch_for_shader(shader, 'TRI_FAN', {"pos": bg_vertices})
        shader.bind()
        shader.uniform_float("color", bg_color)
        batch_bg.draw(shader)

        # Fill
        if self._progress > 0:
            fill_color = colors.get("progress_fill", (0.3, 0.6, 1.0, 1.0))
            fill_color = (*fill_color[:3], fill_color[3] * self._opacity)
            fill_width = max(4, bar_width * self._progress)  # Min width for visibility

            fill_vertices = self._generate_rounded_rect_vertices(bar_x, bar_y, fill_width, bar_height, 2)
            batch_fill = batch_for_shader(shader, 'TRI_FAN', {"pos": fill_vertices})
            shader.uniform_float("color", fill_color)
            batch_fill.draw(shader)

    def _generate_rounded_rect_vertices(self, x, y, w, h, radius, segments=4):
        """Generate vertices for a rounded rectangle (TRI_FAN)."""
        vertices = []
        cx, cy = x + w / 2, y + h / 2
        vertices.append((cx, cy))

        seg = max(2, segments)
        radius = min(radius, w / 2, h / 2)

        # Bottom-left corner
        for i in range(seg + 1):
            angle = math.pi + (math.pi / 2) * (i / seg)
            vx = x + radius + radius * math.cos(angle)
            vy = y + radius + radius * math.sin(angle)
            vertices.append((vx, vy))

        # Bottom-right corner
        for i in range(seg + 1):
            angle = (3 * math.pi / 2) + (math.pi / 2) * (i / seg)
            vx = x + w - radius + radius * math.cos(angle)
            vy = y + radius + radius * math.sin(angle)
            vertices.append((vx, vy))

        # Top-right corner
        for i in range(seg + 1):
            angle = 0 + (math.pi / 2) * (i / seg)
            vx = x + w - radius + radius * math.cos(angle)
            vy = y + h - radius + radius * math.sin(angle)
            vertices.append((vx, vy))

        # Top-left corner
        for i in range(seg + 1):
            angle = (math.pi / 2) + (math.pi / 2) * (i / seg)
            vx = x + radius + radius * math.cos(angle)
            vy = y + h - radius + radius * math.sin(angle)
            vertices.append((vx, vy))

        # Close the shape
        vertices.append(vertices[1])

        return vertices
