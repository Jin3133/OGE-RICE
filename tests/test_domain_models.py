from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from oge_main.domain import (
    FeedbackRecord,
    IrrigationQuotaAssignment,
    IrrigationQuotaDefinition,
    ManagementUnit,
    RemoteSensingResult,
)
from oge_main.domain.models import (
    AnalysisTaskCreate,
    DataQuality,
    DataQualityStatus,
    DateRange,
    GrowthStageSelection,
    StageSelectionMethod,
    VersionInfo,
)
from oge_main.domain.rules import (
    validate_management_hierarchy,
    validate_quota_assignment_uniqueness,
)


def period(start: str, end: str) -> DateRange:
    return DateRange(start_date=date.fromisoformat(start), end_date=date.fromisoformat(end))


def automatic_stage() -> GrowthStageSelection:
    return GrowthStageSelection(
        stage_code="tillering",
        stage_name="分蘖期",
        method=StageSelectionMethod.AUTOMATIC,
        crop_calendar_id="calendar.jiangxia.rice.2025",
        effective_period=period("2025-06-01", "2025-06-30"),
    )


def test_date_range_rejects_reverse_order() -> None:
    with pytest.raises(ValidationError, match="start_date must be on or before end_date"):
        period("2025-06-30", "2025-06-01")


def test_verified_quality_requires_review_evidence() -> None:
    with pytest.raises(ValidationError, match="reviewed_by"):
        DataQuality(status=DataQualityStatus.VERIFIED, statement="已核验")


def test_manual_stage_requires_confirmation() -> None:
    with pytest.raises(ValidationError, match="confirmed_by"):
        GrowthStageSelection(
            stage_code="tillering",
            stage_name="分蘖期",
            method=StageSelectionMethod.USER_MODIFIED,
            crop_calendar_id="calendar.jiangxia.rice.2025",
            effective_period=period("2025-06-01", "2025-06-30"),
        )


def test_task_rejects_duplicate_units_and_unknown_fields() -> None:
    values = {
        "name": "江夏分蘖期分析",
        "business_scope": "江夏水稻管理范围",
        "result_mode": "illustrative",
        "crop_code": "rice",
        "analysis_period": period("2025-06-01", "2025-06-30"),
        "growth_stage": automatic_stage(),
        "management_units": [
            {"record_id": "jx.zone.01", "revision": 1},
            {"record_id": "jx.zone.01", "revision": 1},
        ],
        "remote_sensing_result": {"record_id": "rs.jx.2025.01", "revision": 1},
        "area_statistics": [
            {"record_id": "area.jx.zone.01.rs.2025.01", "revision": 1}
        ],
        "irrigation_quota_assignments": [
            {"record_id": "assignment.jx.01", "revision": 1}
        ],
        "created_by": "manager-01",
    }
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        AnalysisTaskCreate.model_validate(values)
    values["management_units"] = [{"record_id": "jx.zone.01", "revision": 1}]
    values["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AnalysisTaskCreate.model_validate(values)


def test_task_requires_one_explicit_area_version_per_unit() -> None:
    values = json.loads(
        Path("examples/domain/v1/analysis-task-create.json").read_text(encoding="utf-8")
    )
    values["area_statistics"] = []
    with pytest.raises(ValidationError, match="at least 1 item"):
        AnalysisTaskCreate.model_validate(values)


def test_v1_task_rejects_unimplemented_formal_mode() -> None:
    values = json.loads(
        Path("examples/domain/v1/analysis-task-create.json").read_text(encoding="utf-8")
    )
    values["result_mode"] = "formal"
    with pytest.raises(ValidationError, match="illustrative"):
        AnalysisTaskCreate.model_validate(values)


def test_manual_stage_accepts_timezone_aware_confirmation() -> None:
    stage = GrowthStageSelection(
        stage_code="tillering",
        stage_name="分蘖期",
        method=StageSelectionMethod.USER_CONFIRMED,
        crop_calendar_id="calendar.jiangxia.rice.2025",
        effective_period=period("2025-06-01", "2025-06-30"),
        confirmed_by="manager-01",
        confirmed_at=datetime(2025, 6, 1, tzinfo=UTC),
    )
    assert stage.method is StageSelectionMethod.USER_CONFIRMED


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("irrigation-district.json", ManagementUnit),
        ("management-unit.json", ManagementUnit),
        ("remote-sensing-result.json", RemoteSensingResult),
        ("irrigation-quota-definition.json", IrrigationQuotaDefinition),
        ("irrigation-quota-assignment.json", IrrigationQuotaAssignment),
        ("analysis-task-create.json", AnalysisTaskCreate),
        ("feedback-record.json", FeedbackRecord),
    ],
)
def test_versioned_examples_validate(filename: str, model: type) -> None:
    path = Path("examples/domain/v1") / filename
    model.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_revision_greater_than_one_requires_previous_reference() -> None:
    with pytest.raises(ValidationError, match="requires a previous version"):
        VersionInfo(
            revision=2,
            previous=None,
            status="active",
            change_reason="修正定额",
            changed_by="manager-01",
            changed_at=datetime(2026, 11, 12, tzinfo=UTC),
        )


def test_overlapping_quota_assignments_are_rejected() -> None:
    definition = IrrigationQuotaDefinition.model_validate_json(
        Path("examples/domain/v1/irrigation-quota-definition.json").read_text()
    )
    first = IrrigationQuotaAssignment.model_validate_json(
        Path("examples/domain/v1/irrigation-quota-assignment.json").read_text()
    )
    second = first.model_copy(
        update={
            "assignment_id": "quota-assignment.jx.zone.01.duplicate",
            "valid_period": period("2025-06-15", "2025-07-15"),
        }
    )
    with pytest.raises(ValueError, match="overlapping quota assignments"):
        validate_quota_assignment_uniqueness([first, second], [definition])


def test_management_zone_must_be_direct_child_of_district() -> None:
    zone_values = json.loads(
        Path("examples/domain/v1/management-unit.json").read_text(encoding="utf-8")
    )
    zone = ManagementUnit.model_validate(zone_values)
    district_values = {
        **zone_values,
        "unit_id": "jx.district",
        "name": "江夏示例灌区",
        "unit_type": "irrigation_district",
        "root_district": {"record_id": "jx.district", "revision": 1},
        "parent": None,
    }
    district = ManagementUnit.model_validate(district_values)
    validate_management_hierarchy([district, zone])
    with pytest.raises(ValueError, match="parent unit"):
        validate_management_hierarchy([zone])
