"""Repository contracts and an in-memory implementation for tests and local runs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar

from oge_main.domain.models import (
    AreaStatistic,
    IrrigationQuotaAssignment,
    IrrigationQuotaDefinition,
    ManagementUnit,
    RemoteSensingResult,
    VersionedReference,
)

Record = TypeVar(
    "Record",
    ManagementUnit,
    RemoteSensingResult,
    IrrigationQuotaDefinition,
    IrrigationQuotaAssignment,
    AreaStatistic,
)


class DomainRepository(Protocol):
    def get_management_unit(self, reference: VersionedReference) -> ManagementUnit: ...

    def get_remote_sensing_result(
        self, reference: VersionedReference
    ) -> RemoteSensingResult: ...

    def get_quota_definition(
        self, reference: VersionedReference
    ) -> IrrigationQuotaDefinition: ...

    def get_quota_assignment(
        self, reference: VersionedReference
    ) -> IrrigationQuotaAssignment: ...

    def get_area_statistic(self, reference: VersionedReference) -> AreaStatistic: ...

    def find_area_statistic(
        self,
        management_unit: VersionedReference,
        remote_sensing_result: VersionedReference,
    ) -> AreaStatistic: ...


def _record_key(record: object, identifier_field: str) -> tuple[str, int]:
    return (getattr(record, identifier_field), record.version.revision)


class InMemoryDomainRepository:
    """Store immutable record versions by stable id and revision."""

    def __init__(
        self,
        *,
        management_units: Iterable[ManagementUnit],
        remote_sensing_results: Iterable[RemoteSensingResult],
        quota_definitions: Iterable[IrrigationQuotaDefinition],
        quota_assignments: Iterable[IrrigationQuotaAssignment],
        area_statistics: Iterable[AreaStatistic],
    ) -> None:
        self.management_units = self._index(management_units, "unit_id")
        self.remote_sensing_results = self._index(
            remote_sensing_results, "result_id"
        )
        self.quota_definitions = self._index(quota_definitions, "quota_id")
        self.quota_assignments = self._index(quota_assignments, "assignment_id")
        self.area_statistics = self._index(area_statistics, "statistic_id")

    @staticmethod
    def _index(records: Iterable[Record], identifier_field: str) -> dict[tuple[str, int], Record]:
        index: dict[tuple[str, int], Record] = {}
        for record in records:
            key = _record_key(record, identifier_field)
            if key in index:
                raise ValueError(f"duplicate immutable record version {key!r}")
            index[key] = record
        return index

    @staticmethod
    def _get(index: dict, reference: VersionedReference, kind: str):
        key = (reference.record_id, reference.revision)
        try:
            return index[key]
        except KeyError as error:
            raise LookupError(f"{kind} version {key!r} was not found") from error

    def get_management_unit(self, reference: VersionedReference) -> ManagementUnit:
        return self._get(self.management_units, reference, "management unit")

    def get_remote_sensing_result(
        self, reference: VersionedReference
    ) -> RemoteSensingResult:
        return self._get(self.remote_sensing_results, reference, "remote-sensing result")

    def get_quota_definition(
        self, reference: VersionedReference
    ) -> IrrigationQuotaDefinition:
        return self._get(self.quota_definitions, reference, "quota definition")

    def get_quota_assignment(
        self, reference: VersionedReference
    ) -> IrrigationQuotaAssignment:
        return self._get(self.quota_assignments, reference, "quota assignment")

    def get_area_statistic(self, reference: VersionedReference) -> AreaStatistic:
        return self._get(self.area_statistics, reference, "area statistic")

    def find_area_statistic(
        self,
        management_unit: VersionedReference,
        remote_sensing_result: VersionedReference,
    ) -> AreaStatistic:
        matches = [
            record
            for record in self.area_statistics.values()
            if record.management_unit == management_unit
            and record.remote_sensing_result == remote_sensing_result
            and record.version.status.value == "active"
        ]
        if len(matches) != 1:
            raise LookupError(
                "exactly one active area statistic is required for each management-unit "
                "and remote-sensing-result version"
            )
        return matches[0]
