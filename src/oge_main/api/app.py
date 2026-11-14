"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute

from oge_main.api.errors import install_exception_handlers
from oge_main.api.middleware import install_request_id_middleware
from oge_main.api.router import api_router

API_PREFIX = "/api/v1"


def operation_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags else "default"
    return f"{tag}-{route.name}"


def create_app() -> FastAPI:
    app = FastAPI(
        title="禾灌智析业务API",
        version="1.0.0",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        generate_unique_id_function=operation_id,
    )
    install_request_id_middleware(app)
    install_exception_handlers(app)
    app.include_router(api_router, prefix=API_PREFIX)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("oge_main.api.app:app", host="127.0.0.1", port=8000, reload=False)
