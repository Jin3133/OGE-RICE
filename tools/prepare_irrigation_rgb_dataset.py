"""Create leakage-aware irrigation RGB tiles from large labelled mosaics."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_origin


@dataclass(frozen=True)
class Scene:
    scene_id: str
    image: Path
    mask: Path
    valid_mask: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--valid-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--split-file", type=Path, required=True)
    parser.add_argument("--statistics-file", type=Path, required=True)
    parser.add_argument("--tile-size", type=int, default=512)
    parser.add_argument("--group-size-tiles", type=int, default=4)
    parser.add_argument("--minimum-valid-fraction", type=float, default=0.20)
    return parser.parse_args()


def read_binary(path: Path) -> np.ndarray:
    array = np.asarray(Image.open(path).convert("L"))
    values = np.unique(array)
    if not np.isin(values, [0, 1, 255]).all():
        raise ValueError(f"binary mask contains unsupported values: {path}")
    return array > 0


def scenes(args: argparse.Namespace) -> list[Scene]:
    return [
        Scene(
            scene_id="yuelai",
            image=args.source_root / "悦来灌区.png",
            mask=args.source_root / "labels_mask" / "悦来灌区.png",
            valid_mask=args.valid_root / "悦来灌区.footprint-mask.png",
        ),
        Scene(
            scene_id="changle",
            image=args.source_root / "常乐灌区.png",
            mask=args.source_root / "labels_mask" / "常乐灌区.png",
            valid_mask=args.valid_root / "常乐灌区.footprint-mask.png",
        ),
    ]


def split_for(scene_index: int, row: int, col: int, tile: int, group: int) -> str:
    group_row = row // (tile * group)
    group_col = col // (tile * group)
    # Assign whole 2048-pixel groups, never individual neighbouring tiles.
    # The scene offset rotates the held-out groups while retaining both scenes
    # in every split for the two-scene adaptation experiment.
    bucket = (group_row * 3 + group_col * 5 + scene_index * 2) % 7
    if bucket == 0:
        return "test"
    if bucket == 1:
        return "validation"
    return "train"


def write_tile(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 1 if array.ndim == 2 else array.shape[2]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=count,
        dtype="uint8",
        transform=from_origin(0, array.shape[0], 1, 1),
        compress="deflate",
    ) as destination:
        if array.ndim == 2:
            destination.write(array.astype(np.uint8), 1)
        else:
            destination.write(np.moveaxis(array.astype(np.uint8), -1, 0))


def main() -> None:
    args = parse_args()
    image_directory = args.output_root / "train" / "images"
    mask_directory = args.output_root / "train" / "masks"
    split: dict[str, list[str] | dict] = {
        "metadata": {
            "strategy": "2048-pixel spatial groups assigned before 512-pixel tiles",
            "warning": "Two-scene domain-adaptation dataset; test metrics do not establish cross-region generalization.",
        },
        "train": [],
        "validation": [],
        "test": [],
    }
    rows = []
    train_sum = np.zeros(3, dtype=np.float64)
    train_sum_squares = np.zeros(3, dtype=np.float64)
    train_count = 0

    for scene_index, scene in enumerate(scenes(args)):
        rgb = np.asarray(Image.open(scene.image).convert("RGB"))
        target = read_binary(scene.mask)
        valid = read_binary(scene.valid_mask)
        if rgb.shape[:2] != target.shape or target.shape != valid.shape:
            raise ValueError(f"scene arrays differ in size: {scene.scene_id}")
        for row in range(0, rgb.shape[0], args.tile_size):
            for col in range(0, rgb.shape[1], args.tile_size):
                height = min(args.tile_size, rgb.shape[0] - row)
                width = min(args.tile_size, rgb.shape[1] - col)
                valid_crop = valid[row : row + height, col : col + width]
                if float(valid_crop.mean()) < args.minimum_valid_fraction:
                    continue
                image_crop = np.zeros((args.tile_size, args.tile_size, 3), dtype=np.uint8)
                mask_crop = np.zeros((args.tile_size, args.tile_size), dtype=np.uint8)
                source = rgb[row : row + height, col : col + width].copy()
                source[~valid_crop] = 0
                image_crop[:height, :width] = source
                mask_crop[:height, :width] = (
                    target[row : row + height, col : col + width] & valid_crop
                ).astype(np.uint8)
                sample_id = f"{scene.scene_id}_r{row:05d}_c{col:05d}"
                selected_split = split_for(
                    scene_index, row, col, args.tile_size, args.group_size_tiles
                )
                split[selected_split].append(sample_id)
                write_tile(image_directory / f"{sample_id}.tif", image_crop)
                write_tile(mask_directory / f"{sample_id}.tif", mask_crop)
                valid_pixels = image_crop.any(axis=2)
                if selected_split == "train":
                    values = image_crop[valid_pixels].astype(np.float64)
                    train_sum += values.sum(axis=0)
                    train_sum_squares += np.square(values).sum(axis=0)
                    train_count += len(values)
                rows.append(
                    {
                        "sample_id": sample_id,
                        "scene": scene.scene_id,
                        "split": selected_split,
                        "row": row,
                        "col": col,
                        "valid_fraction": round(float(valid_crop.mean()), 6),
                        "positive_fraction_valid": round(
                            float(mask_crop.sum() / max(valid_crop.sum(), 1)), 6
                        ),
                    }
                )

    mean = train_sum / train_count
    variance = np.maximum(train_sum_squares / train_count - np.square(mean), 0)
    statistics = {
        "mean": mean.tolist(),
        "std": np.sqrt(variance).tolist(),
        "valid_pixel_count": train_count,
        "calculation_scope": "irrigation RGB training split valid pixels",
    }
    args.split_file.parent.mkdir(parents=True, exist_ok=True)
    args.statistics_file.parent.mkdir(parents=True, exist_ok=True)
    args.split_file.write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n")
    args.statistics_file.write_text(
        json.dumps(statistics, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output_root / "tile-manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "samples": len(rows),
                "train": len(split["train"]),
                "validation": len(split["validation"]),
                "test": len(split["test"]),
                "statistics": statistics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
