from blendflare import (
    BlendflareClient,
    Category,
    Subcategory,
    CATEGORY_SUBCATEGORIES,
    get_subcategory_names,
    get_subcategories,
    SortBy,
    LicenseType,
    RenderEngine,
    Style,
    MaterialType,
    UVMapping,
    GameEngine,
    Pagination,
    Feature,
    DownloadResponse,
    SearchResponse,
    AuthenticationError,
    ValidationError,
    RateLimitError,
    NotFoundError
)
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("BLENDFLARE_API_KEY")
if not api_key:
    raise RuntimeError("Set BLENDFLARE_API_KEY in env or .env")

# Initialize the client with your API key
client = BlendflareClient(api_key=api_key)


transport_names = get_subcategory_names(Category.MATERIALS)
# print(transport_names)  # ['car', 'bicycle', 'motorcycle', ...]

selected_category = Category.MATERIALS
available_subs = get_subcategories(selected_category)

# print("Available subcategories:", available_subs)  # [Subcategory.CAR, Subcategory.BICYCLE, ...]

try:
    results: SearchResponse = client.search_projects(
        q="glass",
        category=selected_category,
        # subcategory=available_subs[0],
        # features=[Feature.RIGGED, Feature.ANIMATED],
        sort_by=SortBy.NEWEST,
        license_type=LicenseType.CC0,
        # game_engines=[GameEngine.UNREAL_ENGINE],
        # materials=MaterialType.TEXTURE_BASED,
        # render_engine=RenderEngine.CYCLES,
        # style=Style.REALISTIC,
        # uv_mapping=UVMapping.NO_UV,
        limit=2
    )



    # Access metadata
    print(f"Pagination: {results.pagination}")
    print(f"Total results: {results.pagination.total}")
    print(f"Search time: {results.metadata.search_time_ms}ms")

    # Iterate through projects
    for project in results.items:
        # Project info
        print(f"Title: {project.project_info.title}")
        print(f"Tags: {', '.join(project.project_info.tags)}")
        
        # Author
        print(f"Author: {project.author.nickname}")
        print(f"Avatar: {project.author.avatar_url}")
        
        # Stats
        print(f"Downloads: {project.stats.downloads_count}")
        print(f"Likes: {project.stats.likes_count}")
        print(f"Views: {project.stats.views_count}")
        
        # Technical specs
        print(f"Blender: {project.technical_specs.blender_version.full_version}")
        print(f"Render engine: {project.technical_specs.render_engine}")
        
        # File info
        print(f"File size: {project.file_info.file_size_mb:.2f} MB")
        print(f"Polygons: {project.file_info.poly_count}")
        
        # Legal
        print(f"License: {project.legal.license_type}")

except AuthenticationError:
    print("Invalid API key")
except ValidationError as e:
    print(f"Validation error: {e}")
    print(f"Details: {e.details}")
except RateLimitError as e:
    print(f"Rate limit exceeded")
except NotFoundError:
    print("Resource not found")
except Exception as e:
    print(f"Unexpected error: {e}")
