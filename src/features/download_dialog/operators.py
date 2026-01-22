"""Download dialog operators for Blendflare."""

import os
import shutil
import bpy
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, EnumProperty

from ..toast import show_toast, ToastType
from ...logger import download_logger as _log


# Categories that support automatic apply to scene
APPLY_SUPPORTED_CATEGORIES = {
    "materials", "hdris", "scenes",
    # 3D model subcategories
    "architecture", "character", "accessories", "decoration",
    "industrial", "interior", "military", "nature", "space",
    "sport_hobby", "technology", "transport"
}


def _category_supports_apply(category: str) -> bool:
    """Check if a category supports automatic apply to scene."""
    return category.lower() in APPLY_SUPPORTED_CATEGORIES


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def _get_category_icon(category: str) -> str:
    """Get Blender icon for category."""
    icons = {
        "materials": "MATERIAL",
        "hdris": "WORLD",
        "scenes": "SCENE_DATA",
        "3d_models": "MESH_CUBE",
        "architecture": "HOME",
        "character": "ARMATURE_DATA",
        "accessories": "CUBE",
        "decoration": "OUTLINER_OB_LIGHT",
        "industrial": "CON_CLAMPTO",
        "interior": "MOD_FLUIDSIM",
        "military": "TRACKER",
        "nature": "FORCE_WIND",
        "space": "LIGHT_SUN",
        "sport_hobby": "MESH_TORUS",
        "technology": "PREFERENCES",
        "transport": "AUTO",
    }
    return icons.get(category.lower(), "FILE_BLEND")


def _get_category_label(category: str) -> str:
    """Get human readable label for category."""
    labels = {
        "materials": "Material",
        "hdris": "HDRI",
        "scenes": "Scene",
        "3d_models": "3D Model",
        "architecture": "Architecture",
        "character": "Character",
        "accessories": "Accessories",
        "decoration": "Decoration",
        "industrial": "Industrial",
        "interior": "Interior",
        "military": "Military",
        "nature": "Nature",
        "space": "Space",
        "sport_hobby": "Sport & Hobby",
        "technology": "Technology",
        "transport": "Transport",
    }
    return labels.get(category.lower(), category.title())


def _show_message(message: str, title: str = "Blendflare", icon: str = 'INFO'):
    """Show a toast notification and log to console.

    Args:
        message: The message to display
        title: Title (used for logging)
        icon: Icon type to determine toast style
    """
    _log(f"[{title}] {message}")

    # Map icon to toast type
    toast_type = ToastType.INFO
    if icon == 'CHECKMARK':
        toast_type = ToastType.SUCCESS
    elif icon == 'ERROR':
        toast_type = ToastType.ERROR
    elif icon == 'FILE_FOLDER':
        toast_type = ToastType.INFO

    show_toast(message, toast_type, duration=3.0)


class BLENDFLARE_OT_open_download_dialog(Operator):
    """Open the download dialog for a project."""
    bl_idname = "blendflare.open_download_dialog"
    bl_label = "Download Asset"
    bl_description = "Open download dialog for this asset"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from .state import get_download_state
        state = get_download_state()
        if state.project is None:
            self.report({'ERROR'}, "No project selected")
            return {'CANCELLED'}

        # Check if category supports apply
        category = state.project.category.lower()
        if _category_supports_apply(category):
            return bpy.ops.blendflare.download_dialog('INVOKE_DEFAULT')
        else:
            # For unsupported categories, open the download-to-folder dialog
            return bpy.ops.blendflare.download_to_folder_dialog('INVOKE_DEFAULT')


