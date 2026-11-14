"""Export JSON Schemas for application-layer job contracts."""

from __future__ import annotations

import json
from pathlib import Path

from oge_main.application import SpatialStatisticsJob

MODELS = {"spatial-statistics-job": SpatialStatisticsJob}


def main() -> None:
    output = Path("schemas/application/v1")
    output.mkdir(parents=True, exist_ok=True)
    for existing in output.glob("*.schema.json"):
        existing.unlink()
    for name, model in MODELS.items():
        schema = model.model_json_schema(mode="validation")
        (output / f"{name}.schema.json").write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"exported {len(MODELS)} application schemas to {output.resolve()}")


if __name__ == "__main__":
    main()
