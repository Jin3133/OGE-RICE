"""Audit radiometry, masks, duplicates, and split leakage in the OGE farm dataset."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import rasterio
from sklearn.metrics.pairwise import cosine_similarity

from oge_main.data.inventory import paired_samples
from oge_main.data.paths import dataset_root


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def robust_thumbnail(image: np.ndarray, size: int = 16) -> np.ndarray:
    channels = []
    for band in image:
        low, high = np.percentile(band, (2, 98))
        scaled = np.clip((band.astype(np.float32) - low) / max(high - low, 1.0), 0, 1)
        channels.append(cv2.resize(scaled, (size, size), interpolation=cv2.INTER_AREA))
    return np.stack(channels).reshape(-1)


def main() -> None:
    root = dataset_root()
    split_path = Path("data/splits/oge_farm_v1.json")
    splits = json.loads(split_path.read_text())
    split_of = {
        sample_id: split
        for split in ("train", "validation", "test")
        for sample_id in splits[split]
    }

    rows: list[dict[str, object]] = []
    thumbnails: list[np.ndarray] = []
    image_hashes: defaultdict[str, list[str]] = defaultdict(list)
    mask_hashes: defaultdict[str, list[str]] = defaultdict(list)
    sampled_pixels: list[np.ndarray] = []

    for pair in paired_samples(root):
        with rasterio.open(pair.image) as source:
            image = source.read()
        with rasterio.open(pair.mask) as source:
            mask = source.read(1)

        image_hashes[sha256(pair.image)].append(pair.sample_id)
        mask_hashes[sha256(pair.mask)].append(pair.sample_id)
        thumbnails.append(robust_thumbnail(image))
        sampled_pixels.append(image[:, ::16, ::16].reshape(3, -1))

        foreground = mask == 1
        components, _, stats, _ = cv2.connectedComponentsWithStats(
            foreground.astype(np.uint8), connectivity=8
        )
        component_areas = stats[1:, cv2.CC_STAT_AREA] if components > 1 else np.array([])
        row: dict[str, object] = {
            "sample_id": pair.sample_id,
            "split": split_of[pair.sample_id],
            "foreground_fraction": float(foreground.mean()),
            "component_count": int(components - 1),
            "tiny_component_count": int((component_areas < 16).sum()),
            "largest_component_fraction": float(component_areas.max() / mask.size)
            if component_areas.size
            else 0.0,
        }
        for band_index, band in enumerate(image, start=1):
            row[f"band{band_index}_min"] = int(band.min())
            row[f"band{band_index}_max"] = int(band.max())
            row[f"band{band_index}_mean"] = float(band.mean())
            row[f"band{band_index}_std"] = float(band.std())
            row[f"band{band_index}_zero_fraction"] = float((band == 0).mean())
        rows.append(row)

    features = np.stack(thumbnails)
    similarities = cosine_similarity(features)
    np.fill_diagonal(similarities, -1)
    nearest_indices = similarities.argmax(axis=1)
    nearest_scores = similarities[np.arange(len(rows)), nearest_indices]
    for index, row in enumerate(rows):
        row["nearest_sample"] = rows[int(nearest_indices[index])]["sample_id"]
        row["nearest_similarity"] = float(nearest_scores[index])
        row["nearest_cross_split"] = row["split"] != rows[int(nearest_indices[index])]["split"]

    output_dir = Path("outputs/audit")
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "sample_quality.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    pixels = np.concatenate(sampled_pixels, axis=1)
    foreground_fractions = np.array([row["foreground_fraction"] for row in rows])
    exact_image_groups = [ids for ids in image_hashes.values() if len(ids) > 1]
    exact_mask_groups = [ids for ids in mask_hashes.values() if len(ids) > 1]
    summary = {
        "sample_count": len(rows),
        "band_statistics_sampled": {
            f"band{index + 1}": {
                "mean": float(band.mean()),
                "std": float(band.std()),
                "p01": float(np.percentile(band, 1)),
                "p02": float(np.percentile(band, 2)),
                "p50": float(np.percentile(band, 50)),
                "p98": float(np.percentile(band, 98)),
                "p99": float(np.percentile(band, 99)),
            }
            for index, band in enumerate(pixels)
        },
        "foreground_fraction": {
            "mean": float(foreground_fractions.mean()),
            "p00": float(foreground_fractions.min()),
            "p05": float(np.percentile(foreground_fractions, 5)),
            "p50": float(np.percentile(foreground_fractions, 50)),
            "p95": float(np.percentile(foreground_fractions, 95)),
            "p100": float(foreground_fractions.max()),
            "empty_count": int((foreground_fractions == 0).sum()),
            "full_count": int((foreground_fractions == 1).sum()),
            "below_1_percent_count": int((foreground_fractions < 0.01).sum()),
            "above_99_percent_count": int((foreground_fractions > 0.99).sum()),
        },
        "exact_duplicate_image_groups": exact_image_groups,
        "exact_duplicate_mask_group_count": len(exact_mask_groups),
        "near_duplicate_thresholds": {
            str(threshold): {
                "sample_count": int((nearest_scores >= threshold).sum()),
                "cross_split_count": int(
                    sum(
                        score >= threshold and bool(row["nearest_cross_split"])
                        for score, row in zip(nearest_scores, rows, strict=True)
                    )
                ),
            }
            for threshold in (0.99, 0.995, 0.999)
        },
        "split_foreground_means": {
            split: float(
                np.mean([row["foreground_fraction"] for row in rows if row["split"] == split])
            )
            for split in ("train", "validation", "test")
        },
        "flag_counts": {
            "high_zero_fraction_any_band": sum(
                any(float(row[f"band{band}_zero_fraction"]) > 0.05 for band in range(1, 4))
                for row in rows
            ),
            "low_contrast_any_band": sum(
                any(float(row[f"band{band}_std"]) < 100 for band in range(1, 4))
                for row in rows
            ),
            "many_tiny_mask_components": sum(int(row["tiny_component_count"]) > 25 for row in rows),
        },
        "split_counts": dict(Counter(row["split"] for row in rows)),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