class BLENDFLARE_OT_download_dialog(Operator):
    """Download dialog for Blendflare assets."""
    bl_idname = "blendflare.download_dialog"
    bl_label = "Download & Apply"  # El nombre del botón OK tomará este label en muchas versiones
    bl_description = "View asset details and download"
    bl_options = {'INTERNAL'}

    # Eliminada la propiedad 'action' ya que solo queremos Download & Apply

    remove_scripts: BoolProperty(
        name="Remove Scripts",
        description="Remove all scripts and potentially dangerous drivers from the asset for security",
        default=True,
    )

    def invoke(self, context, event):
        from .state import get_download_state
        state = get_download_state()
        if state.project is None:
            self.report({'ERROR'}, "No project data available")
            return {'CANCELLED'}

        # Reset state
        state.is_downloading = False
        state.download_progress = 0.0
        state.download_message = ""
        state.download_error = None
        state.downloaded_file_path = None

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        from .state import get_download_state
        from .version_check import is_version_compatible, get_current_blender_version_string
        from ..cache import get_cache_manager

        layout = self.layout
        state = get_download_state()
        project = state.project

        if project is None:
            layout.label(text="No project data", icon='ERROR')
            return

        try:
            title = project.project_info.title
            # Asumimos que existe username para la URL, usamos nickname para mostrar
            author_nick = project.author.nickname
            author_username = getattr(project.author, 'username', project.author.nickname)
            category = project.category
            subcategory = project.subcategory
            blender_version = project.technical_specs.blender_version.full_version
            render_engine = project.technical_specs.render_engine
            file_size = project.file_info.file_size
            poly_count = project.file_info.poly_count
            file_name = project.file_info.file_name
            license_type = project.legal.license_type
        except AttributeError:
            layout.label(text="Invalid project data", icon='ERROR')
            return

        # For HDRIs with .zip files, skip version check (they contain .hdr/.exr images)
        # Only check version for direct .blend files
        is_hdri_zip = category.lower() == "hdris" and file_name.lower().endswith('.zip')
        is_compatible = is_hdri_zip or is_version_compatible(blender_version)
        current_version = get_current_blender_version_string()
        cache_mgr = get_cache_manager()
        is_cached = cache_mgr.asset_exists(category, author_nick, project.slug)

        category_icon = _get_category_icon(category)
        category_label = _get_category_label(category)

        # Header
        box = layout.box()
        row = box.row()
        row.label(text=title, icon=category_icon)
        box.label(text=f"by {author_nick}")

        # --- NUEVO: Botones de Enlaces Web ---
        box = layout.box()
        box.label(text="View Online", icon='URL')
        row = box.row(align=True)
        
        # URL 1: Author Profile (blendflare.com/<username>)
        author_url = f"https://blendflare.com/{author_username}"
        op = row.operator("wm.url_open", text="View Author", icon='USER')
        op.url = author_url

        # URL 2: Project Detail (blendflare.com/<username>/<project-slug>)
        project_url = f"https://blendflare.com/{author_username}/{project.slug}"
        op = row.operator("wm.url_open", text="View Project", icon='FILE_BLEND')
        op.url = project_url
        # -------------------------------------

        # Info
        box = layout.box()
        box.label(text="Asset Information", icon='INFO')
        col = box.column(align=True)

        row = col.row()
        row.label(text="Category:")
        cat_text = category_label
        if subcategory:
            cat_text += f" / {_get_category_label(subcategory)}"
        row.label(text=cat_text)

        row = col.row()
        row.label(text="Size:")
        row.label(text=_format_file_size(file_size))

        row = col.row()
        row.label(text="License:")
        row.label(text=license_type.replace("_", " ").title() if license_type else "Unknown")

        if render_engine:
            row = col.row()
            row.label(text="Render Engine:")
            row.label(text=render_engine.title())

        if poly_count and poly_count > 0:
            row = col.row()
            row.label(text="Polygons:")
            row.label(text=f"{poly_count:,}")

        # Version compatibility
        box = layout.box()
        if is_compatible:
            box.label(text="Version Compatible", icon='CHECKMARK')
        else:
            box.label(text="Version Incompatible", icon='ERROR')

        col = box.column(align=True)
        row = col.row()
        row.label(text="Your Blender:")
        row.label(text=current_version)

        row = col.row()
        row.label(text="Required:")
        if is_compatible:
            row.label(text=blender_version)
        else:
            row.alert = True
            row.label(text=f"{blender_version} (upgrade needed)")

        # Cache status
        if is_cached:
            box = layout.box()
            box.label(text="Cached locally", icon='FILE_FOLDER')

        # Security options
        box = layout.box()
        box.label(text="Security", icon='LOCKED')
        box.prop(self, "remove_scripts")

        # Download status
        if state.is_downloading:
            box = layout.box()
            box.label(text=state.download_message or "Downloading...", icon='IMPORT')

        if state.download_error:
            box = layout.box()
            box.alert = True
            box.label(text=state.download_error, icon='ERROR')

        if state.downloaded_file_path and not state.is_downloading:
            box = layout.box()
            box.label(text="Download complete!", icon='CHECKMARK')
        
        if not is_compatible:
            layout.label(text="Warning: Blender version too old", icon='ERROR')

    def execute(self, context):
        from .state import get_download_state
        from .version_check import is_version_compatible

        state = get_download_state()
        project = state.project

        if project is None:
            self.report({'ERROR'}, "No project data")
            return {'CANCELLED'}

        category = project.category.lower()
        blender_version = project.technical_specs.blender_version.full_version
        file_name = project.file_info.file_name

        is_hdri_zip = category == "hdris" and file_name.lower().endswith('.zip')
        is_compatible = is_hdri_zip or is_version_compatible(blender_version)

        if not is_compatible:
            self.report({'ERROR'}, f"Blender {blender_version} or newer required to apply asset")
            return {'CANCELLED'}

        apply_asset = True
        _start_download(project, apply_asset, self.remove_scripts)

        return {'FINISHED'}

