"""Inventory and validate paired Wuhan-1 image and mask files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SamplePair:
    sample_id: str
    image: Path
    mask: Path


def paired_samples(root: Path) -> list[SamplePair]:
    images = {path.stem: path for path in (root / "train/images").glob("*.tif")}
    masks = {path.stem: path for path in (root / "train/masks").glob("*.tif")}
    missing_masks = sorted(images.keys() - masks.keys())
    missing_images = sorted(masks.keys() - images.keys())
    if missing_masks or missing_images:
        raise ValueError(
            f"Unpaired samples: missing_masks={missing_masks[:5]}, "
            f"missing_images={missing_images[:5]}"
        )
    return [
        SamplePair(sample_id=key, image=images[key], mask=masks[key])
        for key in sorted(images, key=natural_sample_key)
    ]


def natural_sample_key(value: str) -> tuple[object, ...]:
    """Sort legacy ``img123`` and descriptive business sample IDs."""
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", value)
        if part
    )

