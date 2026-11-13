"""Build spatially separated train/validation/test manifests and statistics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio

SPLIT_GRIDS = {
    "train": ("JX5K_R03C06", "JX5K_R05C04"),
    "validation": ("JX5K_R10C10",),
    "test": ("JX5K_R07C05",),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=Path("../oge-rice/data/raw/sentinel2_demo_ms4"),
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=Path("../oge-rice/data/raw/cropland_reference_2023"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/splits/sentinel_cropland_weak_v1.json"),
    )
    parser.add_argument(
        "--statistics",
        type=Path,
        default=Path("data/statistics/sentinel_cropland_weak_v1.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    splits = {}
    for split, grid_ids in SPLIT_GRIDS.items():
        samples = []
        for grid_id in grid_ids:
            mask = (
                args.reference_dir
                / grid_id
                / f"{grid_id}_crop_weak_reference_2023.tif"
            ).resolve()
            for image in sorted((args.image_dir / grid_id).glob("*_MS4.tif")):
                date = image.stem.split("_")[-2]
                valid = image.with_name(image.name.replace("_MS4.tif", "_CLEAR10m.tif"))
                samples.append(
                    {
                        "sample_id": f"{grid_id}_{date}",
                        "grid_id": grid_id,
                        "date": date,
                        "image": str(image.resolve()),
                        "mask": str(mask),
                        "valid_mask": str(valid.resolve()),
                        "label_quality": "weak_reference_2023",
                    }
                )
        splits[split] = samples

    sums = np.zeros(3, dtype=np.float64)
    squared = np.zeros(3, dtype=np.float64)
    count = 0
    for sample in splits["train"]:
        with rasterio.open(sample["image"]) as source:
            image = source.read([1, 2, 3]).astype(np.float64)
        with rasterio.open(sample["valid_mask"]) as source:
            valid = source.read(1).astype(bool)
        valid &= np.all(image > 0, axis=0)
        values = image[:, valid]
        sums += values.sum(axis=1)
        squared += np.square(values).sum(axis=1)
        count += values.shape[1]
    mean = sums / count
    std = np.sqrt(np.maximum(squared / count - np.square(mean), 0))

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.statistics.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(
            {
                "version": "v1",
                "label_semantics": "2023 annual crops weak reference",
                "input_band_order": ["B02", "B03", "B04"],
                "split_strategy": "spatial separation by 5 km grid",
                "splits": splits,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    args.statistics.write_text(
        json.dumps(
            {"mean": mean.tolist(), "std": std.tolist(), "valid_pixel_count": count},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print({split: len(samples) for split, samples in splits.items()})
    print("mean", mean.tolist())
    print("std", std.tolist())


if __name__ == "__main__":
    main()
