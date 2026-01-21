"""Properties for Blendflare addon."""
import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntProperty
from blendflare.types import (
    Category,
    LicenseType,
    MaterialType,
    UVMapping,
    RenderEngine,
    Style,
    GameEngine,
    SortBy,
)


# 3D model subcategories (these are actual API categories)
MODEL_CATEGORIES = [
    'architecture', 'character', 'accessories', 'decoration',
    'industrial', 'interior', 'military', 'nature', 'space',
    'sport_hobby', 'technology', 'transport'
]

# Top-level category groups for UI
CATEGORY_GROUPS = ['3d_models', 'materials', 'scenes', 'hdris']


def _enum_items_from_enum(enum_cls, include_empty: bool = True):
    """Convert a Python Enum to Blender EnumProperty items."""
    items = []
    if include_empty:
        items.append(("ANY", "Any", "Not specified"))

    for member in enum_cls:
        identifier = str(member.value)
        label = member.name.replace('_', ' ').title()
        items.append((identifier, label, ""))
    return items


def _force_ui_redraw():
    """Force all 3D viewports and headers to redraw."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                    # Also tag all regions (header, toolbar, etc.)
                    for region in area.regions:
                        region.tag_redraw()
    except Exception:
        pass


class BlendflareProperties(PropertyGroup):
    """Scene properties for Blendflare."""

    # Search text (debounced)
    search_text: StringProperty(
        name="Search",
        description="Search for assets",
        default="",
        update=lambda self, ctx: _on_search_update(self, ctx)
    )

    # Category group (all, 3d_models, materials, scenes, hdris)
    # For UI grouping only - 3d_models expands to show subcategories
    category_group: StringProperty(
        name="Category Group",
        description="Top-level category group",
        default="all"
    )

    # Actual category sent to API
    # Empty string means search all categories
    # For 3d_models group: architecture, character, etc.
    # For others: materials, scenes, hdris
    category: StringProperty(
        name="Category",
        description="Active category for API query",
        default="",
        update=lambda self, ctx: _on_category_change(self, ctx)
    )

    # Subcategory filter (e.g., "building" within "architecture")
    # Empty string means "all subcategories"
    subcategory: StringProperty(
        name="Subcategory",
        description="Filter by subcategory within current category",
        default="",
        update=lambda self, ctx: _on_subcategory_change(self, ctx)
    )

    # Sort
    sort_by: EnumProperty(
        name="Sort By",
        description="Sort results by",
        items=[
            item for item in _enum_items_from_enum(SortBy, include_empty=False)
            if item[0] != "bookmarks"
        ],
        default=list(SortBy)[1].value, # Asegúrate que el default no sea bookmarks
        update=lambda self, ctx: _on_filter_change(self, ctx)
    )

    # Filters
    license_type: EnumProperty(
        name="License Type",
        items=_enum_items_from_enum(LicenseType, include_empty=True),
        default="ANY",
        update=lambda self, ctx: _on_filter_change(self, ctx)
    )

    materials: EnumProperty(
        name="Material Type",
        items=_enum_items_from_enum(MaterialType, include_empty=True),
        default="ANY",
        update=lambda self, ctx: _on_filter_change(self, ctx)
    )

    uv_mapping: EnumProperty(
        name="UV Mapping",
        items=_enum_items_from_enum(UVMapping, include_empty=True),
        default="ANY",
        update=lambda self, ctx: _on_filter_change(self, ctx)
    )

    render_engine: EnumProperty(
        name="Render Engine",
        items=_enum_items_from_enum(RenderEngine, include_empty=True),
        default="ANY",
        update=lambda self, ctx: _on_filter_change(self, ctx)
    )

    style: EnumProperty(
        name="Style",
        items=_enum_items_from_enum(Style, include_empty=True),
        default="ANY",
        update=lambda self, ctx: _on_filter_change(self, ctx)
    )

    game_engines: EnumProperty(
        name="Game Engine",
        items=_enum_items_from_enum(GameEngine, include_empty=True),
        default="ANY",
        update=lambda self, ctx: _on_filter_change(self, ctx)
    )

    # Blender version filter (e.g., "4", "4.2", "4.2.0")
    blender_version: StringProperty(
        name="Blender Version",
        description="Filter by Blender version (e.g., 4, 4.2, or 4.2.0)",
        default="",
        update=lambda self, ctx: _on_filter_change(self, ctx)
    )

    # Author filter toggle
    filter_by_author: BoolProperty(
        name="Filter by Author",
        description="Filter results to show only your assets (uses nickname from preferences)",
        default=False,
        update=lambda self, ctx: _on_filter_change(self, ctx)
    )

    # Pagination
    page: IntProperty(
        name="Page",
        default=1,
        min=1,
        update=lambda self, ctx: _on_page_change(self, ctx)
    )

    total_pages: IntProperty(
        name="Total Pages",
        default=1,
        min=1
    )

    has_next_page: BoolProperty(
        name="Has Next Page",
        default=False
    )

    # Legacy compatibility aliases
    @property
    def active_category(self):
        return self.category_group

    @property
    def active_subcategory(self):
        return self.category


def _on_search_update(self, context):
    """Search text changed - debounced query."""
    # Reset to page 1 on new search
    if self.page != 1:
        self['page'] = 1

    try:
        from ..query import on_search_update
        on_search_update(self, context)
    except Exception:
        pass

    _force_ui_redraw()


def _on_category_change(self, context):
    """Category changed - reset page, subcategory and query."""
    # Reset pagination and subcategory
    self['page'] = 1
    self['total_pages'] = 1
    self['has_next_page'] = False
    self['subcategory'] = ""  # Reset subcategory when category changes

    # Update category group based on category
    if self.category == '':
        # Empty category means "all" - search across all categories
        self['category_group'] = 'all'
    elif self.category in MODEL_CATEGORIES:
        self['category_group'] = '3d_models'
    elif self.category in ('materials', 'scenes', 'hdris'):
        self['category_group'] = self.category

    try:
        from ..query import on_filter_update
        on_filter_update(self, context)
    except Exception:
        pass

    _force_ui_redraw()


def _on_subcategory_change(self, context):
    """Subcategory changed - reset page and query."""
    if self.page != 1:
        self['page'] = 1

    try:
        from ..query import on_filter_update
        on_filter_update(self, context)
    except Exception:
        pass

    _force_ui_redraw()


def _on_filter_change(self, context):
    """Filter changed - reset page and query."""
    if self.page != 1:
        self['page'] = 1

    try:
        from ..query import on_filter_update
        on_filter_update(self, context)
    except Exception:
        pass

    _force_ui_redraw()


def _on_page_change(self, context):
    """Page changed - query without reset."""
    try:
        from ..query import on_filter_update
        on_filter_update(self, context)
    except Exception:
        pass

    _force_ui_redraw()
