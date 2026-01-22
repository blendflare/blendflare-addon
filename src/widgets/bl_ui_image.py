import bpy
import gpu
import requests
import tempfile
import os
import hashlib
import threading
from gpu_extras.batch import batch_for_shader
from .bl_ui_widget import BL_UI_Widget
from ..logger import widget_logger


class BL_UI_Image(BL_UI_Widget):
    """Image widget for displaying thumbnails from URLs (WebP native) with async loading.

    Uses disk cache in system temp folder + GPU textures in memory.
    Does NOT store images in bpy.data.images to avoid polluting .blend files.
    """

    # Global texture cache (GPU textures + image size)
    _texture_cache = {}  # url -> (texture, width, height)
    _loading_urls = set()
    _cache_dir = None

    @classmethod
    def _get_cache_dir(cls):
        """Get or create the cache directory in system temp"""
        if cls._cache_dir is None:
            cls._cache_dir = os.path.join(tempfile.gettempdir(), "blendflare_thumbs")
            os.makedirs(cls._cache_dir, exist_ok=True)
        return cls._cache_dir

    @classmethod
    def _get_cache_path(cls, url):
        """Get cache file path for a URL"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(cls._get_cache_dir(), f"{url_hash}.webp")

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self._image_url = None
        self._texture = None
        self._image_size = (0, 0)
        self._loading = False
        self._error = False
        self._placeholder_color = (0.15, 0.15, 0.15, 1.0)
        self._border_color = (0.3, 0.3, 0.3, 0.8)
        self._aspect_ratio = 1.0

    @property
    def image_url(self):
        return self._image_url

    @image_url.setter
    def image_url(self, value):
        if self._image_url != value:
            self._image_url = value
            self._texture = None
            self._image_size = (0, 0)
            self._error = False
            self._loading = False
            if value:
                self._load_image(value)

    @property
    def is_loading(self):
        """Check if image is currently loading."""
        return self._loading

    @property
    def has_error(self):
        """Check if image failed to load."""
        return self._error

    @property
    def is_ready(self):
        """Check if image is ready to display."""
        return self._texture is not None and not self._loading and not self._error

    @property
    def aspect_ratio(self):
        return self._aspect_ratio

    @aspect_ratio.setter
    def aspect_ratio(self, value):
        self._aspect_ratio = max(0.1, value)

    def _load_image(self, url):
        """Load WebP image from URL with disk cache + GPU texture (async).

        Flow: URL -> disk cache (temp folder) -> temporary bpy.data.image -> GPU texture -> remove temp image
        Does NOT persist images in bpy.data.images.
        """

        # Memory cache check (GPU texture already created)
        if url in self._texture_cache:
            self._texture, w, h = self._texture_cache[url]
            self._image_size = (w, h)
            if h > 0:
                self._aspect_ratio = w / h
            self._loading = False
            self._force_redraw()
            return

        # Check if already loading
        if url in self._loading_urls:
            return

        self._loading = True
        self._loading_urls.add(url)

        cache_path = self._get_cache_path(url)

        def _download_if_needed():
            """Download image to disk cache if not already cached"""
            try:
                # Check disk cache first
                if os.path.exists(cache_path):
                    bpy.app.timers.register(
                        lambda: self._create_gpu_texture(url, cache_path),
                        first_interval=0.01
                    )
                    return

                # Download image
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                # Save to disk cache
                with open(cache_path, 'wb') as f:
                    f.write(response.content)

                # Schedule GPU texture creation on main thread
                bpy.app.timers.register(
                    lambda: self._create_gpu_texture(url, cache_path),
                    first_interval=0.01
                )

            except Exception as e:
                widget_logger.error(f"Error downloading image from {url}: {e}")
                self._error = True
                self._loading = False
                self._loading_urls.discard(url)
                self._force_redraw()

        # Start download thread
        thread = threading.Thread(target=_download_if_needed, daemon=True)
        thread.start()

    def _create_gpu_texture(self, url, image_path):
        """Create GPU texture from cached image file (runs on main thread).

        Uses a temporary bpy.data.image that is immediately removed after
        creating the GPU texture.
        """
        try:
            # Load into temporary bpy.data.image
            temp_img = bpy.data.images.load(image_path, check_existing=False)

            try:
                try:
                    temp_img.colorspace_settings.name = 'scene_linear'
                except TypeError:
                    try:
                        temp_img.colorspace_settings.name = 'sRGB'
                    except TypeError:
                        pass
               

                # Limit size (thumbnail)
                max_size = 512
                w, h = temp_img.size

                if w > max_size or h > max_size:
                    scale = max_size / max(w, h)
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    temp_img.scale(new_w, new_h)
                    w, h = new_w, new_h

                # Aspect ratio
                if h > 0:
                    self._aspect_ratio = w / h

                # Create GPU texture
                tex = gpu.texture.from_image(temp_img)

                # Store in memory cache
                self._texture = tex
                self._image_size = (w, h)
                self._texture_cache[url] = (tex, w, h)

            finally:
                # ALWAYS remove the temporary image from bpy.data
                if temp_img:
                    bpy.data.images.remove(temp_img)

            self._loading = False
            self._loading_urls.discard(url)
            self._schedule_redraws(3)

        except Exception as e:
            widget_logger.error(f"Error creating GPU texture: {e}")
            self._error = True
            self._loading = False
            self._loading_urls.discard(url)

        return None  # For timer
    def draw(self):
        if not self._is_visible:
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Background
        batch_bg = batch_for_shader(
            shader, 'TRI_FAN',
            {"pos": [
                (self.x_screen, self.y_screen),
                (self.x_screen + self.width, self.y_screen),
                (self.x_screen + self.width, self.y_screen + self.height),
                (self.x_screen, self.y_screen + self.height)
            ]},
        )
        shader.bind()
        shader.uniform_float("color", self._placeholder_color)
        batch_bg.draw(shader)

        # Image
        if self._texture and not self._error and not self._loading:
            self._draw_texture()

        if self._loading:
            self._draw_loading_indicator()
        elif self._error:
            self._draw_error_indicator()

    def _draw_texture(self):
        try:
            shader = gpu.shader.from_builtin('IMAGE')

            widget_w = self.width
            widget_h = self.height

            tex_w, tex_h = self._image_size

            if tex_h == 0:
                return

            widget_ratio = widget_w / widget_h
            image_ratio = tex_w / tex_h

            # Calculate UV rect to crop image
            u_min = 0.0
            v_min = 0.0
            u_max = 1.0
            v_max = 1.0

            if image_ratio > widget_ratio:
                # Image wider → crop left/right
                scale = widget_ratio / image_ratio
                extra = (1.0 - scale) / 2.0
                u_min = extra
                u_max = 1.0 - extra
            else:
                # Image taller → crop top/bottom
                scale = image_ratio / widget_ratio
                extra = (1.0 - scale) / 2.0
                v_min = extra
                v_max = 1.0 - extra

            batch = batch_for_shader(
                shader, 'TRI_FAN',
                {
                    "pos": [
                        (self.x_screen, self.y_screen),
                        (self.x_screen + widget_w, self.y_screen),
                        (self.x_screen + widget_w, self.y_screen + widget_h),
                        (self.x_screen, self.y_screen + widget_h)
                    ],
                    "texCoord": [
                        (u_min, v_min),
                        (u_max, v_min),
                        (u_max, v_max),
                        (u_min, v_max)
                    ]
                }
            )

            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_sampler("image", self._texture)
            batch.draw(shader)
            gpu.state.blend_set('NONE')

        except Exception as e:
            widget_logger.error(f"Error drawing texture: {e}")
            self._error = True

    def _draw_loading_indicator(self):
        import blf

        font_id = 0
        text = "Loading..."

        blf.size(font_id, 11)
        text_w, text_h = blf.dimensions(font_id, text)

        text_x = self.x_screen + (self.width - text_w) / 2
        text_y = self.y_screen + (self.height - text_h) / 2

        blf.color(font_id, 0.6, 0.6, 0.6, 1.0)
        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, text)

    def _draw_error_indicator(self):
        padding = self.width * 0.3
        x1 = self.x_screen + padding
        y1 = self.y_screen + padding
        x2 = self.x_screen + self.width - padding
        y2 = self.y_screen + self.height - padding

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(
            shader, 'LINES',
            {"pos": [(x1, y1), (x2, y2), (x1, y2), (x2, y1)]}
        )
        shader.bind()
        shader.uniform_float("color", (0.8, 0.2, 0.2, 1.0))
        batch.draw(shader)
    
    def _schedule_redraws(self, count=3):
        """Schedule multiple redraws to ensure image appears"""
        intervals = [0.01, 0.05, 0.1]
        
        for i in range(min(count, len(intervals))):
            try:
                bpy.app.timers.register(
                    lambda: self._force_redraw(),
                    first_interval=intervals[i]
                )
            except Exception:
                pass
    
    def _force_redraw(self):
        """Force area redraw"""
        try:
            if bpy.context.area:
                bpy.context.area.tag_redraw()
        except Exception:
            pass
        return None  # For timer

    @classmethod
    def cleanup_cache(cls, clear_disk=False):
        """Clean up image cache.

        Args:
            clear_disk: If True, also delete cached files from disk.
                       If False, only clear memory cache (GPU textures).
        """
        cls._texture_cache.clear()
        cls._loading_urls.clear()

        if clear_disk and cls._cache_dir and os.path.exists(cls._cache_dir):
            try:
                import shutil
                shutil.rmtree(cls._cache_dir)
                cls._cache_dir = None
            except Exception as e:
                widget_logger.error(f"Error clearing disk cache: {e}")