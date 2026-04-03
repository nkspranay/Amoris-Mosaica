import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter


# ---------------------------------------------------------------------------
# Tuning constants — adjust these to taste without touching logic
# ---------------------------------------------------------------------------

CLAHE_CLIP_LIMIT    = 2.0   # Higher = more contrast boost, more noise risk
CLAHE_TILE_GRID     = (8, 8)  # Smaller grid = more localised enhancement
SHARPEN_RADIUS      = 1.5   # Unsharp mask radius
SHARPEN_PERCENT     = 120   # Unsharp mask strength (100 = no change)
SHARPEN_THRESHOLD   = 3     # Minimum edge difference to sharpen
SATURATION_FACTOR   = 1.2   # 1.0 = no change, 1.3+ gets oversaturated


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preprocess_image(image_path: Path) -> Image.Image:
    """
    Load and enhance a target image before mosaic generation.

    Pipeline: CLAHE (local contrast) → sharpen → saturation boost
    Returns a PIL Image in RGB mode.
    """
    image = _load_as_rgb(image_path)
    image = _apply_clahe(image)
    image = _apply_sharpen(image)
    image = _apply_saturation_boost(image)
    return image


# ---------------------------------------------------------------------------
# Internal steps
# ---------------------------------------------------------------------------

def _load_as_rgb(image_path: Path) -> Image.Image:
    """
    Load any image format and normalise to RGB.
    Handles RGBA (drop alpha), palette mode (P), greyscale, etc.
    """
    image = Image.open(image_path)

    if image.mode == "RGBA":
        # Composite onto white background to drop the alpha channel
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        return background

    return image.convert("RGB")


def _apply_clahe(image: Image.Image) -> Image.Image:
    """
    Apply CLAHE to the L channel of LAB color space.

    Why LAB: CLAHE works on luminance only. LAB separates lightness (L)
    from color (A, B), so we can boost local contrast without shifting hues.
    """
    # PIL RGB → numpy uint8 → OpenCV BGR (cv2 expects BGR)
    img_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # BGR → LAB
    img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)

    # Split channels, apply CLAHE only to L
    l_channel, a_channel, b_channel = cv2.split(img_lab)
    clahe = cv2.createCLAHE(
        clipLimit=CLAHE_CLIP_LIMIT,
        tileGridSize=CLAHE_TILE_GRID,
    )
    l_enhanced = clahe.apply(l_channel)

    # Merge back, convert to RGB PIL Image
    img_lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
    img_bgr_enhanced = cv2.cvtColor(img_lab_enhanced, cv2.COLOR_LAB2BGR)
    img_rgb = cv2.cvtColor(img_bgr_enhanced, cv2.COLOR_BGR2RGB)

    return Image.fromarray(img_rgb)


def _apply_sharpen(image: Image.Image) -> Image.Image:
    """
    Apply unsharp mask sharpening.

    Unsharp mask works by subtracting a blurred version of the image
    from itself — this amplifies edges. The threshold prevents sharpening
    of smooth regions (sky, skin) where noise would become visible.
    """
    return image.filter(
        ImageFilter.UnsharpMask(
            radius=SHARPEN_RADIUS,
            percent=SHARPEN_PERCENT,
            threshold=SHARPEN_THRESHOLD,
        )
    )


def _apply_saturation_boost(image: Image.Image) -> Image.Image:
    """
    Boost colour saturation via the HSV S channel.

    More saturated target image → more distinct average RGB per cell
    → better, more varied tile matching → visually richer mosaic.
    """
    # PIL RGB → numpy → OpenCV BGR → HSV
    img_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

    # Scale saturation channel, clamp to valid uint8 range
    img_hsv[:, :, 1] = np.clip(
        img_hsv[:, :, 1] * SATURATION_FACTOR,
        0,
        255,
    )

    # Back to RGB PIL Image
    img_hsv_uint8 = img_hsv.astype(np.uint8)
    img_bgr_boosted = cv2.cvtColor(img_hsv_uint8, cv2.COLOR_HSV2BGR)
    img_rgb = cv2.cvtColor(img_bgr_boosted, cv2.COLOR_BGR2RGB)

    return Image.fromarray(img_rgb)
