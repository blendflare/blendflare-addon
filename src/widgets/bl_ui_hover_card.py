import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from .bl_ui_widget import BL_UI_Widget
from .bl_ui_image import BL_UI_Image


# Color palette for avatar fallback based on first letter
AVATAR_COLORS = {
    'A': (0.96, 0.26, 0.21, 1.0),  # Red
    'B': (0.91, 0.12, 0.39, 1.0),  # Pink
    'C': (0.61, 0.15, 0.69, 1.0),  # Purple
    'D': (0.40, 0.23, 0.72, 1.0),  # Deep Purple
    'E': (0.25, 0.32, 0.71, 1.0),  # Indigo
    'F': (0.13, 0.59, 0.95, 1.0),  # Blue
    'G': (0.01, 0.66, 0.96, 1.0),  # Light Blue
    'H': (0.00, 0.74, 0.83, 1.0),  # Cyan
    'I': (0.00, 0.59, 0.53, 1.0),  # Teal
    'J': (0.30, 0.69, 0.31, 1.0),  # Green
    'K': (0.55, 0.76, 0.29, 1.0),  # Light Green
    'L': (0.80, 0.86, 0.22, 1.0),  # Lime
    'M': (1.00, 0.93, 0.23, 1.0),  # Yellow
    'N': (1.00, 0.76, 0.03, 1.0),  # Amber
    'O': (1.00, 0.60, 0.00, 1.0),  # Orange
    'P': (1.00, 0.34, 0.13, 1.0),  # Deep Orange
    'Q': (0.47, 0.33, 0.28, 1.0),  # Brown
    'R': (0.62, 0.62, 0.62, 1.0),  # Grey
    'S': (0.38, 0.49, 0.55, 1.0),  # Blue Grey
    'T': (0.96, 0.26, 0.21, 1.0),  # Red
    'U': (0.91, 0.12, 0.39, 1.0),  # Pink
    'V': (0.61, 0.15, 0.69, 1.0),  # Purple
    'W': (0.40, 0.23, 0.72, 1.0),  # Deep Purple
    'X': (0.25, 0.32, 0.71, 1.0),  # Indigo
    'Y': (0.13, 0.59, 0.95, 1.0),  # Blue
    'Z': (0.01, 0.66, 0.96, 1.0),  # Light Blue
}


def _get_avatar_color(nickname: str) -> tuple:
    """Get a color based on the first letter of the nickname."""
    if not nickname:
        return (0.5, 0.5, 0.5, 1.0)  # Default grey
    first_char = nickname[0].upper()
    return AVATAR_COLORS.get(first_char, (0.5, 0.5, 0.5, 1.0))


