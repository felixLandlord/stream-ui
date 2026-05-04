"""
Stream-ui test suite.

Tests cover:
- Decorator behaviour (non-interference, stacking, metadata retrieval)
- Registry discovery
- Mount routes (endpoint list API, UI serving)
- SSE connection
- WebSocket connection
"""

import asyncio
import json
import sys
import os

import pytest
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from stream_ui import StreamUI, sse_endpoint, ws_endpoint
from stream_ui.decorators import get_meta
from stream_ui.registry import StreamUIRegistry


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_app() -> FastAPI:
    """Minimal FastAPI app used across tests."""
    app = FastAPI()

    @app.get("/stream/prices")
    @sse_endpoint(
        summary="Price feed",
        description="Live prices",
        tags=["Market"],
        params=[{"name": "symbol", "in": "query", "required": False, "default": "BTC"}],
    )
    async def prices(symbol: str = "BTC"):
        async def gen():
            yield f"data: {symbol}:100\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.websocket("/ws/echo")
    @ws_endpoint(summary="Echo", tags=["Sockets"], path="/ws/echo")
    async def echo(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                msg = await websocket.receive_text()
                await websocket.send_text(f"echo:{msg}")
        except WebSocketDisconnect:
            pass

    StreamUI(app, path="/stream-ui").mount()
    return app


# ─────────────────────────────────────────────────────────────────────────────
# Decorator tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDecorators:

    def test_sse_metadata_attached(self):
        @sse_endpoint(summary="Test SSE", tags=["T"])
        async def my_fn():
            pass

        meta = get_meta(my_fn)
        assert meta is not None
        assert meta.kind == "sse"
        assert meta.summary == "Test SSE"
        assert meta.tags == ["T"]

    def test_ws_metadata_attached(self):
        @ws_endpoint(summary="Test WS", path="/ws/test")
        async def my_ws():
            pass

        meta = get_meta(my_ws)
        assert meta is not None
        assert meta.kind == "ws"
        assert meta.path == "/ws/test"

    def test_decorator_does_not_alter_function(self):
        """The original function must be callable and return the same result."""

        @sse_endpoint(summary="Passthrough")
        async def returns_hello():
            return "hello"

        result = asyncio.run(returns_hello())
        assert result == "hello"

    def test_decorator_stacking_order_independent(self):
        """Metadata survives stacking in either order."""

        @sse_endpoint(summary="Stacked above")
        async def fn_above():
            return "above"

        async def outer(fn):
            return fn

        # Simulate another decorator wrapping fn_above afterward
        import functools

        @functools.wraps(fn_above)
        async def wrapped(*args, **kwargs):
            return await fn_above(*args, **kwargs)

        wrapped.__wrapped__ = fn_above
        meta = get_meta(wrapped)
        assert meta is not None
        assert meta.kind == "sse"

    def test_no_meta_on_plain_function(self):
        async def plain():
            pass

        assert get_meta(plain) is None

    def test_params_stored_on_meta(self):
        params = [{"name": "limit", "in": "query", "required": False, "default": 10}]

        @sse_endpoint(summary="With params", params=params)
        async def parameterised():
            pass

        meta = get_meta(parameterised)
        assert meta.params == params

    def test_ws_endpoint_defaults(self):
        @ws_endpoint()
        async def bare_ws():
            pass

        meta = get_meta(bare_ws)
        assert meta.kind == "ws"
        assert meta.summary == ""
        assert meta.tags == []
        assert meta.params == []


# ─────────────────────────────────────────────────────────────────────────────
# Registry tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRegistry:

    def test_discovers_sse_endpoint(self):
        app = make_app()
        registry = StreamUIRegistry().build(app)
        paths = [ep.path for ep in registry.endpoints]
        assert "/stream/prices" in paths

    def test_discovers_ws_endpoint(self):
        app = make_app()
        registry = StreamUIRegistry().build(app)
        kinds = {ep.path: ep.meta.kind for ep in registry.endpoints}
        assert kinds.get("/ws/echo") == "ws"

    def test_endpoint_count(self):
        app = make_app()
        registry = StreamUIRegistry().build(app)
        # 2 streaming endpoints registered in make_app
        assert len(registry.endpoints) == 2

    def test_as_json_serialisable(self):
        app = make_app()
        registry = StreamUIRegistry().build(app)
        data = registry.as_json()
        assert isinstance(data, list)
        # Must be JSON-serialisable without error
        json.dumps(data)

    def test_endpoint_meta_preserved(self):
        app = make_app()
        registry = StreamUIRegistry().build(app)
        ep = next(e for e in registry.endpoints if e.path == "/stream/prices")
        assert ep.meta.summary == "Price feed"
        assert ep.meta.tags == ["Market"]

    def test_no_false_positives(self):
        """Unannotated routes should not appear in the registry."""
        app = FastAPI()

        @app.get("/plain")
        async def plain():
            return {"ok": True}
        registry = StreamUIRegistry().build(app)
        assert len(registry.endpoints) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Mount / HTTP route tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMount:

    def setup_method(self):
        self.app = make_app()
        self.client = TestClient(self.app, raise_server_exceptions=True)

    def test_ui_returns_200(self):
        res = self.client.get("/stream-ui")
        assert res.status_code == 200
        assert "Stream-ui" in res.text

    def test_ui_with_trailing_slash(self):
        res = self.client.get("/stream-ui/")
        assert res.status_code == 200

    def test_endpoints_api_returns_json(self):
        res = self.client.get("/stream-ui/_endpoints")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_endpoints_api_contains_sse(self):
        res = self.client.get("/stream-ui/_endpoints")
        endpoints = res.json()
        kinds = {ep["kind"] for ep in endpoints}
        assert "sse" in kinds

    def test_endpoints_api_contains_ws(self):
        res = self.client.get("/stream-ui/_endpoints")
        endpoints = res.json()
        kinds = {ep["kind"] for ep in endpoints}
        assert "ws" in kinds

    def test_custom_mount_path(self):
        app = FastAPI()
        StreamUI(app, path="/devtools").mount()
        client = TestClient(app)
        res = client.get("/devtools")
        assert res.status_code == 200

    def test_streamdeck_not_in_openapi_schema(self):
        """StreamDeck routes must not pollute the app's OpenAPI schema."""
        app = make_app()
        schema = app.openapi()
        paths = schema.get("paths", {})
        for path in paths:
            assert not path.startswith("/stream-ui"), f"Unexpected path in schema: {path}"

    def test_ui_contains_config(self):
        """Config JSON should be embedded in the served HTML."""
        res = self.client.get("/stream-ui")
        assert "base_path" in res.text

    def test_default_token_embedded(self):
        app = FastAPI()
        StreamUI(app, default_token="test-tok-123").mount()
        client = TestClient(app)
        res = client.get("/stream-ui")
        assert "test-tok-123" in res.text


# ─────────────────────────────────────────────────────────────────────────────
# SSE streaming test
# ─────────────────────────────────────────────────────────────────────────────

class TestSSEStream:

    def test_sse_returns_event_stream_content_type(self):
        app = make_app()
        client = TestClient(app, raise_server_exceptions=False)
        with client.stream("GET", "/stream/prices") as res:
            assert res.headers["content-type"].startswith("text/event-stream")

    def test_sse_emits_data(self):
        app = make_app()
        client = TestClient(app, raise_server_exceptions=False)
        events = []
        with client.stream("GET", "/stream/prices?symbol=ETH") as res:
            for line in res.iter_lines():
                if line.startswith("data:"):
                    events.append(line)
                    break  # only need one event
        assert len(events) == 1
        assert "ETH" in events[0]


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket test
# ─────────────────────────────────────────────────────────────────────────────

class TestWebSocket:

    def test_ws_echo(self):
        app = make_app()
        client = TestClient(app)
        with client.websocket_connect("/ws/echo") as ws:
            ws.send_text("hello")
            response = ws.receive_text()
        assert response == "echo:hello"

    def test_ws_multiple_messages(self):
        app = make_app()
        client = TestClient(app)
        with client.websocket_connect("/ws/echo") as ws:
            for i in range(5):
                ws.send_text(str(i))
                assert ws.receive_text() == f"echo:{i}"


# ─────────────────────────────────────────────────────────────────────────────
# Network drop simulation tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNetworkDropScenarios:

    def test_unreliable_sse_stream_drops_after_10_events(self):
        app = FastAPI()

        @app.get("/events/unreliable")
        @sse_endpoint(summary="Unreliable", tags=["Test"])
        async def unreliable():
            async def gen():
                for i in range(10):
                    yield f"data: {json.dumps({'count': i})}\n\n"
                    await asyncio.sleep(0.01)
            return StreamingResponse(gen(), media_type="text/event-stream")

        StreamUI(app).mount()
        client = TestClient(app, raise_server_exceptions=False)

        events = []
        disconnected = False
        try:
            with client.stream("GET", "/events/unreliable") as res:
                for line in res.iter_lines():
                    if line.startswith("data:"):
                        events.append(line)
        except Exception:
            disconnected = True

        assert disconnected or len(events) == 10

    def test_unreliable_sse_emits_reconnect_event(self):
        app = FastAPI()

        @app.get("/events/unreliable")
        @sse_endpoint(summary="Unreliable", tags=["Test"])
        async def unreliable():
            async def gen():
                for i in range(10):
                    if i == 9:
                        yield "event: reconnect\ndata: {}\n\n"
                    else:
                        yield f"data: {json.dumps({'count': i})}\n\n"
            return StreamingResponse(gen(), media_type="text/event-stream")

        StreamUI(app).mount()
        client = TestClient(app, raise_server_exceptions=False)

        reconnect_seen = False
        with client.stream("GET", "/events/unreliable") as res:
            for line in res.iter_lines():
                if line.startswith("event:"):
                    reconnect_seen = True
                    break

        assert reconnect_seen

    def test_flaky_ws_sends_heartbeats_then_drops(self):
        app = FastAPI()

        @app.websocket("/ws/flaky")
        @ws_endpoint(summary="Flaky", tags=["Test"], path="/ws/flaky")
        async def flaky(websocket: WebSocket):
            await websocket.accept()
            for i in range(5):
                await websocket.send_text(json.dumps({"type": "heartbeat", "count": i + 1}))
                await asyncio.sleep(0.01)
            await websocket.send_text(json.dumps({"type": "dropping", "reason": "simulated"}))
            await websocket.close()

        StreamUI(app).mount()
        client = TestClient(app)

        with client.websocket_connect("/ws/flaky") as ws:
            heartbeats = 0
            saw_drop = False
            for _ in range(10):
                msg = ws.receive_text()
                data = json.loads(msg)
                if data["type"] == "heartbeat":
                    heartbeats += 1
                elif data["type"] == "dropping":
                    saw_drop = True
                    break

            assert heartbeats == 5
            assert saw_drop