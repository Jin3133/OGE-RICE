"""Formal reference-irrigation-demand assessment service."""

from __future__ import annotations

from datetime import UTC, datetime

from oge_main.application.repository import DomainRepository
from oge_main.domain.models import (
    AnalysisTask,
    DemandInputSnapshot,
    RecordStatus,
    ReferenceDemandAssessment,
    UnitDemandResult,
    VersionedReference,
)
from oge_main.domain.rules import (
    validate_management_hierarchy,
    validate_quota_assignment_uniqueness,
)

SQUARE_METRES_PER_MU = 2000 / 3


def _require_active(record: object, kind: str) -> None:
    if record.version.status is not RecordStatus.ACTIVE:
        raise ValueError(f"{kind} must reference an active immutable version")


def _covers(container, contained) -> bool:
    return (
        container.start_date <= contained.start_date
        and container.end_date >= contained.end_date
    )


class AssessmentService:
    def __init__(self, repository: DomainRepository) -> None:
        self.repository = repository

    def calculate(
        self,
        task: AnalysisTask,
        *,
        assessment_id: str,
        generated_at: datetime | None = None,
    ) -> ReferenceDemandAssessment:
        units = [
            self.repository.get_management_unit(reference)
            for reference in task.management_units
        ]
        hierarchy = list(units)
        known = {(unit.unit_id, unit.version.revision) for unit in hierarchy}
        pending = [unit.parent for unit in hierarchy if unit.parent is not None]
        while pending:
            parent_reference = pending.pop()
            key = (parent_reference.record_id, parent_reference.revision)
            if key in known:
                continue
            parent = self.repository.get_management_unit(parent_reference)
            hierarchy.append(parent)
            known.add(key)
            if parent.parent is not None:
                pending.append(parent.parent)
        validate_management_hierarchy(hierarchy)
        for unit in units:
            _require_active(unit, "management unit")
            if not _covers(unit.valid_period, task.analysis_period):
                raise ValueError("management unit validity must cover the analysis period")

        remote = self.repository.get_remote_sensing_result(
            task.remote_sensing_result
        )
        _require_active(remote, "remote-sensing result")
        unit_ids = {unit.unit_id for unit in units}
        if not unit_ids.issubset(set(remote.management_unit_ids)):
            raise ValueError("remote-sensing result does not cover every task unit")
        if not remote.observation_period.overlaps(task.analysis_period):
            raise ValueError("remote-sensing observation must overlap the analysis period")

        assignments = [
            self.repository.get_quota_assignment(reference)
            for reference in task.irrigation_quota_assignments
        ]
        definitions = [
            self.repository.get_quota_definition(assignment.quota)
            for assignment in assignments
        ]
        validate_quota_assignment_uniqueness(assignments, definitions)
        for assignment, definition in zip(assignments, definitions, strict=True):
            _require_active(assignment, "quota assignment")
            _require_active(definition, "quota definition")
            if definition.crop_code != task.crop_code:
                raise ValueError("quota crop must match the task crop")
            if definition.stage_code != task.growth_stage.stage_code:
                raise ValueError("quota growth stage must match the task growth stage")
            if not _covers(
                assignment.valid_period, task.growth_stage.effective_period
            ):
                raise ValueError("quota assignment must cover the selected growth stage")

        assignment_by_unit = {item.management_unit_id: item for item in assignments}
        if set(assignment_by_unit) != unit_ids or len(assignments) != len(unit_ids):
            raise ValueError("each task unit requires exactly one quota assignment")
        definition_by_assignment = {
            assignment.assignment_id: definition
            for assignment, definition in zip(assignments, definitions, strict=True)
        }

        unit_results = []
        for unit_reference, unit in zip(task.management_units, units, strict=True):
            assignment = assignment_by_unit[unit.unit_id]
            definition = definition_by_assignment[assignment.assignment_id]
            area = self.repository.find_area_statistic(
                unit_reference, task.remote_sensing_result
            )
            _require_active(area, "area statistic")
            area_mu = area.candidate_area_m2 / SQUARE_METRES_PER_MU
            demand = area_mu * definition.value_m3_per_mu
            unit_results.append(
                UnitDemandResult(
                    unit_id=unit.unit_id,
                    input_snapshot=DemandInputSnapshot(
                        management_unit=unit_reference,
                        remote_sensing_result=task.remote_sensing_result,
                        area_statistic=VersionedReference(
                            record_id=area.statistic_id,
                            revision=area.version.revision,
                        ),
                        quota_assignment=VersionedReference(
                            record_id=assignment.assignment_id,
                            revision=assignment.version.revision,
                        ),
                        quota_definition=assignment.quota,
                        stage_code=task.growth_stage.stage_code,
                        candidate_area_m2=area.candidate_area_m2,
                        candidate_area_mu=area_mu,
                        quota_m3_per_mu=definition.value_m3_per_mu,
                    ),
                    reference_irrigation_demand_m3=demand,
                )
            )

        return ReferenceDemandAssessment(
            assessment_id=assessment_id,
            task=VersionedReference(record_id=task.task_id, revision=task.revision),
            generated_at=generated_at or datetime.now(UTC),
            formula="W_m3 = A_mu * M_m3_per_mu",
            unit_results=unit_results,
            total_candidate_area_m2=sum(
                item.input_snapshot.candidate_area_m2 for item in unit_results
            ),
            total_candidate_area_mu=sum(
                item.input_snapshot.candidate_area_mu for item in unit_results
            ),
            total_reference_irrigation_demand_m3=sum(
                item.reference_irrigation_demand_m3 for item in unit_results
            ),
            limitations=[
                "The candidate mask does not independently identify rice.",
                "Reference irrigation demand is not actual withdrawal or supply.",
            ],
        )