class BLENDFLARE_OT_download_asset(Operator):
    """Download asset to local cache (called from popup menu)."""
    bl_idname = "blendflare.download_asset"
    bl_label = "Download Asset"
    bl_description = "Download asset to local cache"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from .state import get_download_state
        state = get_download_state()
        project = state.project

        if project is None:
            self.report({'ERROR'}, "No project data")
            return {'CANCELLED'}

        _start_download(project, apply_asset=False, sanitize=True)
        return {'FINISHED'}


class BLENDFLARE_OT_download_and_apply_asset(Operator):
    """Download and apply asset to scene."""
    bl_idname = "blendflare.download_and_apply_asset"
    bl_label = "Download & Apply Asset"
    bl_description = "Download asset and apply it to the current scene"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from .state import get_download_state
        from .version_check import is_version_compatible

        state = get_download_state()
        project = state.project

        if project is None:
            self.report({'ERROR'}, "No project data")
            return {'CANCELLED'}

        category = project.category.lower()
        blender_version = project.technical_specs.blender_version.full_version
        file_name = project.file_info.file_name

        # For HDRIs with .zip files, skip version check (they contain .hdr/.exr images)
        is_hdri_zip = category == "hdris" and file_name.lower().endswith('.zip')
        if not is_hdri_zip and not is_version_compatible(blender_version):
            self.report({'ERROR'}, f"Blender {blender_version} or newer required")
            return {'CANCELLED'}

        _start_download(project, apply_asset=True, sanitize=True)
        return {'FINISHED'}


def _start_download(project, apply_asset: bool, sanitize: bool = True):
    """Start the download process."""
    from .state import get_download_state
    from ..cache import get_downloader
    from ..cache.downloader import DownloadStatus

    state = get_download_state()

    state.is_downloading = True
    state.download_progress = 0.0
    state.download_message = "Starting download..."
    state.download_error = None

    downloader = get_downloader()

    def on_progress(progress):
        state.download_progress = progress.progress
        state.download_message = progress.message

    def on_complete(progress):
        state.is_downloading = False
        state.download_progress = progress.progress

        if progress.status == DownloadStatus.ERROR:
            state.download_error = progress.error or progress.message
            _show_message(f"Download failed: {progress.message}", "Error", 'ERROR')
        elif progress.status in (DownloadStatus.COMPLETED, DownloadStatus.CACHED):
            state.downloaded_file_path = progress.file_path
            state.download_message = progress.message

            if progress.status == DownloadStatus.CACHED:
                _show_message(f"Using cached version", "Blendflare", 'FILE_FOLDER')
            else:
                _show_message(f"Download complete!", "Blendflare", 'CHECKMARK')

            if apply_asset:
                _apply_asset_to_scene(project, progress.file_path, sanitize)

    started = downloader.download_asset(
        project=project,
        on_progress=on_progress,
        on_complete=on_complete,
        force_download=False,
    )

    if not started:
        state.is_downloading = False
        _show_message("Download already in progress", "Warning", 'INFO')


