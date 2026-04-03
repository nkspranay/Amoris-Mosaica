from PIL import Image
from tiles.tile_utils import TILE_SIZE


def assemble_mosaic(
    matched_indices: list[int],
    tile_images:     dict[int, Image.Image],
    grid_width:      int,
    grid_height:     int,
    cell_size:       int,
) -> Image.Image:
    """
    Paste matched tile images onto a blank canvas.

    matched_indices: list of tile indices ordered left-to-right, top-to-bottom
    tile_images:     dict of {tile_index: PIL.Image} — only unique tiles loaded
    """
    canvas = Image.new("RGB", (grid_width * cell_size, grid_height * cell_size))

    for i, tile_idx in enumerate(matched_indices):
        row = i // grid_width
        col = i  % grid_width
        x   = col * cell_size
        y   = row * cell_size

        tile = tile_images[tile_idx]

        if tile.size != (cell_size, cell_size):
            tile = tile.resize((cell_size, cell_size), Image.LANCZOS)

        canvas.paste(tile, (x, y))

    return canvas