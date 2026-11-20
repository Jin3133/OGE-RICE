"""Durable orchestration from model inference to versioned area statistics."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from rasterio.crs import CRS
from rasterio.errors import RasterioError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from oge_main.application.spatial_statistics import (
    SpatialStatisticsCommand,
    SpatialStatisticsService,
)
from oge_main.domain.models import DataQuality, VersionedReference, VersionInfo
from oge_main.infrastructure.database.models import (
    AreaStatisticVersionRow,
    AuditEventRow,
    ManagementUnitVersionRow,
    OperationAttemptRow,
    OperationRow,
    RemoteResultManagementUnitRow,
    RemoteSensingResultVersionRow,
    ResourceHeadRow,
    SpatialAssetRow,
)

SQUARE_METRES_PER_MU = 2000 / 3


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _allowed_roots() -> list[Path]:
    configured = os.getenv("OGE_PIPELINE_ALLOWED_ROOTS")
    values = configured.split(os.pathsep) if configured else [str(_project_root())]
    return [Path(value).expanduser().resolve() for value in values if value]


def _resolve_input(value: str, *, roots: list[Path]) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _project_root() / path
    path = path.resolve()
    if not any(path.is_relative_to(root) for root in roots):
        raise ValueError(f"pipeline input is outside configured roots: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"pipeline input does not exist: {path}")
    return path


def _next_revision(
    session: Session,
    *,
    resource_type: str,
    resource_id: str,
    now: datetime,
) -> tuple[int, int | None]:
    inserted_revision = session.scalar(
        pg_insert(ResourceHeadRow)
        .values(
            resource_type=resource_type,
            resource_id=resource_id,
            current_revision=1,
            updated_at=now,
        )
        .on_conflict_do_nothing(
            index_elements=[ResourceHeadRow.resource_type, ResourceHeadRow.resource_id]
        )
        .returning(ResourceHeadRow.current_revision)
    )
    if inserted_revision is not None:
        return int(inserted_revision), None
    head = session.scalar(
        select(ResourceHeadRow)
        .where(
            ResourceHeadRow.resource_type == resource_type,
            ResourceHeadRow.resource_id == resource_id,
        )
        .with_for_update()
    )
    if head is None:
        raise RuntimeError("resource revision allocator lost its resource head")
    previous = head.current_revision
    head.current_revision = previous + 1
    head.updated_at = now
    return previous + 1, previous


def _operation_status(
    factory: sessionmaker[Session],
    operation_id: str,
    *,
    status: str,
    result_summary: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    with factory.begin() as session:
        row = session.get(OperationRow, operation_id)
        if row is None:
            raise LookupError(f"operation {operation_id!r} was not found")
        now = datetime.now(UTC)
        row.status = status
        if status == "running":
            row.started_at = now
        if status in {"succeeded", "failed"}:
            row.finished_at = now
        row.result_summary = result_summary
        if result_summary and result_summary.get("result_revision") is not None:
            row.target_revision = int(result_summary["result_revision"])
        row.error_code = error_code
        row.error_message = error_message


def _run_inference(payload: dict[str, Any], output_directory: Path) -> Path:
    roots = _allowed_roots()
    command = [
        sys.executable,
        str(_project_root() / "tools" / "infer_large_georeferenced_rgb.py"),
        "--source-image",
        str(_resolve_input(payload["source_image_path"], roots=roots)),
        "--fit-response",
        str(_resolve_input(payload["fit_response_path"], roots=roots)),
        "--valid-mask",
        str(_resolve_input(payload["inference_valid_mask_path"], roots=roots)),
        "--checkpoint",
        str(_resolve_input(payload["checkpoint_path"], roots=roots)),
        "--output-directory",
        str(output_directory),
        "--scene-id",
        payload["scene_id"],
        "--target",
        payload["target"],
        "--threshold",
        str(payload["threshold"]),
    ]
    if payload.get("reference_mask_path"):
        command.extend(
            [
                "--reference-mask",
                str(_resolve_input(payload["reference_mask_path"], roots=roots)),
            ]
        )
    completed = subprocess.run(
        command,
        cwd=_project_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"model inference failed: {message[-4000:]}")
    manifest = output_directory / "model-run.json"
    if not manifest.is_file():
        raise RuntimeError("model inference completed without model-run.json")
    return manifest


def _register_remote_result(
    factory: sessionmaker[Session],
    payload: dict[str, Any],
    manifest: dict[str, Any],
    mask_path: Path,
    operation_id: str,
) -> int:
    now = datetime.now(UTC)
    with factory.begin() as session:
        revision, previous_revision = _next_revision(
            session,
            resource_type="remote_sensing_result",
            resource_id=payload["result_id"],
            now=now,
        )
        if previous_revision is not None:
            previous = session.get(
                RemoteSensingResultVersionRow,
                (payload["result_id"], previous_revision),
            )
            if previous is not None and previous.status == "active":
                previous.status = "superseded"
        asset_id = f"asset_{uuid4().hex}"
        checkpoint = manifest["model"]["checkpoint"]
        session.add(
            SpatialAssetRow(
                asset_id=asset_id,
                href=str(mask_path),
                media_type="image/tiff; application=geotiff",
                roles=["mask"],
                crs=manifest["input"]["crs"],
                checksum_sha256=_sha256(mask_path),
                created_at=now,
                source={
                    "title": f"{payload['scene_id']} model candidate mask",
                    "publisher": f"model run {manifest['run_id']} / {Path(checkpoint).name}",
                },
            )
        )
        session.flush()
        session.add(
            RemoteSensingResultVersionRow(
                result_id=payload["result_id"],
                revision=revision,
                target=payload["target"],
                observation_period=Range(
                    date.fromisoformat(payload["observation_start"]),
                    date.fromisoformat(payload["observation_end"]) + timedelta(days=1),
                    bounds="[)",
                ),
                mask_asset_id=asset_id,
                model_name=manifest["model"]["architecture"],
                model_version=manifest["model"]["checkpoint_sha256"][:12],
                produced_at=datetime.fromisoformat(manifest["generated_at"]),
                quality={
                    "status": "unverified",
                    "statement": "模型候选成果，进入面积统计前后均需保留复核状态。",
                },
                previous_result_id=payload["result_id"] if previous_revision else None,
                previous_revision=previous_revision,
                status="active",
                change_reason=payload["change_reason"],
                changed_by=payload["changed_by"],
                changed_at=now,
                feedback_id=None,
            )
        )
        session.flush()
        for unit in payload["units"]:
            session.add(
                RemoteResultManagementUnitRow(
                    result_id=payload["result_id"],
                    result_revision=revision,
                    unit_id=unit["unit_id"],
                )
            )
        session.add(
            AuditEventRow(
                event_id=f"audit_{uuid4().hex}",
                occurred_at=now,
                actor_id=payload["changed_by"],
                request_id=operation_id,
                action="remote_sensing_result.registered",
                resource_type="remote_sensing_result",
                resource_id=payload["result_id"],
                resource_revision=revision,
                summary={"model_run_id": manifest["run_id"], "target": payload["target"]},
            )
        )
    return revision


def _calculate_unit_statistic(
    factory: sessionmaker[Session],
    payload: dict[str, Any],
    unit_input: dict[str, Any],
    *,
    result_revision: int,
    mask_path: Path,
    operation_id: str,
) -> dict[str, Any]:
    roots = _allowed_roots()
    valid_path = _resolve_input(unit_input["valid_observation_mask_path"], roots=roots)
    now = datetime.now(UTC)
    statistic_id = f"area.{payload['result_id']}.{unit_input['unit_id']}"
    with factory() as session:
        row = session.get(
            ManagementUnitVersionRow,
            (unit_input["unit_id"], unit_input["unit_revision"]),
        )
        if row is None:
            raise LookupError(
                f"management unit {(unit_input['unit_id'], unit_input['unit_revision'])!r} "
                "was not found"
            )
        geometry_json = session.scalar(func.ST_AsGeoJSON(row.geom))
        unit_name = row.name
    calculated = SpatialStatisticsService().calculate_with_geometries(
        SpatialStatisticsCommand(
            statistic_id=statistic_id,
            management_unit=VersionedReference(
                record_id=unit_input["unit_id"], revision=unit_input["unit_revision"]
            ),
            remote_sensing_result=VersionedReference(
                record_id=payload["result_id"], revision=result_revision
            ),
            candidate_mask_path=mask_path,
            valid_observation_mask_path=valid_path,
            boundary_path=Path("database-boundary"),
            calculated_at=now,
            quality=DataQuality(
                status="unverified",
                statement="由待复核模型候选掩膜自动计算，须结合质量指标复核。",
            ),
            version=VersionInfo(
                revision=1,
                status="active",
                change_reason=payload["change_reason"],
                changed_by=payload["changed_by"],
                changed_at=now,
            ),
        ),
        geometries=[json.loads(geometry_json)],
        boundary_crs=CRS.from_epsg(4326),
    )
    with factory.begin() as session:
        revision, previous_revision = _next_revision(
            session,
            resource_type="area_statistic",
            resource_id=statistic_id,
            now=now,
        )
        if previous_revision is not None:
            previous = session.get(AreaStatisticVersionRow, (statistic_id, previous_revision))
            if previous is not None and previous.status == "active":
                previous.status = "superseded"
        session.add(
            AreaStatisticVersionRow(
                statistic_id=calculated.statistic_id,
                revision=revision,
                management_unit_id=calculated.management_unit.record_id,
                management_unit_revision=calculated.management_unit.revision,
                remote_result_id=calculated.remote_sensing_result.record_id,
                remote_result_revision=calculated.remote_sensing_result.revision,
                candidate_area_m2=calculated.candidate_area_m2,
                valid_observation_area_m2=calculated.valid_observation_area_m2,
                method=calculated.method,
                calculated_at=calculated.calculated_at,
                quality=calculated.quality.model_dump(mode="json"),
                previous_statistic_id=statistic_id if previous_revision else None,
                previous_revision=previous_revision,
                status="active",
                change_reason=payload["change_reason"],
                changed_by=payload["changed_by"],
                changed_at=now,
                feedback_id=None,
            )
        )
        session.add(
            AuditEventRow(
                event_id=f"audit_{uuid4().hex}",
                occurred_at=now,
                actor_id=payload["changed_by"],
                request_id=operation_id,
                action="area_statistic.calculated",
                resource_type="area_statistic",
                resource_id=statistic_id,
                resource_revision=revision,
                summary={
                    "candidate_area_m2": calculated.candidate_area_m2,
                    "remote_result_revision": result_revision,
                },
            )
        )
    return {
        "statistic_id": statistic_id,
        "revision": revision,
        "unit_id": unit_input["unit_id"],
        "unit_name": unit_name,
        "candidate_area_m2": round(calculated.candidate_area_m2, 2),
        "candidate_area_mu": round(calculated.candidate_area_m2 / SQUARE_METRES_PER_MU, 2),
        "valid_observation_area_m2": round(calculated.valid_observation_area_m2, 2),
    }


def _write_business_result(
    payload: dict[str, Any],
    manifest: dict[str, Any],
    statistics: list[dict[str, Any]],
    operation_id: str,
    result_revision: int,
) -> tuple[str, Path]:
    task_id = f"{payload['scene_id']}-model-candidate"
    root = Path(os.getenv("OGE_BUSINESS_RESULTS_DIR", _project_root() / "data/derived/business-cycle"))
    directory = root / task_id
    directory.mkdir(parents=True, exist_ok=True)
    total_mu = round(sum(item["candidate_area_mu"] for item in statistics), 2)
    result = {
        "task_id": task_id,
        "result_version": result_revision,
        "parent_result_version": result_revision - 1 if result_revision > 1 else None,
        "feedback": None,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "parameter_pending",
        "business_scope": f"{payload['scene_id']}模型候选分析范围",
        "crop_type": "rice",
        "model_target": payload["target"],
        "growth_stage": payload["growth_stage"],
        "calculation_formula": "W = A_mu * M_m3_per_mu",
        "total_candidate_area_mu": total_mu,
        "total_reference_irrigation_demand_m3": None,
        "parameter_basis": {
            "stage_quota_status": "missing",
            "statement": "模型候选面积已自动统计；分阶段定额未确认，不生成正式需水量。",
        },
        "units": [
            {
                "unit_id": item["unit_id"],
                "unit_name": item["unit_name"],
                "candidate_area_m2": item["candidate_area_m2"],
                "candidate_area_mu": item["candidate_area_mu"],
                "growth_stage": payload["growth_stage"],
                "irrigation_quota_m3_per_mu": None,
                "reference_irrigation_demand_m3": None,
                "area_source": "model_candidate_mask",
                "demand_share": None,
                "attention_level": "pending",
                "quality_statement": "模型候选成果待复核；阶段定额缺失。",
                "remote_sensing_evidence": {
                    "operation_id": operation_id,
                    "run_id": manifest["run_id"],
                    "status": manifest["status"],
                    "checkpoint_sha256": manifest["model"]["checkpoint_sha256"],
                    "threshold": manifest["model"]["threshold"],
                    "area_statistic_id": item["statistic_id"],
                    "area_statistic_revision": item["revision"],
                },
            }
            for item in statistics
        ],
        "limitations": [
            "Model output is a review-required candidate result, not a final audited area.",
            "Stage irrigation quota is not available; no formal demand is produced.",
        ],
    }
    output = directory / "demand-result.json"
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    versions = directory / "versions"
    versions.mkdir(exist_ok=True)
    (versions / f"revision-{result_revision}.json").write_text(serialized, encoding="utf-8")
    output.write_text(serialized, encoding="utf-8")
    return task_id, output


def execute_model_pipeline_operation(
    factory: sessionmaker[Session], operation_id: str
) -> None:
    """Execute one durable operation; every unit statistic has its own transaction."""

    try:
        _operation_status(factory, operation_id, status="running")
        with factory.begin() as session:
            operation = session.get(OperationRow, operation_id)
            if operation is None:
                raise LookupError(f"operation {operation_id!r} was not found")
            payload = dict(operation.request_payload)
            attempt = session.scalar(
                select(func.coalesce(func.max(OperationAttemptRow.attempt_number), 0)).where(
                    OperationAttemptRow.operation_id == operation_id
                )
            )
            now = datetime.now(UTC)
            session.add(
                OperationAttemptRow(
                    operation_id=operation_id,
                    attempt_number=int(attempt) + 1,
                    worker_id=f"local-worker-{os.getpid()}",
                    started_at=now,
                    heartbeat_at=now,
                    finished_at=None,
                    status="running",
                    log_reference=None,
                )
            )
        output_directory = (
            _project_root() / "data" / "derived" / "model-pipeline" / operation_id
        )
        output_directory.mkdir(parents=True, exist_ok=True)
        manifest_path = _run_inference(payload, output_directory)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mask_path = (output_directory / "candidate-mask.tif").resolve()
        result_revision = _register_remote_result(
            factory, payload, manifest, mask_path, operation_id
        )
        statistics = [
            _calculate_unit_statistic(
                factory,
                payload,
                unit,
                result_revision=result_revision,
                mask_path=mask_path,
                operation_id=operation_id,
            )
            for unit in payload["units"]
        ]
        task_id, business_path = _write_business_result(
            payload, manifest, statistics, operation_id, result_revision
        )
        summary = {
            "result_id": payload["result_id"],
            "result_revision": result_revision,
            "model_run_id": manifest["run_id"],
            "manifest_path": str(manifest_path),
            "area_statistics": statistics,
            "business_result_task_id": task_id,
            "business_result_path": str(business_path),
        }
        with factory.begin() as session:
            attempt_row = session.scalar(
                select(OperationAttemptRow)
                .where(OperationAttemptRow.operation_id == operation_id)
                .order_by(OperationAttemptRow.attempt_number.desc())
                .limit(1)
            )
            if attempt_row:
                attempt_row.status = "succeeded"
                attempt_row.finished_at = datetime.now(UTC)
                attempt_row.heartbeat_at = attempt_row.finished_at
                attempt_row.log_reference = str(manifest_path)
        _operation_status(factory, operation_id, status="succeeded", result_summary=summary)
    except (OSError, ValueError, LookupError, RuntimeError, RasterioError, SQLAlchemyError) as error:
        with factory.begin() as session:
            attempt_row = session.scalar(
                select(OperationAttemptRow)
                .where(OperationAttemptRow.operation_id == operation_id)
                .order_by(OperationAttemptRow.attempt_number.desc())
                .limit(1)
            )
            if attempt_row:
                attempt_row.status = "failed"
                attempt_row.finished_at = datetime.now(UTC)
                attempt_row.heartbeat_at = attempt_row.finished_at
        _operation_status(
            factory,
            operation_id,
            status="failed",
            error_code=type(error).__name__,
            error_message=str(error)[:4000],
        )


def claim_next_model_pipeline_operation(
    factory: sessionmaker[Session],
) -> str | None:
    """Claim one queued operation without allowing another worker to take it."""

    with factory.begin() as session:
        row = session.scalar(
            select(OperationRow)
            .where(
                OperationRow.operation_type == "model_result_pipeline",
                OperationRow.status == "queued",
            )
            .order_by(OperationRow.submitted_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        row.status = "running"
        row.started_at = datetime.now(UTC)
        return row.operation_id
