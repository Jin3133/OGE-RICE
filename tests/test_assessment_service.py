from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from oge_main.application import AssessmentService, InMemoryDomainRepository
from oge_main.domain import (
    AnalysisTask,
    AreaStatistic,
    IrrigationQuotaAssignment,
    IrrigationQuotaDefinition,
    ManagementUnit,
    RemoteSensingResult,
)

EXAMPLES = Path("examples/domain/v1")


def load(filename: str, model: type):
    return model.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"))


def repository() -> InMemoryDomainRepository:
    return InMemoryDomainRepository(
        management_units=[
            load("irrigation-district.json", ManagementUnit),
            load("management-unit.json", ManagementUnit),
        ],
        remote_sensing_results=[
            load("remote-sensing-result.json", RemoteSensingResult)
        ],
        quota_definitions=[
            load("irrigation-quota-definition.json", IrrigationQuotaDefinition)
        ],
        quota_assignments=[
            load("irrigation-quota-assignment.json", IrrigationQuotaAssignment)
        ],
        area_statistics=[load("area-statistic.json", AreaStatistic)],
    )


def test_formal_assessment_uses_versioned_inputs_and_formula() -> None:
    task = load("analysis-task.json", AnalysisTask)
    result = AssessmentService(repository()).calculate(
        task,
        assessment_id="assessment.jx.2025.tillering.0001",
        generated_at=datetime.fromisoformat("2026-11-12T10:30:00+08:00"),
    )
    assert result.total_candidate_area_m2 == 8_175_000
    assert result.total_candidate_area_mu == pytest.approx(12_262.5)
    assert result.total_reference_irrigation_demand_m3 == pytest.approx(981_000)
    snapshot = result.unit_results[0].input_snapshot
    assert snapshot.management_unit.revision == 1
    assert snapshot.quota_definition.record_id == "quota.jx.rice.tillering.example"


def test_missing_version_is_rejected_instead_of_falling_back_to_latest() -> None:
    task_values = json.loads((EXAMPLES / "analysis-task.json").read_text())
    task_values["management_units"][0]["revision"] = 2
    task = AnalysisTask.model_validate(task_values)
    with pytest.raises(LookupError, match="version"):
        AssessmentService(repository()).calculate(
            task, assessment_id="assessment.missing-version"
        )


def test_draft_quota_is_not_used_for_calculation() -> None:
    repo = repository()
    assignment = next(iter(repo.quota_assignments.values()))
    draft = assignment.model_copy(
        update={
            "version": assignment.version.model_copy(update={"status": "draft"})
        }
    )
    repo.quota_assignments = {
        (draft.assignment_id, draft.version.revision): draft
    }
    with pytest.raises(ValueError, match="active immutable version"):
        AssessmentService(repo).calculate(
            load("analysis-task.json", AnalysisTask),
            assessment_id="assessment.draft-quota",
        )


def test_task_replay_uses_explicit_superseded_area_version() -> None:
    repo = repository()
    original = next(iter(repo.area_statistics.values()))
    superseded = original.model_copy(
        update={
            "version": original.version.model_copy(update={"status": "superseded"})
        }
    )
    newer = original.model_copy(
        update={
            "statistic_id": "area.jx.zone.01.rs.2025.tillering.v2",
            "candidate_area_m2": 1_000_000,
        }
    )
    repo.area_statistics = {
        (superseded.statistic_id, superseded.version.revision): superseded,
        (newer.statistic_id, newer.version.revision): newer,
    }

    result = AssessmentService(repo).calculate(
        load("analysis-task.json", AnalysisTask),
        assessment_id="assessment.historical-replay",
    )

    assert result.total_candidate_area_m2 == 8_175_000


def test_task_rejects_area_from_another_remote_result() -> None:
    repo = repository()
    area = next(iter(repo.area_statistics.values()))
    mismatched = area.model_copy(
        update={
            "remote_sensing_result": {
                "record_id": "rs.other",
                "revision": 1,
            }
        }
    )
    repo.area_statistics = {
        (mismatched.statistic_id, mismatched.version.revision): mismatched
    }
    with pytest.raises(ValueError, match="must match the task"):
        AssessmentService(repo).calculate(
            load("analysis-task.json", AnalysisTask),
            assessment_id="assessment.mismatched-area",
        )
