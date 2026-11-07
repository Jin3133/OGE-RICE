"""Paired geometric and mild radiometric augmentation for remote-sensing patches."""

from __future__ import annotations

import random

import numpy as np


class TrainingTransform:
    def __init__(self, radiometric_probability: float = 0.5) -> None:
        self.radiometric_probability = radiometric_probability

    def __call__(
        self, image: np.ndarray, mask: np.ndarray, valid: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if random.random() < 0.5:
            image, mask, valid = image[:, :, ::-1], mask[:, ::-1], valid[:, ::-1]
        if random.random() < 0.5:
            image, mask, valid = image[:, ::-1, :], mask[::-1, :], valid[::-1, :]
        rotations = random.randrange(4)
        if rotations:
            image = np.rot90(image, rotations, axes=(1, 2))
            mask = np.rot90(mask, rotations)
            valid = np.rot90(valid, rotations)
        if random.random() < self.radiometric_probability:
            gain = np.random.uniform(0.95, 1.05, size=(3, 1, 1)).astype(np.float32)
            offset = np.random.uniform(-20, 20, size=(3, 1, 1)).astype(np.float32)
            image = image * gain + offset
            image[:, ~valid] = 0
        return image.copy(), mask.copy(), valid.copy()

