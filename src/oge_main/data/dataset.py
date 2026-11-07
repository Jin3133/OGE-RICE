"""PyTorch dataset with radiometric normalization and explicit invalid-pixel masks."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
import torch
from torch.utils.data import Dataset

from oge_main.data.inventory import SamplePair, paired_samples
from oge_main.data.paths import dataset_root

SampleTransform = Callable[
    [np.ndarray, np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray, np.ndarray]
]


class FarmSegmentationDataset(Dataset[dict[str, object]]):
    """Read original uint16 TIFFs without converting or overwriting source data."""

    def __init__(
        self,
        split: str,
        split_file: str | Path = "data/splits/oge_farm_v2.json",
        statistics_file: str | Path = "data/statistics/oge_farm_v2.json",
        root: str | Path | None = None,
        transform: SampleTransform | None = None,
    ) -> None:
        self.root = dataset_root(root)
        split_payload = json.loads(Path(split_file).read_text())
        statistics = json.loads(Path(statistics_file).read_text())
        selected = set(split_payload[split])
        self.samples: list[SamplePair] = [
            pair for pair in paired_samples(self.root) if pair.sample_id in selected
        ]
        if len(self.samples) != len(selected):
            raise ValueError(f"Split {split!r} contains unknown or duplicate sample IDs")
        self.mean = np.asarray(statistics["mean"], dtype=np.float32)[:, None, None]
        self.std = np.asarray(statistics["std"], dtype=np.float32)[:, None, None]
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, object]:
        pair = self.samples[index]
        with rasterio.open(pair.image) as source:
            image = source.read().astype(np.float32)
        with rasterio.open(pair.mask) as source:
            mask = source.read(1).astype(np.float32)

        valid = np.any(image != 0, axis=0)
        if self.transform is not None:
            image, mask, valid = self.transform(image, mask, valid)
        image = (image - self.mean) / self.std
        image[:, ~valid] = 0.0

        return {
            "sample_id": pair.sample_id,
            "image": torch.from_numpy(np.ascontiguousarray(image)).float(),
            "mask": torch.from_numpy(np.ascontiguousarray(mask)).float(),
            "valid_mask": torch.from_numpy(np.ascontiguousarray(valid)).bool(),
        }

