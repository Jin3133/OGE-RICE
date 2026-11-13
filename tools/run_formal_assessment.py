"""Run the formal versioned assessment service from a local JSON catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oge_main.application import AssessmentService, InMemoryDomainRepository
from oge_main.domain import (
    AnalysisTask,
    AreaStatistic,
    IrrigationQuotaAssignment,
    IrrigationQuotaDefinition,
    ManagementUnit,
    RemoteSensingResult,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--assessment-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_many(paths: list[str], model: type):
    return [model.model_validate_json(Path(path).read_text(encoding="utf-8")) for path in paths]


def main() -> None:
    args = parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    repository = InMemoryDomainRepository(
        management_units=load_many(catalog["management_units"], ManagementUnit),
        remote_sensing_results=load_many(
            catalog["remote_sensing_results"], RemoteSensingResult
        ),
        quota_definitions=load_many(
            catalog["quota_definitions"], IrrigationQuotaDefinition
        ),
        quota_assignments=load_many(
            catalog["quota_assignments"], IrrigationQuotaAssignment
        ),
        area_statistics=load_many(catalog["area_statistics"], AreaStatistic),
    )
    task = AnalysisTask.model_validate_json(args.task.read_text(encoding="utf-8"))
    result = AssessmentService(repository).calculate(
        task, assessment_id=args.assessment_id
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "assessment_id": result.assessment_id,
                "task": result.task.model_dump(mode="json"),
                "total_candidate_area_mu": result.total_candidate_area_mu,
                "total_reference_irrigation_demand_m3": (
                    result.total_reference_irrigation_demand_m3
                ),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
