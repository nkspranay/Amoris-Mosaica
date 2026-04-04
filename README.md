# Amoris Mosaica

A high-fidelity photo mosaic generator that reconstructs any image from thousands of smaller photos. Upload a target image or enter a text prompt — the engine splits it into a grid of cells, matches each cell to the closest tile by color, and assembles a mosaic with near-photorealistic accuracy.

**Live Demo:**
- Frontend: [amoris-mosaica.vercel.app](https://amoris-mosaica.vercel.app)
- Backend API: [amoris-mosaica.onrender.com/docs](https://amoris-mosaica.onrender.com/docs)

---

## Features

- **Dual-pass mosaic engine** — a base pass for overall color structure and a finer detail pass layered on top, blended for maximum depth
- **Face detection & enhancement** — OpenCV Haar cascade detects faces and applies a gradient mask to prioritize accuracy in facial regions
- **Patch-level matching** — each cell is matched using pixel-level comparison (color + edge structure + skin tone maps), not just average RGB
- **KD-tree color matching** — scipy KDTree enables sub-millisecond nearest-neighbor lookup across 12,000+ tiles
- **Lazy tile loading** — only RGB arrays are loaded at startup (~1MB). Actual tile images are loaded on-demand per request, keeping memory well within Render's free tier
- **Async job architecture** — generation runs as a background task, WebSocket streams real-time progress, frontend polls for completion — no HTTP timeouts regardless of generation time
- **Text-to-image input** — Unsplash API (primary) + Pixabay API (fallback) resolve any text prompt to a target image
- **Three curated preset datasets** — Nature (4,000+ tiles), Famous Artworks (4,975 tiles from WikiArt + Met Museum), Space/NASA (2,649 tiles from Hubble + APOD)
- **Custom tile uploads** — upload your own ZIP or individual images as a tile dataset
- **Image pre-processing** — CLAHE contrast enhancement, unsharp mask sharpening, and HSV saturation boost on the target image before generation
- **CLI interface** — generate mosaics from the terminal without the web UI

---

## Tech Stack

### Backend
- **Python** + **FastAPI** — async web framework
- **Uvicorn** — ASGI server
- **NumPy** — vectorized cell averaging and tile packing
- **Pillow** — image loading, resizing, blending, and assembly
- **OpenCV** (headless) — CLAHE contrast enhancement, face detection
- **SciPy** — KDTree for nearest-neighbor color matching
- **WebSockets** — real-time progress streaming

### Frontend
- **React** + **Vite** — component-based UI
- **CSS Modules** — scoped styling

### Deployment
- **Render** (backend) — free tier, Python runtime
- **Vercel** (frontend) — static site deployment
- **GitHub** — source control + private assets repo for override images

---

## Architecture

```
Frontend (Vercel)
       ↓  POST /api/generate → returns job_id instantly
Backend (Render / FastAPI)
       ↓  BackgroundTask fires
       ↓  WebSocket streams progress (preprocess → match → assemble)
       ↓  Result saved to temp/{job_id}.png
Frontend polls GET /api/result/{job_id}
       ↓  PNG returned when ready
```

### Engine pipeline

```
Target image
     ↓
Preprocessor      — CLAHE + sharpen + saturation boost
     ↓
Face detector     — OpenCV Haar cascade
     ↓
Grid splitter     — dynamic cell size based on quality level
     ↓  (vectorised NumPy reshape, no per-cell Python loop)
Color matcher     — KDTree query → patch scoring (color + edge + skin)
     ↓  (lazy tile loading — only TOP_K candidates loaded per cell)
Assembler         — unique tiles loaded once, pasted onto canvas
     ↓
Dual-pass blend   — base + detail mosaic blended (alpha 0.4)
     ↓
Face mask         — Gaussian gradient composite for face regions
     ↓
Final blend       — 25% original image overlaid for clarity
     ↓
Output PNG
```

---

## Project Structure

```
Amoris-Mosaica/
│
├── api/                    # FastAPI application
│   ├── main.py             # App init, CORS, lifespan startup
│   ├── ws.py               # WebSocket connection manager
│   ├── jobs.py             # In-memory async job registry
│   └── routes/
│       ├── generate.py     # POST /generate, POST /generate-from-text
│       ├── datasets.py     # GET /datasets
│       └── tiles.py        # POST /upload-tiles, chunked ZIP upload
│
├── engine/                 # Core mosaic generation
│   ├── mosaic.py           # Pipeline orchestrator (dual-pass)
│   ├── preprocessor.py     # CLAHE + sharpen + saturation
│   ├── splitter.py         # Vectorised grid splitting
│   └── assembler.py        # Tile placement onto canvas
│
├── tiles/                  # Tile dataset management
│   ├── tile_utils.py       # TileIndex (lazy), bin file loading
│   └── color_match.py      # KDTree + patch matching + repeat penalty
│
├── input/                  # Input resolution
│   ├── resolver.py         # Upload / prompt / override routing
│   ├── fetcher.py          # Unsplash + Pixabay API
│   └── overrides.py        # Hardcoded prompt → local asset map
│
├── scripts/                # Utility scripts (run locally)
│   ├── download_*.py       # Dataset downloaders (NASA, Unsplash, WikiArt, Met)
│   ├── topup_*.py          # Focused top-up downloaders per preset
│   ├── precompute_caches.py# Build .npy RGB caches from preset images
│   ├── pack_tiles.py       # Pack tile images into .bin for deployment
│   └── startup.sh          # Render startup — clones private assets, starts uvicorn
│
├── cache/                  # Committed to git — used on Render
│   ├── *.npy               # Avg RGB arrays per preset
│   ├── *_files.npy         # Filenames in cache order
│   ├── *_tiles.bin         # Packed tile images (~30MB each)
│   └── metadata.json       # Tile counts per preset
│
├── src/                    # React frontend
│   ├── App.jsx             # State machine (input → processing → result)
│   ├── config.js           # API URL switcher (local dev vs production)
│   └── components/
│       ├── InputScreen.*   # Upload / prompt / dataset / quality UI
│       ├── ProcessScreen.* # Tile animation + WebSocket progress
│       └── ResultScreen.*  # Mosaic display + download
│
├── cli/main.py             # Terminal interface
├── config.py               # Pydantic settings (env vars)
├── validators.py           # File size, type, count validation
├── render.yaml             # Render deployment config
└── requirements.txt
```

---

## Running Locally

### Prerequisites
- Python 3.11+
- Node.js 18+

### Backend

```bash
# Clone the repo
git clone https://github.com/nkspranay/Amoris-Mosaica.git
cd Amoris-Mosaica

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Fill in your API keys in .env

# Start the backend
uvicorn api.main:app --reload
```

Backend runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### Frontend

```bash
# Install dependencies
npm install

# Start the frontend
npm run dev
```

Frontend runs at `http://localhost:5173`.

### Generating preset caches (first time setup)

```bash
# Download preset tile images
python scripts/download_nature.py
python scripts/download_artworks.py
python scripts/download_space.py

# Compute RGB caches
python scripts/precompute_caches.py

# Pack tiles for deployment
python scripts/pack_tiles.py
```

### CLI usage

```bash
python -m cli.main --image photo.jpg --dataset nature --quality 2 --output mosaic.png
python -m cli.main --prompt "Mount Fuji" --dataset space --quality 3
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `NASA_API_KEY` | NASA image API key ([api.nasa.gov](https://api.nasa.gov)) |
| `UNSPLASH_ACCESS_KEY` | Unsplash API key ([unsplash.com/developers](https://unsplash.com/developers)) |
| `PIXABAY_API_KEY` | Pixabay API key ([pixabay.com/api/docs](https://pixabay.com/api/docs)) |
| `OVERRIDE_MAP` | Prompt → asset filename map (format: `prompt:file.jpg;prompt2:file1.jpg\|file2.jpg`) |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) |
| `GITHUB_ASSETS_TOKEN` | GitHub PAT for cloning private assets repo on Render |
| `GITHUB_ASSETS_REPO` | Private repo containing override images (`username/repo`) |

---

## Quality Levels

| Level | Target Tiles | Cell Size | Use Case |
|---|---|---|---|
| Draft | ~15,000 | Large | Fast preview |
| Fine | ~40,000 | Medium | Balanced quality |
| Master | ~75,000 | Small | Maximum detail |

At Master quality, a typical portrait generates 75,000+ individual tile placements across two passes.

---

## Deployment

- Backend deployed on **Render** free tier (512MB RAM). Lazy tile loading keeps memory well within limits — only ~1MB at startup, ~25-50MB peak per request.
- Frontend deployed on **Vercel** as a static site.
- Override images stored in a **private GitHub repository**, cloned to Render at startup via a personal access token.
- Tile images packed into `.bin` files (~30MB each) committed to the main repo — no external storage service needed.

---

## About

Built as a portfolio project demonstrating algorithmic image processing, async system design, and full-stack engineering.

*"Built from fragments. Made with love."*