def _apply_asset_to_scene(project, file_path: str, sanitize: bool = True):
    """Apply downloaded asset to the scene based on category.

    Args:
        project: The project data from the API
        file_path: Path to the downloaded asset file
        sanitize: Whether to sanitize the file before import
    """
    from ..asset_apply import get_applier_for_category

    category = project.category.lower()
    asset_name = project.project_info.title
    asset_metadata = {
        "slug": project.slug,
        "category": category,
        "author": project.author.nickname,
    }

    try:
        applier = get_applier_for_category(
            category=category,
            file_path=file_path,
            sanitize=sanitize,
            asset_name=asset_name,
            asset_metadata=asset_metadata
        )

        if not applier.prepare():
            _show_message("Failed to prepare asset", "Error", 'ERROR')
            return

        result = applier.apply(bpy.context)

        if result.success:
            # Build success message
            items = ", ".join(result.applied_items[:3])
            if len(result.applied_items) > 3:
                items += f" (+{len(result.applied_items) - 3} more)"
            _show_message(f"Applied: {items}", "Success", 'CHECKMARK')
        else:
            _show_message(result.message, "Error", 'ERROR')

        applier.cleanup()

    except NotImplementedError as e:
        _show_message(str(e), "Not Implemented", 'INFO')
    except Exception as e:
        _show_message(f"Error: {str(e)}", "Error", 'ERROR')


class BLENDFLARE_OT_download_to_folder_dialog(Operator):
    """Download dialog for assets that don't support apply - saves to user-selected folder."""
    bl_idname = "blendflare.download_to_folder_dialog"
    bl_label = "Download to Folder"
    bl_description = "Download asset to a folder of your choice"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        from .state import get_download_state
        state = get_download_state()
        if state.project is None:
            self.report({'ERROR'}, "No project data available")
            return {'CANCELLED'}

        # Reset state
        state.is_downloading = False
        state.download_progress = 0.0
        state.download_message = ""
        state.download_error = None
        state.downloaded_file_path = None

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        from .state import get_download_state
        from .version_check import get_current_blender_version_string
        from ..cache import get_cache_manager

        layout = self.layout
        state = get_download_state()
        project = state.project

        if project is None:
            layout.label(text="No project data", icon='ERROR')
            return

        try:
            title = project.project_info.title
            author_nick = project.author.nickname
            author_username = getattr(project.author, 'username', project.author.nickname)
            category = project.category
            subcategory = project.subcategory
            file_size = project.file_info.file_size
            license_type = project.legal.license_type
        except AttributeError:
            layout.label(text="Invalid project data", icon='ERROR')
            return

        current_version = get_current_blender_version_string()
        cache_mgr = get_cache_manager()
        is_cached = cache_mgr.asset_exists(category, author_nick, project.slug)

        category_icon = _get_category_icon(category)
        category_label = _get_category_label(category)

        # Header
        box = layout.box()
        row = box.row()
        row.label(text=title, icon=category_icon)
        box.label(text=f"by {author_nick}")

        # View Online links
        box = layout.box()
        box.label(text="View Online", icon='URL')
        row = box.row(align=True)

        author_url = f"https://blendflare.com/{author_username}"
        op = row.operator("wm.url_open", text="View Author", icon='USER')
        op.url = author_url

        project_url = f"https://blendflare.com/{author_username}/{project.slug}"
        op = row.operator("wm.url_open", text="View Project", icon='FILE_BLEND')
        op.url = project_url

        # Info
        box = layout.box()
        box.label(text="Asset Information", icon='INFO')
        col = box.column(align=True)

        row = col.row()
        row.label(text="Category:")
        cat_text = category_label
        if subcategory:
            cat_text += f" / {_get_category_label(subcategory)}"
        row.label(text=cat_text)

        row = col.row()
        row.label(text="Size:")
        row.label(text=_format_file_size(file_size))

        row = col.row()
        row.label(text="License:")
        row.label(text=license_type.replace("_", " ").title() if license_type else "Unknown")

        # Notice about download-only
        box = layout.box()
        box.label(text="Download Only", icon='INFO')
        col = box.column(align=True)
        col.label(text="This asset category doesn't support")
        col.label(text="automatic import. You can download")
        col.label(text="it to a folder and use it manually.")

        # Cache status
        if is_cached:
            box = layout.box()
            box.label(text="Cached locally", icon='FILE_FOLDER')

        # Download status
        if state.is_downloading:
            box = layout.box()
            box.label(text=state.download_message or "Downloading...", icon='IMPORT')

        if state.download_error:
            box = layout.box()
            box.alert = True
            box.label(text=state.download_error, icon='ERROR')

        if state.downloaded_file_path and not state.is_downloading:
            box = layout.box()
            box.label(text="Download complete!", icon='CHECKMARK')

    def execute(self, context):
        from .state import get_download_state

        state = get_download_state()
        project = state.project

        if project is None:
            self.report({'ERROR'}, "No project data")
            return {'CANCELLED'}

        # Open file browser to select destination folder
        bpy.ops.blendflare.select_download_folder('INVOKE_DEFAULT')

        return {'FINISHED'}


