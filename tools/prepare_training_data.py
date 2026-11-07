"""Create a leakage-aware split and train-only normalization statistics."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import rasterio
from sklearn.metrics.pairwise import cosine_similarity

from oge_main.data.inventory import SamplePair, paired_samples
from oge_main.data.paths import dataset_root


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def thumbnail(image: np.ndarray, size: int = 16) -> np.ndarray:
    valid = np.any(image != 0, axis=0)
    channels = []
    for band in image:
        sample = band[valid]
        low, high = np.percentile(sample, (2, 98)) if sample.size else (0, 1)
        scaled = np.clip((band.astype(np.float32) - low) / max(high - low, 1), 0, 1)
        channels.append(cv2.resize(scaled, (size, size), interpolation=cv2.INTER_AREA))
    return np.stack(channels).reshape(-1)


def inspect(pair: SamplePair) -> tuple[float, float, np.ndarray]:
    with rasterio.open(pair.image) as source:
        image = source.read()
    with rasterio.open(pair.mask) as source:
        mask = source.read(1)
    valid = np.any(image != 0, axis=0)
    foreground = float(mask[valid].mean()) if valid.any() else 0.0
    return float(valid.mean()), foreground, thumbnail(image)


def foreground_bin(value: float) -> int:
    return int(np.digitize(value, [0.10, 0.25, 0.50, 0.75]))


def build_split(
    pairs: list[SamplePair], seed: int, minimum_eval_coverage: float, similarity: float
) -> tuple[dict[str, list[str]], dict[str, object]]:
    records = [inspect(pair) for pair in pairs]
    features = np.stack([record[2] for record in records])
    matrix = cosine_similarity(features)
    union_find = UnionFind(len(pairs))
    left, right = np.where(np.triu(matrix, k=1) >= similarity)
    for left_index, right_index in zip(left, right, strict=True):
        union_find.union(int(left_index), int(right_index))

    groups: defaultdict[int, list[int]] = defaultdict(list)
    for index in range(len(pairs)):
        groups[union_find.find(index)].append(index)

    forced_train: list[list[int]] = []
    eligible_by_bin: defaultdict[int, list[list[int]]] = defaultdict(list)
    for indices in groups.values():
        if min(records[index][0] for index in indices) < minimum_eval_coverage:
            forced_train.append(indices)
        else:
            mean_foreground = float(np.mean([records[index][1] for index in indices]))
            eligible_by_bin[foreground_bin(mean_foreground)].append(indices)

    rng = random.Random(seed)
    assigned: dict[str, list[int]] = {"train": [], "validation": [], "test": []}
    assigned["train"].extend(index for group in forced_train for index in group)
    for bin_groups in eligible_by_bin.values():
        rng.shuffle(bin_groups)
        sample_count = sum(len(group) for group in bin_groups)
        validation_target = round(sample_count * 0.10)
        test_target = round(sample_count * 0.10)
        validation_count = 0
        test_count = 0
        for group in bin_groups:
            if validation_count < validation_target:
                destination = "validation"
                validation_count += len(group)
            elif test_count < test_target:
                destination = "test"
                test_count += len(group)
            else:
                destination = "train"
            assigned[destination].extend(group)

    split = {
        name: sorted((pairs[index].sample_id for index in indices), key=lambda x: int(x[3:]))
        for name, indices in assigned.items()
    }
    diagnostics: dict[str, object] = {
        "seed": seed,
        "minimum_eval_valid_coverage": minimum_eval_coverage,
        "similarity_group_threshold": similarity,
        "similarity_group_count": len(groups),
        "multi_sample_group_count": sum(len(group) > 1 for group in groups.values()),
        "forced_train_count": sum(len(group) for group in forced_train),
        "split_counts": {name: len(ids) for name, ids in split.items()},
        "split_mean_valid_coverage": {
            name: float(np.mean([records[index][0] for index in assigned[name]]))
            for name in assigned
        },
        "split_mean_foreground_fraction": {
            name: float(np.mean([records[index][1] for index in assigned[name]]))
            for name in assigned
        },
    }
    return split, diagnostics


def training_statistics(pairs: list[SamplePair], train_ids: set[str]) -> dict[str, object]:
    sums = np.zeros(3, dtype=np.float64)
    squared_sums = np.zeros(3, dtype=np.float64)
    count = 0
    for pair in pairs:
        if pair.sample_id not in train_ids:
            continue
        with rasterio.open(pair.image) as source:
            image = source.read().astype(np.float64)
        valid = np.any(image != 0, axis=0)
        values = image[:, valid]
        sums += values.sum(axis=1)
        squared_sums += np.square(values).sum(axis=1)
        count += values.shape[1]
    mean = sums / count
    variance = np.maximum(squared_sums / count - np.square(mean), 0)
    return {
        "mean": mean.tolist(),
        "std": np.sqrt(variance).tolist(),
        "valid_pixel_count": count,
        "calculation_scope": "training split; pixels where at least one band is non-zero",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--minimum-eval-coverage", type=float, default=0.80)
    parser.add_argument("--similarity", type=float, default=0.995)
    parser.add_argument("--split-output", type=Path, default=Path("data/splits/oge_farm_v2.json"))
    parser.add_argument(
        "--statistics-output", type=Path, default=Path("data/statistics/oge_farm_v2.json")
    )
    args = parser.parse_args()

    pairs = paired_samples(dataset_root())
    split, diagnostics = build_split(
        pairs, args.seed, args.minimum_eval_coverage, args.similarity
    )
    statistics = training_statistics(pairs, set(split["train"]))
    payload = {"metadata": diagnostics, **split}
    args.split_output.parent.mkdir(parents=True, exist_ok=True)
    args.statistics_output.parent.mkdir(parents=True, exist_ok=True)
    args.split_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    args.statistics_output.write_text(
        json.dumps(statistics, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    print(json.dumps(statistics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