class BL_UI_Hover_Card(BL_UI_Widget):
    """Expanded hover card showing detailed project information."""

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self._project = None
        self._is_visible = False

        # Colors
        self._bg_color = (0.12, 0.12, 0.12, 0.98)
        self._border_color = (0.3, 0.3, 0.3, 0.8)
        self._text_color = (0.95, 0.95, 0.95, 1.0)
        self._label_color = (0.75, 0.75, 0.75, 1.0)
        self._title_bg_color = (0.08, 0.08, 0.08, 0.95)
        self._tag_bg_color = (0.2, 0.2, 0.2, 0.9)

        # Layout
        self._padding = 10
        self._avatar_size = 32
        self._title_area_height = 50
        self._info_line_height = 15
        self._tags_height = 20

        # Image widget (16:9 aspect ratio)
        image_width = width - (self._padding * 2)
        self._image_height = int(image_width * 9 / 16)
        self._image = BL_UI_Image(
            x + self._padding,
            y + height - self._image_height - self._padding,
            image_width,
            self._image_height
        )

        # Avatar image widget
        self._avatar = BL_UI_Image(0, 0, self._avatar_size, self._avatar_size)

        # Recalculate total height based on content
        self._recalculate_height()

    def _recalculate_height(self):
        """Calculate proper height for all content."""
        info_lines = 5  # 5 rows of info
        info_height = info_lines * self._info_line_height
        total = (
            self._padding +  # top padding
            self._image_height +  # preview image
            self._padding +  # space after image
            self._title_area_height +  # title + author area
            self._padding // 2 +  # small space after title
            info_height +  # info lines
            self._padding // 2 +  # space before tags
            self._tags_height +  # tags row
            self._padding // 2  # bottom padding
        )
        self.height = total

    @property
    def project(self):
        return self._project

    @project.setter
    def project(self, value):
        """Set project data and update display."""
        self._project = value
        if value:
            try:
                self._image.image_url = value.preview_image
            except Exception:
                pass
            try:
                self._avatar.image_url = value.author.avatar_url
            except Exception:
                pass

    def show_at(self, x, y, project):
        """Show hover card at specific position with project data."""
        self._project = project
        self.project = project
        self.update(x, y)
        self._is_visible = True

    def hide(self):
        """Hide hover card."""
        self._is_visible = False

    def update(self, x, y):
        """Update positions."""
        super().update(x, y)
        image_width = self.width - (self._padding * 2)
        self._image.x_screen = x + self._padding
        self._image.y_screen = y + self.height - self._image_height - self._padding
        self._image.width = image_width
        self._image.height = self._image_height

    def draw(self):
        if not self._is_visible or not self._project:
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Background
        self._draw_rect(shader, self.x_screen, self.y_screen,
                        self.width, self.height, self._bg_color)

        # Preview image
        self._image.draw()

        # Title area background (below image)
        title_y = self._image.y_screen - self._padding - self._title_area_height
        self._draw_rect(shader, self.x_screen + self._padding, title_y,
                        self.width - self._padding * 2, self._title_area_height,
                        self._title_bg_color)

        # Draw title and author section
        self._draw_title_section(title_y)

        # Draw info section
        self._draw_info_section(title_y)

        # Draw tags at bottom
        self._draw_tags_section(shader)

    def _draw_rect(self, shader, x, y, w, h, color):
        """Draw a filled rectangle."""
        batch = batch_for_shader(
            shader, 'TRI_FAN',
            {"pos": [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]},
        )
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    def _draw_title_section(self, base_y):
        """Draw title and author with avatar."""
        if not self._project:
            return

        font_id = 0
        content_x = self.x_screen + self._padding * 2
        content_width = self.width - self._padding * 4

        # Avatar on the left side
        avatar_x = content_x
        avatar_y = base_y + (self._title_area_height - self._avatar_size) / 2
        self._avatar.x_screen = int(avatar_x)
        self._avatar.y_screen = int(avatar_y)
        self._avatar.width = self._avatar_size
        self._avatar.height = self._avatar_size

        # Check if we should draw fallback avatar (error or no URL)
        nickname = ""
        try:
            nickname = self._project.author.nickname
        except Exception:
            pass

        should_draw_fallback = (
            self._avatar.has_error or
            not self._avatar.image_url or
            (self._avatar.is_loading and not self._avatar.is_ready)
        )

        if should_draw_fallback and nickname:
            self._draw_avatar_fallback(int(avatar_x), int(avatar_y), nickname)
        else:
            self._avatar.draw()

        # Text area (to the right of avatar)
        text_x = avatar_x + self._avatar_size + 10
        text_width = content_width - self._avatar_size - 10

        # Title (larger, top)
        try:
            title = self._project.project_info.title
            blf.size(font_id, 12)
            blf.color(font_id, *self._text_color)
            truncated_title = self._truncate_text(title, text_width, font_id)
            title_y = base_y + self._title_area_height - 18
            blf.position(font_id, text_x, title_y, 0)
            blf.draw(font_id, truncated_title)
        except Exception:
            pass

        # Author name (below title)
        try:
            author = self._project.author.nickname
            blf.size(font_id, 10)
            blf.color(font_id, *self._label_color)
            author_text_y = base_y + 10
            blf.position(font_id, text_x, author_text_y, 0)
            blf.draw(font_id, f"by {author}")
        except Exception:
            pass

    def _draw_avatar_fallback(self, x, y, nickname):
        """Draw a fallback avatar with the first letter of the nickname."""
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Get color based on nickname
        bg_color = _get_avatar_color(nickname)

        # Draw circular-ish background (actually a rounded square approximation)
        self._draw_rect(shader, x, y, self._avatar_size, self._avatar_size, bg_color)

        # Draw the initial letter
        font_id = 0
        initial = nickname[0].upper() if nickname else "?"

        blf.size(font_id, 16)
        text_w, text_h = blf.dimensions(font_id, initial)

        text_x = x + (self._avatar_size - text_w) / 2
        text_y = y + (self._avatar_size - text_h) / 2

        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)  # White text
        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, initial)

    def _draw_info_section(self, title_base_y):
        """Draw project info below title section."""
        if not self._project:
            return

        font_id = 0
        line_height = self._info_line_height
        content_x = self.x_screen + self._padding

        # Start below title area
        current_y = title_base_y - self._padding // 2 - line_height

        # Info items in two columns
        left_col_x = content_x
        right_col_x = self.x_screen + self.width / 2

        # Row 1: License | Polygons
        try:
            license_type = self._project.legal.license_type.upper()
            self._draw_info_item(font_id, "License", license_type, left_col_x, current_y)
        except Exception:
            pass

        try:
            poly_count = self._project.file_info.poly_count
            poly_str = f"{poly_count:,}" if poly_count > 0 else "N/A"
            self._draw_info_item(font_id, "Polygons", poly_str, right_col_x, current_y)
        except Exception:
            pass

        current_y -= line_height

        # Row 2: Size | Category
        try:
            size_mb = self._project.file_info.file_size_mb
            self._draw_info_item(font_id, "Size", f"{size_mb:.1f} MB", left_col_x, current_y)
        except Exception:
            pass

        try:
            category = self._project.category.replace('_', ' ').title()
            self._draw_info_item(font_id, "Category", category, right_col_x, current_y)
        except Exception:
            pass

        current_y -= line_height

        # Row 3: Blender | Render Engine
        try:
            blender_ver = self._project.technical_specs.blender_version.full_version
            self._draw_info_item(font_id, "Blender", blender_ver, left_col_x, current_y)
        except Exception:
            pass

        try:
            render_engine = self._project.technical_specs.render_engine.title()
            self._draw_info_item(font_id, "Render", render_engine, right_col_x, current_y)
        except Exception:
            pass

        current_y -= line_height

        # Row 4: Subcategory | Stats
        try:
            subcategory = self._project.subcategory.replace('_', ' ').title()
            self._draw_info_item(font_id, "Subcat", subcategory, left_col_x, current_y)
        except Exception:
            pass

        try:
            views = self._project.stats.views_count
            downloads = self._project.stats.downloads_count
            likes = self._project.stats.likes_count
            stats_str = f"👁 {views} | ⬇ {downloads} | ♥ {likes}"
            self._draw_info_item(font_id, "Stats", stats_str, right_col_x, current_y)
        except Exception:
            pass

    def _draw_tags_section(self, shader):
        """Draw tags at the bottom of the card."""
        if not self._project:
            return

        try:
            tags = self._project.project_info.tags[:3]  # Max 3 tags
            if not tags:
                return
        except Exception:
            return

        font_id = 0
        blf.size(font_id, 9)

        tag_x = self.x_screen + self._padding
        tag_y = self.y_screen + self._padding // 2
        tag_padding_h = 6
        tag_padding_v = 3
        tag_spacing = 6

        for tag in tags:
            tag_w, tag_h = blf.dimensions(font_id, tag)
            box_w = tag_w + tag_padding_h * 2
            box_h = tag_h + tag_padding_v * 2

            # Check if tag fits
            if tag_x + box_w > self.x_screen + self.width - self._padding:
                break

            # Draw tag background
            self._draw_rect(shader, tag_x, tag_y, box_w, box_h, self._tag_bg_color)

            # Draw tag text
            blf.color(font_id, *self._label_color)
            blf.position(font_id, tag_x + tag_padding_h, tag_y + tag_padding_v, 0)
            blf.draw(font_id, tag)

            tag_x += box_w + tag_spacing

    def _draw_info_item(self, font_id, label, value, x, y):
        """Draw a label: value pair."""
        blf.size(font_id, 9)

        # Label
        blf.color(font_id, *self._label_color)
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, f"{label}:")

        # Value
        label_w, _ = blf.dimensions(font_id, f"{label}: ")
        blf.color(font_id, *self._text_color)
        blf.position(font_id, x + label_w, y, 0)
        blf.draw(font_id, str(value))

    def _truncate_text(self, text, max_width, font_id):
        """Truncate text to fit within max_width."""
        text_width, _ = blf.dimensions(font_id, text)

        if text_width <= max_width:
            return text

        left, right = 0, len(text)
        result = text

        while left < right:
            mid = (left + right + 1) // 2
            truncated = text[:mid] + "..."
            width, _ = blf.dimensions(font_id, truncated)

            if width <= max_width:
                result = truncated
                left = mid
            else:
                right = mid - 1

        return result if result != text else text[:1] + "..."
