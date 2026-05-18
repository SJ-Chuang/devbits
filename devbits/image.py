from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from .utils import ensure_dir, list_images, parse_size


def image_to_ico(input_path: Path, output_path: Path, sizes: str = "16,32,48,64,128,256") -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    size_values = [int(item.strip()) for item in sizes.split(",") if item.strip()]
    ico_sizes = [(size, size) for size in size_values]
    with Image.open(input_path) as image:
        image = image.convert("RGBA")
        image.save(output_path, format="ICO", sizes=ico_sizes)
    return output_path


def contact_sheet(
    folder: Path,
    output_path: Path,
    cols: int = 5,
    thumb_size: str = "256,256",
    pattern: str = "*",
    labels: bool = False,
) -> Path:
    images = list_images(folder, pattern=pattern)
    if not images:
        raise ValueError(f"No images found in {folder}")

    thumb_w, thumb_h = parse_size(thumb_size)
    label_h = 24 if labels else 0
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)

    for index, image_path in enumerate(images):
        row, col = divmod(index, cols)
        x = col * thumb_w
        y = row * (thumb_h + label_h)
        try:
            with Image.open(image_path) as image:
                thumb = ImageOps.contain(image.convert("RGB"), (thumb_w, thumb_h))
        except UnidentifiedImageError:
            continue
        paste_x = x + (thumb_w - thumb.width) // 2
        paste_y = y + (thumb_h - thumb.height) // 2
        sheet.paste(thumb, (paste_x, paste_y))
        if labels:
            draw.text((x + 4, y + thumb_h + 4), image_path.name[:40], fill="black")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return output_path


def check_images(folder: Path, recursive: bool = False, remove_broken: bool = False) -> list[Path]:
    broken: list[Path] = []
    for image_path in list_images(folder, recursive=recursive):
        try:
            with Image.open(image_path) as image:
                image.verify()
        except Exception:
            broken.append(image_path)
            if remove_broken:
                image_path.unlink(missing_ok=True)
    return broken


def resize_image(input_path: Path, output_path: Path, size: str, keep_ratio: bool = True) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_size = parse_size(size)
    with Image.open(input_path) as image:
        image = image.convert("RGB")
        if keep_ratio:
            image = ImageOps.contain(image, target_size)
        else:
            image = image.resize(target_size)
        image.save(output_path)
    return output_path


def batch_images(folder: Path, output_folder: Path, size: str | None = None, fmt: str | None = None) -> list[Path]:
    ensure_dir(output_folder)
    outputs: list[Path] = []
    for image_path in list_images(folder):
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            if size:
                image = ImageOps.contain(image, parse_size(size))
            suffix = f".{fmt.lower()}" if fmt else image_path.suffix
            out = output_folder / f"{image_path.stem}{suffix}"
            image.save(out)
            outputs.append(out)
    return outputs
