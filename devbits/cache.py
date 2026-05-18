from __future__ import annotations

import shutil
from pathlib import Path

CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
PYC_PATTERNS = ["*.pyc", "*.pyo"]


def clear_cache(root: Path, include_extra: bool = False, dry_run: bool = False) -> list[Path]:
    targets: list[Path] = []
    dir_names = set(CACHE_DIR_NAMES if include_extra else {"__pycache__"})

    for path in root.rglob("*"):
        if path.is_dir() and path.name in dir_names:
            targets.append(path)

    for pattern in PYC_PATTERNS:
        targets.extend(root.rglob(pattern))

    unique_targets = sorted(set(targets), key=lambda p: len(p.parts), reverse=True)
    if dry_run:
        return unique_targets

    for target in unique_targets:
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    return unique_targets
