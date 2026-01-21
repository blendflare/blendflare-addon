import bpy
import gpu
import blf
import math
from gpu_extras.batch import batch_for_shader
from .bl_ui_widget import BL_UI_Widget
from .bl_ui_button import RADIUS_NONE, RADIUS_FULL, draw_global_tooltip, clear_active_tooltip


class BL_UI_Drag_Panel(BL_UI_Widget):
    """Draggable panel that can contain other widgets"""

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self._widgets = []
        self._is_dragging = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._title = ""
        self._title_height = 30
        self._shadow_offset = 6
        self._shadow_color = (0.0, 0.0, 0.0, 0.4)
        self._border_radius = RADIUS_NONE  # Default: no radius

    @property
    def border_radius(self):
        return self._border_radius

    @border_radius.setter
    def border_radius(self, value):
        self._border_radius = value
        
    @property
    def title(self):
        return self._title
    
    @title.setter
    def title(self, value):
        self._title = value
        
    def add_widget(self, widget):
        """Add a child widget to this panel"""
        self._widgets.append(widget)
        # Initialize child widget position relative to panel
        widget.x_screen = self.x_screen + widget.x
        widget.y_screen = self.y_screen + widget.y
        
    def remove_widget(self, widget):
        """Remove a child widget from this panel"""
        if widget in self._widgets:
            self._widgets.remove(widget)
    
    def get_widget_by_tag(self, tag):
        """Get a widget by its tag"""
        for widget in self._widgets:
            if hasattr(widget, 'tag') and widget.tag == tag:
                return widget
        return None
        
    def handle_event(self, event):
        if not self._is_visible:
            return False
            
        x = event.mouse_region_x
        y = event.mouse_region_y
        
        # Pass event to child widgets first (they have priority)
        for widget in self._widgets:
            if widget.handle_event(event):
                return True
        
        # Check if dragging the panel (top drag zone)
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                # Use title_height if set, otherwise use a default drag zone of 35px
                drag_zone_height = self._title_height if self._title_height > 0 else 35
                drag_y_min = self.y_screen + self.height - drag_zone_height
                drag_y_max = self.y_screen + self.height

                if (self.x_screen <= x <= (self.x_screen + self.width)) and \
                   (drag_y_min <= y <= drag_y_max):
                    self._is_dragging = True
                    self._drag_offset_x = x - self.x_screen
                    self._drag_offset_y = y - self.y_screen
                    return True
            else:  # RELEASE
                if self._is_dragging:
                    self._is_dragging = False
                    return True
                
        if event.type == 'MOUSEMOVE':
            if self._is_dragging:
                new_x = x - self._drag_offset_x
                new_y = y - self._drag_offset_y
                self.update(new_x, new_y)
                return True
                
        return False
        
    def update(self, x, y):
        """Update panel and child widget positions"""
        # Calculate the delta movement
        delta_x = x - self.x_screen
        delta_y = y - self.y_screen
        
        # Update panel position
        self.x_screen = x
        self.y_screen = y
        
        # Update all child widgets recursively
        for widget in self._widgets:
            # Update widget screen position
            widget.x_screen += delta_x
            widget.y_screen += delta_y
            
            # If widget has its own update method (like grid), call it
            if hasattr(widget, 'update') and callable(widget.update):
                try:
                    widget.update(widget.x_screen, widget.y_screen)
                except Exception as e:
                    print(f"⚠️  Error updating widget: {e}")
            
    def center_on_screen(self, area_width, area_height):
        """Center the panel on screen"""
        x = (area_width - self.width) / 2
        y = (area_height - self.height) / 2
        self.update(x, y)
            
    def draw(self):
        if not self._is_visible:
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Calculate actual radius
        radius = self._border_radius
        if radius == RADIUS_FULL:
            radius = min(self.width, self.height) / 2
        else:
            radius = min(radius, self.width / 2, self.height / 2)

        # Draw panel background
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
        else:
            vertices = self._generate_rounded_rect_vertices(
                self.x_screen, self.y_screen,
                self.width, self.height, radius
            )
            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})

        shader.uniform_float("color", self._bg_color)
        batch.draw(shader)

        # Draw title bar if title is set
        if self._title:
            title_bar_y = self.y_screen + self.height - self._title_height
            title_color = (0.15, 0.15, 0.15, 0.95)

            # Title bar with rounded top corners only
            if radius > 0:
                title_vertices = self._generate_rounded_rect_vertices(
                    self.x_screen, title_bar_y,
                    self.width, self._title_height, radius,
                    round_bottom=False
                )
                title_batch = batch_for_shader(shader, 'TRI_FAN', {"pos": title_vertices})
            else:
                title_batch = batch_for_shader(
                    shader, 'TRI_FAN',
                    {"pos": [
                        (self.x_screen, title_bar_y),
                        (self.x_screen + self.width, title_bar_y),
                        (self.x_screen + self.width, self.y_screen + self.height),
                        (self.x_screen, self.y_screen + self.height)
                    ]},
                )
            shader.uniform_float("color", title_color)
            title_batch.draw(shader)

            # Draw title text
            font_id = 0
            blf.size(font_id, 14)
            blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
            text_width, text_height = blf.dimensions(font_id, self._title)
            text_x = self.x_screen + (self.width - text_width) / 2
            text_y = title_bar_y + (self._title_height - text_height) / 2
            blf.position(font_id, text_x, text_y, 0)
            blf.draw(font_id, self._title)

        # Clear any previous tooltip before drawing widgets
        clear_active_tooltip()

        # Draw child widgets
        for widget in self._widgets:
            widget.draw()

        # Draw tooltips on top of everything (after all widgets)
        draw_global_tooltip()

    def _generate_rounded_rect_vertices(self, x, y, w, h, radius, segments=8, round_bottom=True):
        """Generate vertices for a rounded rectangle (TRI_FAN)"""
        vertices = []
        # Center point for TRI_FAN
        cx, cy = x + w / 2, y + h / 2
        vertices.append((cx, cy))

        seg = max(2, segments)

        if round_bottom:
            # Bottom-left corner (rounded)
            for i in range(seg + 1):
                angle = math.pi + (math.pi / 2) * (i / seg)
                vx = x + radius + radius * math.cos(angle)
                vy = y + radius + radius * math.sin(angle)
                vertices.append((vx, vy))

            # Bottom-right corner (rounded)
            for i in range(seg + 1):
                angle = (3 * math.pi / 2) + (math.pi / 2) * (i / seg)
                vx = x + w - radius + radius * math.cos(angle)
                vy = y + radius + radius * math.sin(angle)
                vertices.append((vx, vy))
        else:
            # Bottom-left corner (square)
            vertices.append((x, y))
            # Bottom-right corner (square)
            vertices.append((x + w, y))

        # Top-right corner (rounded)
        for i in range(seg + 1):
            angle = 0 + (math.pi / 2) * (i / seg)
            vx = x + w - radius + radius * math.cos(angle)
            vy = y + h - radius + radius * math.sin(angle)
            vertices.append((vx, vy))

        # Top-left corner (rounded)
        for i in range(seg + 1):
            angle = (math.pi / 2) + (math.pi / 2) * (i / seg)
            vx = x + radius + radius * math.cos(angle)
            vy = y + h - radius + radius * math.sin(angle)
            vertices.append((vx, vy))

        # Close the shape
        vertices.append(vertices[1])

        return vertices