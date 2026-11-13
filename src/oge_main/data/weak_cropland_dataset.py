"""Sentinel-2 dataset paired with a spatially aligned weak cropland reference."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
import torch
from torch.utils.data import Dataset

SampleTransform = Callable[
    [np.ndarray, np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray, np.ndarray]
]


class WeakCroplandDataset(Dataset[dict[str, object]]):
    def __init__(
        self,
        split: str,
        manifest_file: str | Path,
        statistics_file: str | Path,
        transform: SampleTransform | None = None,
    ) -> None:
        manifest = json.loads(Path(manifest_file).read_text(encoding="utf-8"))
        self.samples = manifest["splits"][split]
        statistics = json.loads(Path(statistics_file).read_text(encoding="utf-8"))
        self.mean = np.asarray(statistics["mean"], dtype=np.float32)[:, None, None]
        self.std = np.asarray(statistics["std"], dtype=np.float32)[:, None, None]
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, object]:
        sample = self.samples[index]
        with rasterio.open(sample["image"]) as source:
            image = source.read([1, 2, 3]).astype(np.float32)
        with rasterio.open(sample["mask"]) as source:
            mask = source.read(1).astype(np.float32)
        with rasterio.open(sample["valid_mask"]) as source:
            valid = source.read(1).astype(bool)
        valid &= np.all(image > 0, axis=0)
        if self.transform is not None:
            image, mask, valid = self.transform(image, mask, valid)
        image = (image - self.mean) / self.std
        image[:, ~valid] = 0

        height, width = mask.shape
        padded_h = ((height + 15) // 16) * 16
        padded_w = ((width + 15) // 16) * 16
        padded_image = np.zeros((3, padded_h, padded_w), dtype=np.float32)
        padded_mask = np.zeros((padded_h, padded_w), dtype=np.float32)
        padded_valid = np.zeros((padded_h, padded_w), dtype=bool)
        padded_image[:, :height, :width] = image
        padded_mask[:height, :width] = mask
        padded_valid[:height, :width] = valid
        return {
            "sample_id": sample["sample_id"],
            "image": torch.from_numpy(np.ascontiguousarray(padded_image)).float(),
            "mask": torch.from_numpy(np.ascontiguousarray(padded_mask)).float(),
            "valid_mask": torch.from_numpy(np.ascontiguousarray(padded_valid)).bool(),
        }
