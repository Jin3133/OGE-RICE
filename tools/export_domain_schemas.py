"""Export version-controlled JSON Schemas for the public domain contracts."""

from __future__ import annotations

import json
from pathlib import Path

from oge_main.domain import (
    AnalysisTask,
    AnalysisTaskCreate,
    AreaStatistic,
    FeedbackRecord,
    IrrigationQuotaAssignment,
    IrrigationQuotaDefinition,
    ManagementUnit,
    ReferenceDemandAssessment,
    RemoteSensingResult,
)

MODELS = {
    "analysis-task-create": AnalysisTaskCreate,
    "analysis-task": AnalysisTask,
    "management-unit": ManagementUnit,
    "remote-sensing-result": RemoteSensingResult,
    "irrigation-quota-definition": IrrigationQuotaDefinition,
    "irrigation-quota-assignment": IrrigationQuotaAssignment,
    "feedback-record": FeedbackRecord,
    "area-statistic": AreaStatistic,
    "reference-demand-assessment": ReferenceDemandAssessment,
}


def main() -> None:
    output = Path("schemas/domain/v1")
    output.mkdir(parents=True, exist_ok=True)
    for existing in output.glob("*.schema.json"):
        existing.unlink()
    for name, model in MODELS.items():
        schema = model.model_json_schema(mode="validation")
        (output / f"{name}.schema.json").write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"exported {len(MODELS)} schemas to {output.resolve()}")


if __name__ == "__main__":
    main()
