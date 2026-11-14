"""Error translation at the HTTP boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from oge_main.api.contracts import ErrorDetail, ErrorResponse


@dataclass(slots=True)
class ApiProblem(Exception):
    status_code: int
    code: str
    message: str
    field_name: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _response(request: Request, problem: ApiProblem) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code=problem.code,
            message=problem.message,
            field=problem.field_name,
            details=problem.details,
            request_id=_request_id(request),
        )
    )
    return JSONResponse(status_code=problem.status_code, content=payload.model_dump())


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def handle_api_problem(request: Request, error: ApiProblem) -> JSONResponse:
        return _response(request, error)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        first = error.errors()[0] if error.errors() else {}
        location = first.get("loc", ())
        field_name = ".".join(str(part) for part in location) or None
        return _response(
            request,
            ApiProblem(
                status_code=422,
                code="CONTRACT_VALIDATION_FAILED",
                message="request does not satisfy the API contract",
                field_name=field_name,
                details={"errors": error.errors()},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        code = "RESOURCE_NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR"
        return _response(
            request,
            ApiProblem(
                status_code=error.status_code,
                code=code,
                message=str(error.detail),
            ),
        )
