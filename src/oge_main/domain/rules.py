"""Cross-record business rules that require repository-level context."""

from __future__ import annotations

from collections.abc import Iterable

from oge_main.domain.models import (
    IrrigationQuotaAssignment,
    IrrigationQuotaDefinition,
    ManagementUnit,
)


def validate_management_hierarchy(units: Iterable[ManagementUnit]) -> None:
    """Validate parent types and root membership across management-unit records."""
    records = list(units)
    by_key = {(unit.unit_id, unit.version.revision): unit for unit in records}
    if len(by_key) != len(records):
        raise ValueError("management unit versions must be unique in a hierarchy snapshot")
    for unit in records:
        if unit.unit_type == "irrigation_district":
            continue
        parent_key = (unit.parent.record_id, unit.parent.revision)
        parent = by_key.get(parent_key)
        if parent is None:
            raise ValueError(f"parent unit version {parent_key!r} was not provided")
        if unit.unit_type == "management_zone" and parent.unit_type != "irrigation_district":
            raise ValueError("management zone parent must be an irrigation district")
        if unit.unit_type == "custom" and parent.unit_type not in {
            "irrigation_district",
            "management_zone",
        }:
            raise ValueError("custom unit parent must be a district or management zone")
        if unit.root_district != parent.root_district:
            raise ValueError("child and parent must belong to the same root district")

    for unit in records:
        visited: set[str] = set()
        current = unit
        while current.parent is not None:
            current_key = f"{current.unit_id}:{current.version.revision}"
            if current_key in visited:
                raise ValueError("management hierarchy contains a cycle")
            visited.add(current_key)
            current = by_key[(current.parent.record_id, current.parent.revision)]


def validate_quota_assignment_uniqueness(
    assignments: Iterable[IrrigationQuotaAssignment],
    definitions: Iterable[IrrigationQuotaDefinition],
) -> None:
    """Reject overlapping effective quotas for one unit, crop and growth stage."""
    definition_map = {
        (item.quota_id, item.version.revision): item for item in definitions
    }
    resolved = []
    for assignment in assignments:
        key = (assignment.quota.record_id, assignment.quota.revision)
        definition = definition_map.get(key)
        if definition is None:
            raise ValueError(f"quota definition {key!r} was not provided")
        resolved.append((assignment, definition))
    for index, (left_assignment, left_definition) in enumerate(resolved):
        for right_assignment, right_definition in resolved[index + 1 :]:
            same_business_key = (
                left_assignment.management_unit_id
                == right_assignment.management_unit_id
                and left_definition.crop_code == right_definition.crop_code
                and left_definition.stage_code == right_definition.stage_code
            )
            if same_business_key and left_assignment.valid_period.overlaps(
                right_assignment.valid_period
            ):
                raise ValueError(
                    "one management unit cannot have overlapping quota assignments "
                    "for the same crop and growth stage"
                )
