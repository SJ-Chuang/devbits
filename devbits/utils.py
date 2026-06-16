from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def ensure_exists(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    return path


def ensure_dir(path: Path) -> Path:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    return path


def natural_key(value: str) -> list[object]:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", value)]


def list_files(folder: Path, pattern: str = "*", recursive: bool = False) -> list[Path]:
    iterator = folder.rglob(pattern) if recursive else folder.glob(pattern)
    return sorted([p for p in iterator if p.is_file()], key=lambda p: natural_key(p.name))


def list_images(folder: Path, pattern: str = "*", recursive: bool = False) -> list[Path]:
    return [p for p in list_files(folder, pattern, recursive) if p.suffix.lower() in IMAGE_EXTS]


def parse_size(size: str) -> tuple[int, int]:
    try:
        width, height = size.replace("x", ",").split(",")
        width_i, height_i = int(width), int(height)
    except Exception as exc:
        raise ValueError("Size must be WIDTH,HEIGHT or WIDTHxHEIGHT, e.g. 640,480") from exc
    if width_i <= 0 or height_i <= 0:
        raise ValueError("Width and height must be positive integers")
    return width_i, height_i


def parse_color(value: str) -> tuple[int, int, int]:
    """Parse a color into an ``(R, G, B)`` tuple.

    Accepts a CSS name (``black``), a hex value (``#1a73e8``), or a comma-/
    space-separated ``R,G,B`` triple (``0,178,179``).
    """
    from PIL import ImageColor

    text = value.strip()
    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if len(parts) != 3:
            raise ValueError(f"RGB color must have 3 components, got: {value!r}")
        try:
            channels = tuple(int(p) for p in parts)
        except ValueError as exc:
            raise ValueError(f"RGB components must be integers: {value!r}") from exc
        if any(c < 0 or c > 255 for c in channels):
            raise ValueError(f"RGB components must be in 0-255: {value!r}")
        return channels  # type: ignore[return-value]

    try:
        return ImageColor.getrgb(text)[:3]
    except ValueError as exc:
        raise ValueError(f"Unrecognized color: {value!r}") from exc


def parse_int_tuple(value: str, expected: int, name: str) -> tuple[int, ...]:
    try:
        items = tuple(int(x.strip()) for x in value.split(","))
    except Exception as exc:
        raise ValueError(f"{name} must be comma-separated integers") from exc
    if len(items) != expected:
        raise ValueError(f"{name} must contain {expected} comma-separated integers")
    return items


def readable_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def iter_project_tree(root: Path, ignore: Iterable[str], max_depth: int) -> list[str]:
    ignore_set = set(ignore)
    lines: list[str] = []

    def walk(path: Path, prefix: str = "", depth: int = 0) -> None:
        if depth > max_depth:
            return
        children = [p for p in sorted(path.iterdir(), key=lambda p: (p.is_file(), natural_key(p.name))) if p.name not in ignore_set]
        for index, child in enumerate(children):
            connector = "└── " if index == len(children) - 1 else "├── "
            lines.append(f"{prefix}{connector}{child.name}{'/' if child.is_dir() else ''}")
            if child.is_dir():
                extension = "    " if index == len(children) - 1 else "│   "
                walk(child, prefix + extension, depth + 1)

    lines.append(f"{root.name}/")
    walk(root, max_depth=max_depth)
    return lines
