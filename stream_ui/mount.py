"""
Stream-ui mount logic.

Attaches the /stream-ui UI and its companion API routes to a FastAPI app.
Mirrors how FastAPI mounts /docs and /redoc — a single class, no extra
servers, no external dependencies.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from .registry import StreamUIRegistry, build_openapi_param_index
from .ui import render_ui


class StreamUI:
    """
    Stream-ui streaming API explorer for FastAPI.

    Instantiate with your FastAPI app and configuration, then call mount()
    to attach the UI and its companion API routes.

    Args:
        app:            The FastAPI application instance.
        path:           URL prefix for the Stream-ui UI. Default: "/stream-ui".
        title:          Browser tab title.
        default_token:  Pre-fill the Bearer token field (dev convenience).
        enable_api_key: Show an API-key field in addition to Bearer token.

    Example::

        from fastapi import FastAPI
        from stream_ui import StreamUI, sse_endpoint

        app = FastAPI()

        @app.get("/events")
        @sse_endpoint(summary="Live feed")
        async def events(): ...

        stream_ui = StreamUI(app)
        stream_ui.mount()
        # UI now available at http://localhost:8000/stream-ui
    """

    def __init__(
        self,
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
        self.app = app
        self.path = path
        self.title = title
        self.default_token = default_token
        self.enable_api_key = enable_api_key

    def mount(self) -> None:
        """
        Mount the Stream-ui UI and internal API onto the FastAPI app.

        Call this after all routes have been registered (or at startup via a
        lifespan handler if routes are added dynamically).
        """
        registry = StreamUIRegistry()

        @self.app.get(f"{self.path}/_endpoints", include_in_schema=False)
        async def _list_endpoints() -> JSONResponse:
            """Return all discovered streaming endpoints as JSON."""
            # Rebuild on every call so dynamic routes are always reflected.
            registry.build(self.app)

            # Merge OpenAPI params (query/path) for SSE endpoints.
            try:
                schema = self.app.openapi()
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

        ui_config = {
            "title": self.title,
            "base_path": self.path,
            "default_token": self.default_token or "",
            "enable_api_key": self.enable_api_key,
        }

        @self.app.get(self.path, include_in_schema=False)
        @self.app.get(f"{self.path}/", include_in_schema=False)
        async def _stream_ui_ui() -> HTMLResponse:
            return HTMLResponse(content=render_ui(ui_config))