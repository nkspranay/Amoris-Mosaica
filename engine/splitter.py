import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def split_into_grid(
    image: Image.Image,
    cell_size: int,
) -> tuple[list[np.ndarray], list[np.ndarray], int, int]:
    """
    Split a PIL Image into a grid of equal cells and return:

      - cell_patches : list of np.ndarray (cell_size, cell_size, 3)
      - cell_avgs    : list of np.ndarray([R, G, B])
      - grid_width   : number of tile columns
      - grid_height  : number of tile rows

    Each patch is the actual pixel data for that cell.
    """

    image = _crop_to_grid(image, cell_size)
    img_array = np.array(image, dtype=np.float32)

    grid_height = image.height // cell_size
    grid_width  = image.width  // cell_size

    cell_patches, cell_avgs = _extract_patches_and_averages(
        img_array, grid_height, grid_width, cell_size
    )

    return cell_patches, cell_avgs, grid_width, grid_height


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _crop_to_grid(image: Image.Image, cell_size: int) -> Image.Image:
    new_width  = (image.width  // cell_size) * cell_size
    new_height = (image.height // cell_size) * cell_size

    if new_width == image.width and new_height == image.height:
        return image

    return image.crop((0, 0, new_width, new_height))


def _extract_patches_and_averages(
    img_array: np.ndarray,
    grid_height: int,
    grid_width: int,
    cell_size: int,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """
    Extract both:
    - full image patches
    - average RGB per patch

    Returns flattened lists in row-major order.
    """

    cell_patches = []
    cell_avgs = []

    for row in range(grid_height):
        for col in range(grid_width):
            y0 = row * cell_size
            y1 = y0 + cell_size
            x0 = col * cell_size
            x1 = x0 + cell_size

            patch = img_array[y0:y1, x0:x1]  # shape (cell_size, cell_size, 3)

            cell_patches.append(patch)
            cell_avgs.append(patch.mean(axis=(0, 1)))

    return cell_patches, cell_avgs