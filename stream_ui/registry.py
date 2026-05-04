"""
Stream-ui endpoint registry.

Responsible for walking a FastAPI application's route table and collecting
all endpoints annotated with @sse_endpoint or @ws_endpoint.

This is intentionally kept separate from the mount logic so it can be
tested independently and reused if needed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from starlette.routing import Route, WebSocketRoute

from .decorators import EndpointMeta, get_meta


class RegisteredEndpoint:
    """A fully-resolved streaming endpoint entry."""

    __slots__ = ("path", "meta")

    def __init__(self, path: str, meta: EndpointMeta) -> None:
        self.path = path
        meta.path = path  # backfill path onto meta
        self.meta = meta

    def to_dict(self) -> dict:
        return self.meta.to_dict()


class StreamUIRegistry:
    """
    Discovers streaming endpoints from a FastAPI app.

    Call .build(app) after all routes have been registered.
    """

    def __init__(self) -> None:
        self._endpoints: List[RegisteredEndpoint] = []

    def build(self, app: FastAPI) -> "StreamUIRegistry":
        """Walk the app route table and collect annotated endpoints."""
        self._endpoints.clear()

        for route in _iter_routes(app):
            endpoint_fn = getattr(route, "endpoint", None)
            if endpoint_fn is None:
                continue

            meta = get_meta(endpoint_fn)
            if meta is None:
                continue

            path = route.path  # type: ignore[attr-defined]
            methods = list(getattr(route, "methods", []))

            # For SSE routes, the path comes from the route itself.
            # For WS routes, it also comes from the route — but we allow
            # the decorator to override with an explicit path= kwarg.
            resolved_path = meta.path or path

            # Backfill methods discovered from the FastAPI route table
            meta.methods = methods

            self._endpoints.append(RegisteredEndpoint(path=resolved_path, meta=meta))

        return self

    @property
    def endpoints(self) -> List[RegisteredEndpoint]:
        return list(self._endpoints)

    def as_json(self) -> List[dict]:
        """Serialisable list of endpoint descriptors for the UI."""
        return [ep.to_dict() for ep in self._endpoints]

    def openapi_params_for(self, path: str) -> List[dict]:
        """
        Look up OpenAPI-sourced parameter list for a path.
        Used to merge OpenAPI params with decorator-supplied hints.
        """
        for ep in self._endpoints:
            if ep.path == path:
                return ep.meta.params
        return []


def _iter_routes(app: FastAPI):
    """Yield all Route and WebSocketRoute objects from a FastAPI app."""
    routers_seen = set()

    def walk(router: Any) -> None:
        router_id = id(router)
        if router_id in routers_seen:
            return
        routers_seen.add(router_id)

        for route in getattr(router, "routes", []):
            if isinstance(route, (Route, WebSocketRoute)):
                yield route
            # Recurse into mounted sub-applications / APIRouter
            if hasattr(route, "app"):
                yield from walk(route.app)
            if hasattr(route, "router"):
                yield from walk(route.router)

    yield from walk(app)


def build_openapi_param_index(openapi_schema: dict) -> Dict[str, List[dict]]:
    """
    Build a path -> [param, ...] index from an OpenAPI schema dict.

    Handles GET/POST/etc. for SSE routes (typically GET with query params).
    WebSocket routes don't appear in OpenAPI so they come purely from
    decorator hints.
    """
    index: Dict[str, List[dict]] = {}
    paths = openapi_schema.get("paths", {})

    for path, methods in paths.items():
        params: List[dict] = []
        for _method, op in methods.items():
            if not isinstance(op, dict):
                continue
            for p in op.get("parameters", []):
                params.append(
                    {
                        "name": p.get("name", ""),
                        "in": p.get("in", "query"),
                        "description": p.get("description", ""),
                        "required": p.get("required", False),
                        "default": p.get("schema", {}).get("default", ""),
                        "type": p.get("schema", {}).get("type", "string"),
                    }
                )
            # Take params from the first method found
            if params:
                break
        if params:
            index[path] = params

    return index