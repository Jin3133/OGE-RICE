"""Resolve local dataset paths without copying raw data into this repository."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_RELATIVE_DATASET = Path(
    "../oge-rice/data/raw/oge_wuhan1_farm/extracted/"
    "89d279976ef74625a1ea00d6cad512c1_farm"
)


def dataset_root(explicit: str | Path | None = None) -> Path:
    """Return and validate the extracted OGE Wuhan-1 dataset root."""
    candidate = explicit or os.getenv("OGE_FARM_DATASET") or DEFAULT_RELATIVE_DATASET
    root = Path(candidate).expanduser()
    if not root.is_absolute():
        root = (Path(__file__).resolve().parents[3] / root).resolve()
    images = root / "train/images"
    masks = root / "train/masks"
    if not images.is_dir() or not masks.is_dir():
        raise FileNotFoundError(
            f"Dataset not found at {root}. Expected train/images and train/masks."
        )
    return root

