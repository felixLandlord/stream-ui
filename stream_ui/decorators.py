"""
Decorators for annotating streaming endpoints.

Design principles:
- Zero side-effects on the wrapped function — they remain fully callable
- Safe to stack with other decorators (e.g. @app.get + @sse_endpoint)
- Metadata is stored as a function attribute, never patching __wrapped__ chains
- Order-independent: @sse_endpoint can go above or below @app.get
"""

from __future__ import annotations

import functools
from typing import Any, Callable, List, Optional

# Attribute name used to carry Stream-ui metadata through decorator stacks
_STREAMUI_META_ATTR = "__stream_ui_meta__"


class EndpointMeta:
    """Metadata attached to an annotated endpoint function."""

    __slots__ = ("kind", "summary", "description", "tags", "path", "params")

    def __init__(
        self,
        kind: str,  # "sse" | "ws"
        summary: str,
        description: str,
        tags: List[str],
        path: Optional[str],
        params: List[dict],
    ) -> None:
        self.kind = kind
        self.summary = summary
        self.description = description
        self.tags = tags
        self.path = path  # resolved later during mount
        self.params = params

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "summary": self.summary,
            "description": self.description,
            "tags": self.tags,
            "path": self.path,
            "params": self.params,
        }


def _attach_meta(fn: Callable, meta: EndpointMeta) -> Callable:
    """
    Attach Stream-ui metadata to a function without altering its behaviour.

    We walk the __wrapped__ chain so the attribute is visible regardless of
    where in a decorator stack @sse_endpoint / @ws_endpoint sits.
    """
    # Attach on the original function itself
    setattr(fn, _STREAMUI_META_ATTR, meta)

    # Also attach on the outermost wrapper if this is being stacked
    # (functools.wraps copies __wrapped__; we set on both ends)
    inner = fn
    while hasattr(inner, "__wrapped__"):
        inner = inner.__wrapped__
        setattr(inner, _STREAMUI_META_ATTR, meta)

    return fn


def _make_decorator(
    kind: str,
    summary: str,
    description: str,
    tags: List[str],
    path: Optional[str],
    params: List[dict],
) -> Callable:
    meta = EndpointMeta(
        kind=kind,
        summary=summary,
        description=description,
        tags=tags,
        path=path,
        params=params,
    )

    def decorator(fn: Callable) -> Callable:
        # Preserve the original function completely — no wrapping needed
        _attach_meta(fn, meta)

        # If already wrapped (e.g. by @app.get), attach on the wrapper too
        # so registry lookup works regardless of reference used
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        _attach_meta(wrapper, meta)
        wrapper.__wrapped__ = fn  # standard introspection convention
        return wrapper

    return decorator


def sse_endpoint(
    *,
    summary: str = "",
    description: str = "",
    tags: Optional[List[str]] = None,
    path: Optional[str] = None,
    params: Optional[List[dict]] = None,
) -> Callable:
    """
    Mark a FastAPI route as a Server-Sent Events endpoint.

    Safe to combine with any other decorator. Does not alter function behaviour.

    Args:
        summary:     Short human-readable label shown in Stream-ui UI.
        description: Longer markdown description shown in the detail panel.
        tags:        Grouping tags (same convention as FastAPI tags).
        path:        Override the route path (auto-detected from OpenAPI if omitted).
        params:      Extra query/path param hints not captured by OpenAPI.
                     Each item: {"name": str, "in": "query"|"path", "description": str,
                                 "required": bool, "default": any}

    Example::

        @app.get("/events")
        @sse_endpoint(summary="Live event stream", tags=["Streaming"])
        async def live_events(topic: str = "all"):
            async def generate():
                while True:
                    yield f"data: tick\\n\\n"
                    await asyncio.sleep(1)
            return EventSourceResponse(generate())
    """
    return _make_decorator(
        kind="sse",
        summary=summary,
        description=description,
        tags=tags or [],
        path=path,
        params=params or [],
    )


def ws_endpoint(
    *,
    summary: str = "",
    description: str = "",
    tags: Optional[List[str]] = None,
    path: Optional[str] = None,
    params: Optional[List[dict]] = None,
) -> Callable:
    """
    Mark a FastAPI WebSocket route for Stream-ui discovery.

    Safe to combine with any other decorator. Does not alter function behaviour.

    Args:
        summary:     Short human-readable label shown in Stream-ui UI.
        description: Longer markdown description shown in the detail panel.
        tags:        Grouping tags (same convention as FastAPI tags).
        path:        Explicit route path (required for WebSocket routes since
                     they are not included in OpenAPI by default).
        params:      Query/path param hints.
                     Each item: {"name": str, "in": "query"|"path", "description": str,
                                 "required": bool, "default": any}

    Example::

        @app.websocket("/ws/chat")
        @ws_endpoint(summary="Chat socket", tags=["Chat"], path="/ws/chat")
        async def chat_socket(websocket: WebSocket):
            await websocket.accept()
            while True:
                msg = await websocket.receive_text()
                await websocket.send_text(f"echo: {msg}")
    """
    return _make_decorator(
        kind="ws",
        summary=summary,
        description=description,
        tags=tags or [],
        path=path,
        params=params or [],
    )


def get_meta(fn: Callable) -> Optional[EndpointMeta]:
    """Return Stream-ui metadata from a function, if present."""
    meta = getattr(fn, _STREAMUI_META_ATTR, None)
    if meta is not None:
        return meta
    # Walk __wrapped__ chain for deeply stacked decorators
    inner = fn
    while hasattr(inner, "__wrapped__"):
        inner = inner.__wrapped__
        meta = getattr(inner, _STREAMUI_META_ATTR, None)
        if meta is not None:
            return meta
    return None