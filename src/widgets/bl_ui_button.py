import bpy
import blf
import gpu
import math
from gpu_extras.batch import batch_for_shader
from .bl_ui_widget import BL_UI_Widget
import os


# Border radius presets
RADIUS_NONE = 0
RADIUS_SM = 2
RADIUS_MD = 4
RADIUS_LG = 6
RADIUS_XL = 8
RADIUS_FULL = 999  # Will be calculated as min(width, height) / 2


# Global tooltip state for rendering on top of all widgets
_active_tooltip = None  # (text, x, y)


def get_active_tooltip():
    """Get the currently active tooltip to render."""
    return _active_tooltip


def clear_active_tooltip():
    """Clear the active tooltip."""
    global _active_tooltip
    _active_tooltip = None


def draw_global_tooltip():
    """Draw the active tooltip on top of everything."""
    global _active_tooltip
    if not _active_tooltip:
        return

    text, tooltip_x, tooltip_y = _active_tooltip

    font_id = 0
    blf.size(font_id, 11)

    tooltip_width, tooltip_height = blf.dimensions(font_id, text)
    padding = 6

    tooltip_w = tooltip_width + padding * 2
    tooltip_h = tooltip_height + padding * 2

    # Tooltip background
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(
        shader, 'TRI_FAN',
        {"pos": [
            (tooltip_x, tooltip_y),
            (tooltip_x + tooltip_w, tooltip_y),
            (tooltip_x + tooltip_w, tooltip_y + tooltip_h),
            (tooltip_x, tooltip_y + tooltip_h)
        ]},
    )
    shader.bind()
    shader.uniform_float("color", (0.1, 0.1, 0.1, 0.95))
    batch.draw(shader)

    # Tooltip text
    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
    blf.position(font_id, tooltip_x + padding, tooltip_y + padding, 0)
    blf.draw(font_id, text)


