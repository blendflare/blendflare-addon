"""Panel header component: close button and category buttons."""
import bpy
from ....widgets import BL_UI_Button, RADIUS_FULL, RADIUS_MD

# Model subcategories: (ID, Label, Icon filename)
# Icons are PNG files in src/icons/categories/
MODEL_SUBCATEGORIES = [
    ('architecture', 'Architecture', 'architecture'),
    ('character', 'Character', 'character'),
    ('accessories', 'Accessories', 'accessories'),
    ('decoration', 'Decoration', 'decoration'),
    ('industrial', 'Industrial', 'industrial'),
    ('interior', 'Interior', 'interior'),
    ('military', 'Military', 'military'),
    ('nature', 'Nature', 'nature'),
    ('space', 'Space', 'space'),
    ('sport_hobby', 'Sport & Hobby', 'sport'),
    ('technology', 'Technology', 'technology'),
    ('transport', 'Transport', 'transport'),
]

def add_close_button(panel, panel_width, panel_height, on_close):
    """Add close button to panel - call this LAST so it renders on top."""
    btn_w, btn_h = 18, 18
    right_margin = 4
    top_margin = 4
    close_x = panel_width - right_margin - btn_w
    close_y = panel_height - top_margin - btn_h

    close_btn = BL_UI_Button(int(close_x), int(close_y), btn_w, btn_h)
    close_btn.text = "×"
    close_btn.text_size = 11
    close_btn.bg_color = (0.4, 0.15, 0.15, 0.9)
    close_btn.border_radius = RADIUS_MD 
    close_btn.set_mouse_up(lambda widget: on_close())
    close_btn.tag = "close_button"
    panel.add_widget(close_btn)


def add_header_controls(panel, panel_width, panel_height, on_close, on_category_click):
    """Add category buttons to the panel header area."""

    is_compact = panel_width < 1050

    # Get current category
    current_category = 'architecture'
    try:
        props = bpy.context.scene.blendflare_props
        current_category = props.category
    except Exception:
        pass

    if is_compact:
        btn_width = 22       
        btn_text_size = 14   
        spacing = 2
    else:
        btn_width = 80       
        btn_text_size = 9   
        spacing = 3

    btn_height = 22        


    start_x = 4
    cat_top_margin = 4  # Minimal margin from top
    start_y = panel_height - cat_top_margin - btn_height

    vertical_spacing = 2

    max_inner_width = panel_width - (start_x * 2) - 26
    columns = max(1, int((max_inner_width + spacing) // (btn_width + spacing)))

    for i, (cat_id, cat_label, cat_icon) in enumerate(MODEL_SUBCATEGORIES):
        col = i % columns
        row = i // columns
        
        x = start_x + col * (btn_width + spacing)
        y = start_y - row * (btn_height + vertical_spacing)

        btn = BL_UI_Button(int(x), int(y), btn_width, btn_height)
        btn.border_radius = RADIUS_MD 

        if is_compact:
            btn.text = ""  
            btn.icon = f"categories/{cat_icon}"  
            btn.tooltip = cat_label  
        else:
            btn.text = cat_label.upper()

        btn.text_size = btn_text_size
        btn.tag = f"category_{cat_id}"

        # Highlight active category
        if cat_id == current_category:
            btn.bg_color = (0.2, 0.4, 0.8, 0.9)
        else:
            btn.bg_color = (0.2, 0.2, 0.2, 0.9)

        btn.set_mouse_up(lambda widget, c=cat_id: on_category_click(c))
        panel.add_widget(btn)