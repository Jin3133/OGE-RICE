"""Conservative control-point suggestions from source and reference imagery.

The matcher only produces review candidates.  It never promotes points to
verified GCPs or writes a management boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class SuggestedControlPoint:
    pixel_x: float
    pixel_y: float
    reference_x: float
    reference_y: float
    match_distance: float


@dataclass(frozen=True, slots=True)
class ControlPointSuggestionResult:
    points: tuple[SuggestedControlPoint, ...]
    detected_matches: int
    ransac_inliers: int
    method: str = "sift_affine_ransac_v1"


def _decode_image(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("image could not be decoded")
    return image


def _scaled_gray(image: np.ndarray, maximum_dimension: int) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    scale = min(1.0, maximum_dimension / max(height, width))
    if scale < 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return gray, scale


def suggest_control_points(
    source_image: bytes,
    reference_image: bytes,
    *,
    maximum_points: int = 12,
    maximum_dimension: int = 2200,
) -> ControlPointSuggestionResult:
    """Suggest spatially distributed SIFT matches after affine RANSAC filtering."""

    if maximum_points < 3 or maximum_points > 30:
        raise ValueError("maximum_points must be between 3 and 30")
    source_gray, source_scale = _scaled_gray(_decode_image(source_image), maximum_dimension)
    reference_gray, reference_scale = _scaled_gray(
        _decode_image(reference_image), maximum_dimension
    )

    sift = cv2.SIFT_create(nfeatures=10_000, contrastThreshold=0.025)
    source_keypoints, source_descriptors = sift.detectAndCompute(source_gray, None)
    reference_keypoints, reference_descriptors = sift.detectAndCompute(reference_gray, None)
    if source_descriptors is None or reference_descriptors is None:
        raise ValueError("not enough visual features were detected")

    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(
        source_descriptors, reference_descriptors, k=2
    )
    matches = [first for first, second in pairs if first.distance < 0.72 * second.distance]
    if len(matches) < 6:
        raise ValueError("not enough distinctive feature matches were found")

    source_positions = np.float32(
        [source_keypoints[item.queryIdx].pt for item in matches]
    )
    reference_positions = np.float32(
        [reference_keypoints[item.trainIdx].pt for item in matches]
    )
    _, inlier_mask = cv2.estimateAffine2D(
        source_positions,
        reference_positions,
        method=cv2.RANSAC,
        ransacReprojThreshold=5.0,
        maxIters=5000,
        confidence=0.995,
        refineIters=25,
    )
    if inlier_mask is None:
        raise ValueError("feature matches did not produce a stable affine transform")
    inlier_indices = np.flatnonzero(inlier_mask.ravel() == 1).tolist()
    if len(inlier_indices) < 4:
        raise ValueError("fewer than four feature matches survived RANSAC")

    # Keep the strongest match in each source-image grid cell before filling any
    # remaining slots.  This avoids returning many impressive-looking points in
    # one small corner, which is unsafe for georeferencing.
    ranked = sorted(inlier_indices, key=lambda index: matches[index].distance)
    cells: dict[tuple[int, int], int] = {}
    source_height, source_width = source_gray.shape
    for index in ranked:
        x, y = source_positions[index]
        cell = (min(3, int(4 * x / source_width)), min(3, int(4 * y / source_height)))
        cells.setdefault(cell, index)
    # Do not fill the requested count with clustered leftovers.  Returning eight
    # well-spread candidates is safer than returning twelve points where four
    # describe almost the same small neighbourhood.
    selected = list(cells.values())[:maximum_points]

    suggestions = tuple(
        SuggestedControlPoint(
            pixel_x=float(source_positions[index][0] / source_scale),
            pixel_y=float(source_positions[index][1] / source_scale),
            reference_x=float(reference_positions[index][0] / reference_scale),
            reference_y=float(reference_positions[index][1] / reference_scale),
            match_distance=float(matches[index].distance),
        )
        for index in selected
    )
    return ControlPointSuggestionResult(
        points=suggestions,
        detected_matches=len(matches),
        ransac_inliers=len(inlier_indices),
    )
