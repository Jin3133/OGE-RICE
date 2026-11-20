"""Durable model-to-statistics pipeline operations."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from oge_main.api.contracts import ModelPipelineCreate, ModelPipelineOperationResponse
from oge_main.api.dependencies import get_database_session
from oge_main.api.errors import ApiProblem
from oge_main.infrastructure.database.models import IdempotencyRecordRow, OperationRow

router = APIRouter(prefix="/model-pipeline-operations", tags=["model-pipeline"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _response(row: OperationRow) -> ModelPipelineOperationResponse:
    summary: dict[str, Any] = row.result_summary or {}
    return ModelPipelineOperationResponse(
        operation_id=row.operation_id,
        status=row.status,
        submitted_by=row.submitted_by,
        submitted_at=row.submitted_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        result_id=summary.get("result_id"),
        result_revision=summary.get("result_revision"),
        area_statistics=summary.get("area_statistics", []),
        business_result_task_id=summary.get("business_result_task_id"),
        error_code=row.error_code,
        error_message=row.error_message,
    )


@router.post(
    "",
    response_model=ModelPipelineOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_model_pipeline_operation(
    payload: ModelPipelineCreate,
    session: DatabaseSession,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=100)
    ],
) -> ModelPipelineOperationResponse:
    request_body = payload.model_dump(mode="json")
    request_hash = hashlib.sha256(
        json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    existing = session.get(IdempotencyRecordRow, (payload.changed_by, idempotency_key))
    if existing:
        if existing.request_hash != request_hash:
            raise ApiProblem(409, "IDEMPOTENCY_KEY_REUSED", "idempotency key was reused")
        if existing.resource_type == "model_pipeline_operation" and existing.resource_id:
            operation = session.get(OperationRow, existing.resource_id)
            if operation is not None:
                return _response(operation)
        raise ApiProblem(409, "IDEMPOTENCY_RECORD_INVALID", "pipeline idempotency record is invalid")
    now = datetime.now(UTC)
    row = OperationRow(
        operation_id=f"op_{uuid4().hex}",
        operation_type="model_result_pipeline",
        status="queued",
        submitted_by=payload.changed_by,
        target_resource_type="remote_sensing_result",
        target_resource_id=payload.result_id,
        target_revision=None,
        submitted_at=now,
        started_at=None,
        finished_at=None,
        error_code=None,
        error_message=None,
        request_payload=request_body,
        result_summary=None,
    )
    session.add(row)
    session.add(
        IdempotencyRecordRow(
            actor_id=payload.changed_by,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="completed",
            response_status=status.HTTP_202_ACCEPTED,
            resource_type="model_pipeline_operation",
            resource_id=row.operation_id,
            resource_revision=None,
            response_body=None,
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
    )
    try:
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        raise ApiProblem(
            503, "DATABASE_UNAVAILABLE", "pipeline operation could not be queued"
        ) from error
    return _response(row)


@router.get("/{operation_id}", response_model=ModelPipelineOperationResponse)
def get_model_pipeline_operation(
    operation_id: str, session: DatabaseSession
) -> ModelPipelineOperationResponse:
    row = session.get(OperationRow, operation_id)
    if row is None or row.operation_type != "model_result_pipeline":
        raise ApiProblem(404, "PIPELINE_OPERATION_NOT_FOUND", "pipeline operation was not found")
    return _response(row)
