import numpy as np
from collections import deque, Counter
from scipy.spatial import KDTree
from PIL import Image

from tiles.tile_utils import TileIndex, TILE_SIZE

REPEAT_PENALTY_WINDOW = 50
TOP_K_CANDIDATES      = 4
MAX_USAGE_PER_WINDOW  = 4
FAST_MATCH_THRESHOLD  = 15 


class ColorMatcher:

    def __init__(self, index: TileIndex) -> None:
        self._index    = index
        self._avg_rgbs = index.avg_rgbs
        self._tree     = KDTree(self._avg_rgbs)
        self._count    = index.count

        # Lazy cache — only loaded when a tile is actually a TOP_K candidate
        # Keys are tile indices, values are numpy arrays
        self._tile_arrays: dict[int, np.ndarray] = {}
        self._tile_edges:  dict[int, np.ndarray] = {}
        self._tile_skin:   dict[int, np.ndarray] = {}

        dynamic_window    = max(10, min(100, self._count // 10))
        self._window_size = min(REPEAT_PENALTY_WINDOW, dynamic_window)
        self._recent      = deque(maxlen=self._window_size)
        self._usage       = Counter()

        print(f"[ColorMatcher] {self._count} tiles indexed, window: {self._window_size}")

    def find_closest_index(self, cell_patch: np.ndarray, cell_avg_rgb: np.ndarray) -> int:
        """
        Returns the best matching tile INDEX only.
        Never loads or returns a PIL Image — that happens later in assembler.
        """
        idx = self._query_with_penalty(cell_patch, cell_avg_rgb)

        if len(self._recent) == self._recent.maxlen:
            self._usage[self._recent[0]] -= 1
        self._recent.append(idx)
        self._usage[idx] += 1

        return idx

    @property
    def tile_count(self) -> int:
        return self._count

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _query_with_penalty(self, cell_patch, cell_avg_rgb) -> int:
        k = min(TOP_K_CANDIDATES + self._window_size, self._count)
        distances, indices = self._tree.query(cell_avg_rgb, k=k)
        indices   = np.atleast_1d(indices)
        distances = np.atleast_1d(distances)

        best_idx = int(indices[0])
        if distances[0] < FAST_MATCH_THRESHOLD and self._usage[best_idx] < MAX_USAGE_PER_WINDOW:
            return best_idx

        filtered = [int(i) for i in indices if self._usage[int(i)] < MAX_USAGE_PER_WINDOW]
        if not filtered:
            filtered = [int(i) for i in indices]

        return self._best_patch_match(cell_patch, filtered[:TOP_K_CANDIDATES])

    def _best_patch_match(self, cell_patch, candidates: list[int]) -> int:
        patch_img     = Image.fromarray(cell_patch.astype(np.uint8))
        patch_resized = np.array(
            patch_img.resize((TILE_SIZE, TILE_SIZE), Image.BILINEAR),
            dtype=np.float32
        )
        patch_edges = _compute_edge_map(patch_resized)
        patch_skin  = _compute_skin_map(patch_resized)

        best_idx, best_score = candidates[0], float("inf")

        for idx in candidates:
            arr   = self._get_tile_array(idx)
            score = (
                0.6  * float(np.mean((arr                      - patch_resized) ** 2)) +
                0.25 * float(np.mean((self._get_tile_edges(idx) - patch_edges)   ** 2)) +
                0.15 * float(np.mean((self._get_tile_skin(idx)  - patch_skin)    ** 2))
            )
            if score < best_score:
                best_score = score
                best_idx   = idx

        return best_idx

    def _get_tile_array(self, idx: int) -> np.ndarray:
        """Lazy load tile pixel data only when needed for patch matching."""
        if idx not in self._tile_arrays:
            # Try bin file first (Render deployment)
            if self._index.bin_path and self._index.bin_path.exists():
                packed = np.load(self._index.bin_path, mmap_mode='r')
                arr    = packed[idx].copy().astype(np.float32)
            elif idx < len(self._index.tile_paths):
                path = self._index.tile_paths[idx]
                img  = Image.open(path).convert("RGB").resize(
                    (TILE_SIZE, TILE_SIZE), Image.BILINEAR
                )
                arr = np.array(img, dtype=np.float32)
            else:
                # Fallback — solid color from avg RGB
                arr = np.full((TILE_SIZE, TILE_SIZE, 3),
                              self._index.avg_rgbs[idx], dtype=np.float32)

            self._tile_arrays[idx] = arr
            self._tile_edges[idx]  = _compute_edge_map(arr)
            self._tile_skin[idx]   = _compute_skin_map(arr)

        return self._tile_arrays[idx]

    def _get_tile_edges(self, idx: int) -> np.ndarray:
        self._get_tile_array(idx)
        return self._tile_edges[idx]

    def _get_tile_skin(self, idx: int) -> np.ndarray:
        self._get_tile_array(idx)
        return self._tile_skin[idx]


def _compute_edge_map(img_array: np.ndarray) -> np.ndarray:
    gray = np.mean(img_array, axis=2)
    gx   = np.pad(np.abs(np.diff(gray, axis=1)), ((0,0),(0,1)), mode='constant')
    gy   = np.pad(np.abs(np.diff(gray, axis=0)), ((0,1),(0,0)), mode='constant')
    return gx + gy


def _compute_skin_map(img_array: np.ndarray) -> np.ndarray:
    r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
    return (
        (r > 95) & (g > 40) & (b > 20) &
        ((np.max(img_array, axis=2) - np.min(img_array, axis=2)) > 15) &
        (np.abs(r.astype(float) - g.astype(float)) > 15) &
        (r > g) & (r > b)
    ).astype(np.float32)