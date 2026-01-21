import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from .bl_ui_widget import BL_UI_Widget


class BL_UI_Panel(BL_UI_Widget):
    """Static panel that can contain other widgets (non-draggable)"""
    
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self._widgets = []
        self._shadow_offset = 4
        self._shadow_color = (0.0, 0.0, 0.0, 0.3)
        
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
        
        # Pass event to child widgets
        for widget in self._widgets:
            if widget.handle_event(event):
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
        
        # Update all child widgets
        for widget in self._widgets:
            widget.x_screen += delta_x
            widget.y_screen += delta_y
            
    def center_on_screen(self, area_width, area_height):
        """Center the panel on screen"""
        x = (area_width - self.width) / 2
        y = (area_height - self.height) / 2
        self.update(x, y)
        
    def draw(self):
        if not self._is_visible:
            return
        
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        
            
        # Draw panel background
        batch = batch_for_shader(
            shader, 'TRI_FAN',
            {"pos": [
                (self.x_screen, self.y_screen),
                (self.x_screen + self.width, self.y_screen),
                (self.x_screen + self.width, self.y_screen + self.height),
                (self.x_screen, self.y_screen + self.height)
            ]},
        )
        shader.uniform_float("color", self._bg_color)
        batch.draw(shader)
    
        
        # Draw child widgets
        for widget in self._widgets:
            widget.draw()