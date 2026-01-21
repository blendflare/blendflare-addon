"""Panel body component: grid for displaying search results."""
from ....widgets import BL_UI_Grid


def add_body_content(panel, panel_width, panel_height):
    """Add results grid to panel body."""
    card_width = 110
    card_height = 140  # Image + title
    grid_height = card_height + 8  # Card + minimal padding

    grid = BL_UI_Grid(
        x=4,
        y=4,  # Bottom margin
        width=panel_width - 8,
        height=grid_height
    )
    grid.tag = "results_grid"
    grid.card_width = card_width
    grid.card_height = card_height

    panel.add_widget(grid)
    return grid
