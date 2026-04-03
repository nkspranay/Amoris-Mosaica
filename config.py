"""
Central config — all environment variables and app-wide constants in one place.
Loaded once at startup via pydantic-settings. Every module imports from here.
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── API Keys ────────────────────────────────────────────────────────────
    nasa_api_key:        str = Field(default="DEMO_KEY", alias="NASA_API_KEY")
    unsplash_access_key: str = Field(default="",         alias="UNSPLASH_ACCESS_KEY")
    pixabay_api_key:     str = Field(default="",         alias="PIXABAY_API_KEY")

    # ── CORS ────────────────────────────────────────────────────────────────
    allowed_origins_str: str = Field(
        default="http://localhost:5173",
        alias="ALLOWED_ORIGINS",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins_str.split(",")]

    # ── Upload limits ───────────────────────────────────────────────────────
    max_target_image_mb:  int = 50       # Target image up to 50MB
    max_zip_mb:           int = 2000     # ZIP up to 2GB for large custom datasets
    max_single_tile_mb:   int = 20       # Per tile up to 20MB
    min_custom_tiles:     int = 50       # Hard minimum
    warn_custom_tiles:    int = 200      # Quality warning below this
    max_custom_tiles:     int = 5000     # Support up to 5000 custom tiles

    # ── Preset tile usage ───────────────────────────────────────────────────
    # How many tiles to load from each preset for mosaic generation
    # We have 4000+ per preset but cap at 2000 for performance
    # Higher = better color matching, slower KD-tree build
    max_preset_tiles:     int = 2000

    # ── Mosaic engine ───────────────────────────────────────────────────────
    max_quality_level:    int = 3

    # ── Paths ───────────────────────────────────────────────────────────────
    project_root:   Path = Path(__file__).resolve().parent
    temp_dir:       Path = Path(__file__).resolve().parent / "temp"
    cache_dir:      Path = Path(__file__).resolve().parent / "cache"
    overrides_dir:  Path = Path(__file__).resolve().parent / "assets" / "overrides"
    presets_dir:    Path = Path(__file__).resolve().parent / "tiles" / "presets"

    model_config = {
        "env_file":          ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name":  True,
        "extra":             "ignore",
    }


# Single shared instance — import this everywhere
settings = Settings()

# Ensure temp directory exists at startup
settings.temp_dir.mkdir(parents=True, exist_ok=True)