"""
FastAPI application entry point.

Initialises the app, configures CORS, mounts all routers,
and handles startup/shutdown lifecycle events.

Run with:
    uvicorn api.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes import generate, datasets, tiles
from api.ws import router as ws_router


# ---------------------------------------------------------------------------
# Lifespan — startup and shutdown logic
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: pre-load all three preset tile datasets into memory.
    This means the first request doesn't pay the loading cost.
    Shutdown: nothing to clean up — stateless app.
    """
    print("Starting up Photo Mosaic API...")

    from tiles.tile_utils import load_tile_index
    from tiles.color_match import ColorMatcher

    preset_ids = ["nature", "artworks", "space"]
    loaded = []
    failed = []

    for dataset_id in preset_ids:
        try:
            # Load lightweight index only — no images in memory
            index = load_tile_index(dataset_id)
            # Build KD-tree now so first request is instant
            ColorMatcher(index)
            loaded.append(dataset_id)
            print(f"  ✓ {dataset_id} ({index.count} tiles indexed, no images loaded)")
        except Exception as e:
            failed.append(dataset_id)
            print(f"  ✗ {dataset_id} failed to load: {e}")

    if failed:
        print(f"Warning: {', '.join(failed)} preset(s) unavailable.")
    print(f"Ready. Loaded presets: {', '.join(loaded)}\n")

    yield  # App runs here

    print("Shutting down Photo Mosaic API...")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Photo Mosaic API",
    description="Generate photo mosaics from images or text prompts.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Tile-Count",
        "X-Processing-Ms",
        "X-Grid-Width",
        "X-Grid-Height",
    ],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(generate.router, prefix="/api", tags=["generate"])
app.include_router(datasets.router, prefix="/api", tags=["datasets"])
app.include_router(tiles.router,    prefix="/api", tags=["tiles"])
app.include_router(ws_router,       tags=["websocket"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}