class BL_UI_Button(BL_UI_Widget):
    """Button widget with hover, press states, and icon support"""

    # Cache global de texturas GPU
    _texture_cache = {}

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self._text = "Button"
        self._text_size = 12
        self._text_color = (1.0, 1.0, 1.0, 1.0)
        self._icon = None
        self._is_pressed = False
        self._hover_bg_color = (0.3, 0.3, 0.3, 0.9)
        self._press_bg_color = (0.15, 0.15, 0.15, 0.9)
        self._is_hovered = False
        self.mouse_down_func = None
        self.mouse_up_func = None
        self._border_radius = RADIUS_NONE  # Default: no radius
        self.selected = False
        self._selected_bg_color = (0.2, 0.4, 0.8, 0.9)
        self._tooltip = None

    @property
    def border_radius(self):
        return self._border_radius

    @border_radius.setter
    def border_radius(self, value):
        self._border_radius = value
        
    @property
    def text(self):
        return self._text
    
    @text.setter
    def text(self, value):
        self._text = value
        
    @property
    def icon(self):
        return self._icon
    
    @icon.setter 
    def icon(self, value):
        """Set icon by name (without .png extension)"""
        self._icon = value
        if value and value not in self._texture_cache:
            self._load_icon_texture(value)
    
    @classmethod
    def _load_icon_texture(cls, icon_name):
        """Load PNG icon as GPU texture.

        Supports paths with '/' for subfolders, e.g. 'categories/architecture'
        """
        try:
            # Get addon path (subir 2 niveles desde widgets/)
            addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # Support subfolder paths like 'categories/architecture'
            icon_path = os.path.join(addon_dir, "icons", *icon_name.split('/')) + ".png"
            
            print(f"🔍 Looking for icon: {icon_path}")
            
            if not os.path.exists(icon_path):
                print(f"⚠️  Icon not found: {icon_path}")
                cls._texture_cache[icon_name] = None
                return
            
            # Load image in Blender (usar nombre único para evitar conflictos)
            img_name = f"__blendflare_icon_{icon_name}__"
            
            # Check if already loaded
            if img_name in bpy.data.images:
                img = bpy.data.images[img_name]
                print(f"♻️  Icon already loaded: {icon_name}")
            else:
                img = bpy.data.images.load(icon_path, check_existing=False)
                img.name = img_name
                img.colorspace_settings.name = 'Non-Color'  # Importante para iconos
                print(f"✓ Icon loaded: {icon_name}")
            
            # Crear textura GPU desde la imagen
            # NO usar bindcode, sino gpu.texture.from_image()
            texture = gpu.texture.from_image(img)
            cls._texture_cache[icon_name] = texture
            
        except Exception as e:
            print(f"❌ Error loading icon {icon_name}: {e}")
            import traceback
            traceback.print_exc()
            cls._texture_cache[icon_name] = None
    
    @property
    def tooltip(self):
        return self._tooltip
    
    @tooltip.setter
    def tooltip(self, value):
        self._tooltip = value
        
    @property
    def text_size(self):
        return self._text_size
    
    @text_size.setter
    def text_size(self, value):
        self._text_size = value
        
    def set_mouse_down(self, mouse_down_func):
        self.mouse_down_func = mouse_down_func
        
    def set_mouse_up(self, mouse_up_func):
        self.mouse_up_func = mouse_up_func
        
    def handle_event(self, event):
        if not self._is_visible:
            return False

        x = event.mouse_region_x
        y = event.mouse_region_y

        if event.type == 'MOUSEMOVE':
            was_hovered = self._is_hovered
            self._is_hovered = self.is_in_rect(x, y)
            # Return True if hover state changed to force redraw
            if was_hovered != self._is_hovered:
                return True
            return False
            
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                if self.is_in_rect(x, y):
                    self._is_pressed = True
                    if self.mouse_down_func:
                        try:
                            self.mouse_down_func(self)
                        except Exception as e:
                            print(f"Error in button down callback: {e}")
                    return True
            else:  # RELEASE
                if self._is_pressed:
                    self._is_pressed = False
                    if self.is_in_rect(x, y):
                        if self.mouse_up_func:
                            try:
                                self.mouse_up_func(self)
                            except Exception as e:
                                print(f"Error in button up callback: {e}")
                    return True
                
        return False
        
    def draw(self):
        if not self._is_visible:
            return
            
        # Determine background color based on state
        if self._is_pressed:
            bg_color = self._press_bg_color
        elif self.selected:
            bg_color = self._selected_bg_color
        elif self._is_hovered:
            bg_color = self._hover_bg_color
        else:
            bg_color = self._bg_color
            
        # Draw background
        self._draw_rounded_box(bg_color)
        
        # Draw icon if exists
        if self._icon:
            self._draw_icon()
        
        # Draw text
        if self._text:
            self._draw_text()
            
        # Register tooltip for global rendering (on top of everything)
        if self._is_hovered and self._tooltip:
            self._register_tooltip()
    
    def _draw_rounded_box(self, color):
        """Draw background with optional rounded corners"""
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Calculate actual radius
        radius = self._border_radius
        if radius == RADIUS_FULL:
            radius = min(self.width, self.height) / 2
        else:
            # Clamp radius to half of smallest dimension
            radius = min(radius, self.width / 2, self.height / 2)

        # If no radius, draw simple rectangle
        if radius <= 0:
            batch = batch_for_shader(
                shader, 'TRI_FAN',
                {"pos": [
                    (self.x_screen, self.y_screen),
                    (self.x_screen + self.width, self.y_screen),
                    (self.x_screen + self.width, self.y_screen + self.height),
                    (self.x_screen, self.y_screen + self.height)
                ]},
            )
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
        else:
            # Draw rounded rectangle using triangles
            vertices = self._generate_rounded_rect_vertices(
                self.x_screen, self.y_screen,
                self.width, self.height, radius
            )
            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)

        # Draw border when selected
        if self.selected:
            border_color = (0.3, 0.5, 1.0, 1.0)
            if radius <= 0:
                x1, y1 = self.x_screen, self.y_screen
                x2, y2 = self.x_screen + self.width, self.y_screen + self.height
                batch_border = batch_for_shader(
                    shader, 'LINES',
                    {"pos": [
                        (x1, y1), (x2, y1),
                        (x2, y1), (x2, y2),
                        (x2, y2), (x1, y2),
                        (x1, y2), (x1, y1),
                    ]},
                )
                shader.uniform_float("color", border_color)
                batch_border.draw(shader)
            else:
                # Draw rounded border
                border_vertices = self._generate_rounded_rect_border_vertices(
                    self.x_screen, self.y_screen,
                    self.width, self.height, radius
                )
                batch_border = batch_for_shader(shader, 'LINES', {"pos": border_vertices})
                shader.uniform_float("color", border_color)
                batch_border.draw(shader)

    def _generate_rounded_rect_vertices(self, x, y, w, h, radius, segments=6):
        """Generate vertices for a rounded rectangle (TRI_FAN)"""
        vertices = []
        # Center point for TRI_FAN
        cx, cy = x + w / 2, y + h / 2
        vertices.append((cx, cy))

        # Number of segments per corner
        seg = max(2, segments)

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

    def _generate_rounded_rect_border_vertices(self, x, y, w, h, radius, segments=6):
        """Generate vertices for rounded rectangle border (LINES)"""
        points = []
        seg = max(2, segments)

        # Bottom-left corner
        for i in range(seg + 1):
            angle = math.pi + (math.pi / 2) * (i / seg)
            vx = x + radius + radius * math.cos(angle)
            vy = y + radius + radius * math.sin(angle)
            points.append((vx, vy))

        # Bottom-right corner
        for i in range(seg + 1):
            angle = (3 * math.pi / 2) + (math.pi / 2) * (i / seg)
            vx = x + w - radius + radius * math.cos(angle)
            vy = y + radius + radius * math.sin(angle)
            points.append((vx, vy))

        # Top-right corner
        for i in range(seg + 1):
            angle = 0 + (math.pi / 2) * (i / seg)
            vx = x + w - radius + radius * math.cos(angle)
            vy = y + h - radius + radius * math.sin(angle)
            points.append((vx, vy))

        # Top-left corner
        for i in range(seg + 1):
            angle = (math.pi / 2) + (math.pi / 2) * (i / seg)
            vx = x + radius + radius * math.cos(angle)
            vy = y + h - radius + radius * math.sin(angle)
            points.append((vx, vy))

        # Convert to line segments
        vertices = []
        for i in range(len(points)):
            vertices.append(points[i])
            vertices.append(points[(i + 1) % len(points)])

        return vertices
    
    def _draw_icon(self):
        """Draw icon from PNG texture"""
        if not self._icon or self._icon not in self._texture_cache:
            return
        
        texture = self._texture_cache[self._icon]
        if texture is None:
            return
        
        try:
            # Icon size and position (centered in button)
            icon_size = 18
            icon_x = self.x_screen + (self.width - icon_size) / 2
            icon_y = self.y_screen + (self.height - icon_size) / 2
            
            # Prepare shader
            shader = gpu.shader.from_builtin('IMAGE')
            
            batch = batch_for_shader(
                shader, 'TRI_FAN',
                {
                    "pos": [
                        (icon_x, icon_y),
                        (icon_x + icon_size, icon_y),
                        (icon_x + icon_size, icon_y + icon_size),
                        (icon_x, icon_y + icon_size)
                    ],
                    "texCoord": [(0, 0), (1, 0), (1, 1), (0, 1)]
                }
            )
            
            # Enable alpha blending
            gpu.state.blend_set('ALPHA')
            
            shader.bind()
            shader.uniform_sampler("image", texture)
            batch.draw(shader)
            
            gpu.state.blend_set('NONE')
            
        except Exception as e:
            print(f"❌ Error drawing icon {self._icon}: {e}")
    
    def _draw_text(self):
        """Draw button text, offset if icon exists"""
        font_id = 0
        blf.size(font_id, self._text_size)
        blf.color(font_id, *self._text_color)
        
        text_width, text_height = blf.dimensions(font_id, self._text)
        
        # Offset if there's an icon
        offset_x = 24 if self._icon else 0
        
        text_x = self.x_screen + (self.width - text_width) / 2 + offset_x / 2
        text_y = self.y_screen + (self.height - text_height) / 2
        
        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, self._text)
    
    def _register_tooltip(self):
        """Register tooltip for global rendering on top of everything."""
        global _active_tooltip
        if not self._tooltip:
            return

        # Position tooltip below button (to avoid being clipped by Blender's header)
        font_id = 0
        blf.size(font_id, 11)
        _, tooltip_height = blf.dimensions(font_id, self._tooltip)
        padding = 6
        tooltip_h = tooltip_height + padding * 2

        tooltip_x = self.x_screen
        tooltip_y = self.y_screen - tooltip_h - 4

        _active_tooltip = (self._tooltip, tooltip_x, tooltip_y)
    
    @classmethod
    def cleanup_textures(cls):
        """Clean up loaded textures (call on addon unregister)"""
        print("🧹 Cleaning up icon textures...")
        
        # Clear texture cache
        cls._texture_cache.clear()
        
        # Clean up loaded images
        for img_name in list(bpy.data.images.keys()):
            if img_name.startswith("__blendflare_icon_"):
                bpy.data.images.remove(bpy.data.images[img_name])
                print(f"  ✓ Removed: {img_name}")