class BLENDFLARE_OT_select_download_folder(Operator):
    """Open file browser to select download destination folder."""
    bl_idname = "blendflare.select_download_folder"
    bl_label = "Select Download Folder"
    bl_description = "Choose where to save the downloaded asset"
    bl_options = {'INTERNAL'}

    directory: StringProperty(
        name="Directory",
        description="Folder to download the asset to",
        subtype='DIR_PATH',
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .state import get_download_state

        state = get_download_state()
        project = state.project

        if project is None:
            self.report({'ERROR'}, "No project data")
            return {'CANCELLED'}

        if not self.directory:
            self.report({'ERROR'}, "No folder selected")
            return {'CANCELLED'}

        # Start download to the selected folder
        _start_download_to_folder(project, self.directory)

        return {'FINISHED'}


def _start_download_to_folder(project, destination_folder: str):
    """Start download and copy to user-selected folder."""
    from .state import get_download_state
    from ..cache import get_downloader
    from ..cache.downloader import DownloadStatus

    state = get_download_state()

    state.is_downloading = True
    state.download_progress = 0.0
    state.download_message = "Starting download..."
    state.download_error = None

    downloader = get_downloader()

    def on_progress(progress):
        state.download_progress = progress.progress
        state.download_message = progress.message

    def on_complete(progress):
        state.is_downloading = False
        state.download_progress = progress.progress

        if progress.status == DownloadStatus.ERROR:
            state.download_error = progress.error or progress.message
            _show_message(f"Download failed: {progress.message}", "Error", 'ERROR')
        elif progress.status in (DownloadStatus.COMPLETED, DownloadStatus.CACHED):
            # Copy the file to the user-selected folder
            source_path = progress.file_path
            if source_path and os.path.exists(source_path):
                try:
                    filename = os.path.basename(source_path)
                    dest_path = os.path.join(destination_folder, filename)

                    # If it's a directory (extracted), copy the whole tree
                    if os.path.isdir(source_path):
                        dest_path = os.path.join(destination_folder, os.path.basename(source_path))
                        if os.path.exists(dest_path):
                            shutil.rmtree(dest_path)
                        shutil.copytree(source_path, dest_path)
                    else:
                        shutil.copy2(source_path, dest_path)

                    state.downloaded_file_path = dest_path
                    state.download_message = f"Saved to: {dest_path}"
                    _show_message(f"Asset saved to: {dest_path}", "Success", 'CHECKMARK')
                except Exception as e:
                    state.download_error = f"Failed to copy file: {str(e)}"
                    _show_message(f"Failed to copy file: {str(e)}", "Error", 'ERROR')
            else:
                state.download_error = "Downloaded file not found"
                _show_message("Downloaded file not found", "Error", 'ERROR')

    started = downloader.download_asset(
        project=project,
        on_progress=on_progress,
        on_complete=on_complete,
        force_download=False,
    )

    if not started:
        state.is_downloading = False
        _show_message("Download already in progress", "Warning", 'INFO')


def register_progress_property():
    """Register progress property on window manager."""
    bpy.types.WindowManager.blendflare_download_progress = bpy.props.FloatProperty(
        name="Download Progress",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype='PERCENTAGE',
    )


def unregister_progress_property():
    """Unregister progress property."""
    if hasattr(bpy.types.WindowManager, 'blendflare_download_progress'):
        del bpy.types.WindowManager.blendflare_download_progress
