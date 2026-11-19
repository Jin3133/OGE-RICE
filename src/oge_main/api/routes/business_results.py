"""Read completed, versioned business-result artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import ValidationError

from oge_main.api.contracts import BusinessResultCollection, BusinessResultResponse
from oge_main.api.errors import ApiProblem

router = APIRouter(prefix="/business-results", tags=["business-results"])


def _result_root() -> Path:
    configured = os.getenv("OGE_BUSINESS_RESULTS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[4] / "data" / "derived" / "business-cycle"


def _load_results() -> list[BusinessResultResponse]:
    root = _result_root()
    if not root.is_dir():
        return []
    results = []
    for path in sorted(root.glob("*/demand-result.json")):
        try:
            results.append(
                BusinessResultResponse.model_validate_json(path.read_text(encoding="utf-8"))
            )
        except (OSError, ValidationError, json.JSONDecodeError) as error:
            raise ApiProblem(
                500,
                "INVALID_BUSINESS_RESULT_ARTIFACT",
                f"business result artifact is invalid: {path.name}",
            ) from error
    return sorted(results, key=lambda item: item.generated_at, reverse=True)


@router.get("", response_model=BusinessResultCollection)
def list_business_results() -> BusinessResultCollection:
    items = _load_results()
    return BusinessResultCollection(items=items, total=len(items))


@router.get("/{task_id}", response_model=BusinessResultResponse)
def get_business_result(task_id: str) -> BusinessResultResponse:
    for item in _load_results():
        if item.task_id == task_id:
            return item
    raise ApiProblem(404, "BUSINESS_RESULT_NOT_FOUND", "business result was not found")
