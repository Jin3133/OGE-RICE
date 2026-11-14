"""Small transport middleware with no business behavior."""

from __future__ import annotations

import re
from uuid import uuid4

from fastapi import FastAPI, Request

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")


def _request_id(value: str | None) -> str:
    if value and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())


def install_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = _request_id(request.headers.get("Request-Id"))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["Request-Id"] = request_id
        return response
