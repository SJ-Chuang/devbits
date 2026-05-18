from __future__ import annotations

import shutil
from pathlib import Path

from .utils import ensure_dir, iter_project_tree, list_files, readable_size

DEFAULT_IGNORES = [".git", "__pycache__", ".venv", "venv", "node_modules", "build", "dist"]


def print_tree(root: Path, depth: int = 3, ignore: list[str] | None = None) -> list[str]:
    return iter_project_tree(root, ignore or DEFAULT_IGNORES, depth)


def folder_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def top_sizes(root: Path, top: int = 20) -> list[tuple[Path, int, str]]:
    items = [(p, folder_size(p)) for p in root.iterdir()]
    items.sort(key=lambda item: item[1], reverse=True)
    return [(path, size, readable_size(size)) for path, size in items[:top]]


def rename_files(folder: Path, prefix: str = "file", digits: int = 6, start: int = 1, dry_run: bool = False) -> list[tuple[Path, Path]]:
    files = list_files(folder)
    mappings: list[tuple[Path, Path]] = []
    for index, old_path in enumerate(files, start=start):
        new_path = folder / f"{prefix}_{index:0{digits}d}{old_path.suffix.lower()}"
        mappings.append((old_path, new_path))
    if dry_run:
        return mappings
    temp_mappings: list[tuple[Path, Path]] = []
    for index, (old_path, _) in enumerate(mappings):
        temp_path = folder / f".__devbits_tmp_{index}{old_path.suffix}"
        old_path.rename(temp_path)
        temp_mappings.append((temp_path, mappings[index][1]))
    for temp_path, new_path in temp_mappings:
        temp_path.rename(new_path)
    return mappings


def sample_files(folder: Path, output_folder: Path, num: int, copy: bool = True) -> list[Path]:
    files = list_files(folder)
    ensure_dir(output_folder)
    selected = files[:num]
    outputs: list[Path] = []
    for source in selected:
        dest = output_folder / source.name
        if copy:
            shutil.copy2(source, dest)
        else:
            shutil.move(str(source), str(dest))
        outputs.append(dest)
    return outputs
