"""
Stream-ui mount logic.

Attaches the /stream-ui UI and its companion API routes to a FastAPI app.
Mirrors how FastAPI mounts /docs and /redoc — a single function call, no
extra servers, no external dependencies.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from .registry import StreamUIRegistry, build_openapi_param_index
from .ui import render_ui


def mount_stream_ui(
    app: FastAPI,
    *,
    path: str = "/stream-ui",
    title: str = "Stream-ui",
    # Auth token that the UI will pre-populate into the Bearer field.
    # Mirrors how swagger_ui_init_oauth works in FastAPI.
    default_token: Optional[str] = None,
    # Whether to include a query-param based API key field alongside Bearer.
    enable_api_key: bool = True,
) -> None:
    """
    Mount the Stream-ui streaming API explorer onto a FastAPI application.

    Call this after all routes have been registered (or at startup via a
    lifespan handler if routes are added dynamically).

    Args:
        app:            The FastAPI application instance.
        path:           URL prefix for the Stream-ui UI. Default: "/stream-ui".
        title:          Browser tab title.
        default_token:  Pre-fill the Bearer token field (dev convenience).
        enable_api_key: Show an API-key field in addition to Bearer token.

    Example::

        app = FastAPI()

        @app.get("/events")
        @sse_endpoint(summary="Live feed")
        async def events(): ...

        mount_stream_ui(app)
        # UI now available at http://localhost:8000/stream-ui
    """
    registry = StreamUIRegistry()   

    # ------------------------------------------------------------------ #
    # Internal API — consumed by the embedded UI via fetch()              #
    # ------------------------------------------------------------------ #

    @app.get(f"{path}/_endpoints", include_in_schema=False)
    async def _list_endpoints() -> JSONResponse:
        """Return all discovered streaming endpoints as JSON."""
        # Rebuild on every call so dynamic routes are always reflected.
        registry.build(app)

        # Merge OpenAPI params (query/path) for SSE endpoints.
        try:
            schema = app.openapi()
            param_index = build_openapi_param_index(schema)
        except Exception:
            param_index = {}

        endpoints = registry.as_json()
        for ep in endpoints:
            path_key = ep["path"]
            if ep["kind"] == "sse" and path_key in param_index:
                # Decorator-supplied params take precedence; fill gaps from OpenAPI.
                existing_names = {p["name"] for p in ep["params"]}
                for p in param_index[path_key]:
                    if p["name"] not in existing_names:
                        ep["params"].append(p)

        return JSONResponse(content=endpoints)

    # ------------------------------------------------------------------ #
    # UI — served as a self-contained HTML page                           #
    # ------------------------------------------------------------------ #

    ui_config = {
        "title": title,
        "base_path": path,
        "default_token": default_token or "",
        "enable_api_key": enable_api_key,
    }

    @app.get(path, include_in_schema=False)
    @app.get(f"{path}/", include_in_schema=False)
    async def _stream_ui_ui() -> HTMLResponse:
        return HTMLResponse(content=render_ui(ui_config))