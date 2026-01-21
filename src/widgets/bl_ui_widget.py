import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader


class BL_UI_Widget:
    """Base class for all UI widgets"""
    
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.x_screen = x
        self.y_screen = y
        self.width = width
        self.height = height
        self._bg_color = (0.2, 0.2, 0.2, 0.9)
        self._is_visible = True
        self._tag = None  # User-defined tag for identification
        
    @property
    def bg_color(self):
        return self._bg_color
    
    @bg_color.setter
    def bg_color(self, value):
        self._bg_color = value
        
    @property
    def tag(self):
        return self._tag
    
    @tag.setter
    def tag(self, value):
        self._tag = value
        
    def set_location(self, x, y):
        """Set widget location (relative coordinates)"""
        self.x = x
        self.y = y
        self.x_screen = x
        self.y_screen = y
        
    def is_in_rect(self, x, y):
        """Check if point is inside widget bounds"""
        if (self.x_screen <= x <= (self.x_screen + self.width)) and \
           (self.y_screen <= y <= (self.y_screen + self.height)):
            return True
        return False
    
    def get_area_height(self):
        """Get viewport height"""
        return bpy.context.area.height if bpy.context.area else 0
    
    def handle_event(self, event):
        """Override in subclass to handle events"""
        return False
        
    def draw(self):
        """Override in subclass to draw widget"""
        pass
    
    def update(self, x, y):
        """Update widget position"""
        self.x_screen = x
        self.y_screen = y