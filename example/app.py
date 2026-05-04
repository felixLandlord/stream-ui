r"""
Stream-ui example app.

Run with:
    uv sync && source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
    uvicorn example.app:app --reload

Endpoints:
  SSE:
    GET /events/ticker  - Price ticker (use ?symbol=BTC)
    GET /events/system  - System health (cpu, memory, disk events)
    GET /events/logs    - Application log tail (?level=INFO)
  WebSocket:
    WS /ws/echo   - Echoes messages back
    WS /ws/chat   - Broadcast chat room (?username=...)
    WS /ws/calc   - JSON calculator ({op, a, b})

Then open: http://localhost:8000/stream-ui
"""

import asyncio
import json
import random
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

# Import Stream-ui
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from stream_ui import StreamUI, sse_endpoint, ws_endpoint

app = FastAPI(
    title="Stream-ui Example",
    description="Demonstrates SSE and WebSocket endpoints with Stream-ui.",
)


# ── SSE: Simple ticker ─────────────────────────────────────────────────────

@app.get("/events/ticker", tags=["Streaming"])
@sse_endpoint(
    summary="Price ticker",
    description="Streams fake market price updates every second. "
                "Use `symbol` to filter by asset.",
    tags=["Streaming"],
)
async def price_ticker(symbol: str = "BTC"):
    """Streams SSE price updates for a given symbol."""

    async def generate() -> AsyncIterator[str]:
        price = 42_000.0
        for i in range(300):  # auto-close after 5 min
            price += random.uniform(-200, 200)
            payload = json.dumps({
                "symbol": symbol,
                "price": round(price, 2),
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            yield f"data: {payload}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── SSE: Named events ──────────────────────────────────────────────────────

@app.get("/events/system", tags=["Streaming"])
@sse_endpoint(
    summary="System health feed",
    description="Emits named SSE events: `cpu`, `memory`, and `disk`.",
    tags=["Streaming"],
)
async def system_health():
    """SSE stream with multiple named event types."""

    async def generate() -> AsyncIterator[str]:
        while True:
            for event_type in ("cpu", "memory", "disk"):
                value = random.randint(10, 90)
                yield f"event: {event_type}\ndata: {json.dumps({'value': value, 'unit': '%'})}\n\n"
                await asyncio.sleep(0.8)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── SSE: Slow log stream ───────────────────────────────────────────────────

@app.get("/events/logs", tags=["Streaming"])
@sse_endpoint(
    summary="Application log tail",
    description="Tails application logs. Set `level` to filter by severity.",
    tags=["Streaming"],
    params=[
        {
            "name": "level",
            "in": "query",
            "description": "Log level filter",
            "required": False,
            "default": "INFO",
            "type": "string",
        }
    ],
)
async def log_tail(level: str = "INFO"):
    """Fake log tail endpoint."""

    LEVELS = ["DEBUG", "INFO", "INFO", "WARN", "ERROR"]
    MESSAGES = [
        "Request processed successfully",
        "Cache miss for key user:42",
        "Retrying connection to upstream",
        "Slow query detected: 320ms",
        "Worker heartbeat OK",
        "Rate limit approaching for client 10.0.0.1",
    ]

    async def generate() -> AsyncIterator[str]:
        while True:
            log_level = random.choice(LEVELS)
            if LEVELS.index(log_level) >= LEVELS.index(level.upper() if level.upper() in LEVELS else "INFO"):
                msg = random.choice(MESSAGES)
                payload = json.dumps({
                    "level": log_level,
                    "message": msg,
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
                yield f"data: {payload}\n\n"
            await asyncio.sleep(random.uniform(0.5, 2.0))

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── SSE: Broken (POST-only) ────────────────────────────────────────────────

@app.post("/events/broken", tags=["Streaming"])
@sse_endpoint(
    summary="Broken POST endpoint",
    description="This endpoint is intentionally POST-only to demonstrate Stream-ui's method warning system. "
                "Since standard SSE (EventSource) requires GET, this will show an alert in the UI.",
    tags=["Streaming"],
)
async def broken_sse():
    """A POST-only SSE endpoint that will trigger UI warnings."""
    async def generate() -> AsyncIterator[str]:
        yield "data: this will never be reached via Stream-ui\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")


# ── WebSocket: Echo ────────────────────────────────────────────────────────

@app.websocket("/ws/echo")
@ws_endpoint(
    summary="Echo socket",
    description="Echoes every message back. Useful for testing WS connectivity.",
    tags=["WebSocket"],
    path="/ws/echo",
)
async def ws_echo(websocket: WebSocket):
    """Simple WebSocket echo endpoint."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"echo: {data}")
    except WebSocketDisconnect:
        pass


# ── WebSocket: Chat room (broadcast) ──────────────────────────────────────

_chat_clients: list[WebSocket] = []


@app.websocket("/ws/chat")
@ws_endpoint(
    summary="Broadcast chat room",
    description="Multi-client chat room. Messages are broadcast to all connected clients.\n\n"
                "Connect multiple browser tabs to see it in action.",
    tags=["WebSocket"],
    path="/ws/chat",
    params=[
        {
            "name": "username",
            "in": "query",
            "description": "Your display name",
            "required": False,
            "default": "anonymous",
            "type": "string",
        }
    ],
)
async def ws_chat(websocket: WebSocket, username: str = "anonymous"):
    """Broadcast WebSocket chat room."""
    await websocket.accept()
    _chat_clients.append(websocket)
    join_msg = json.dumps({"system": True, "message": f"{username} joined"})
    for client in _chat_clients:
        await client.send_text(join_msg)
    try:
        while True:
            text = await websocket.receive_text()
            payload = json.dumps({"from": username, "message": text, "ts": datetime.now(timezone.utc).isoformat()})
            for client in _chat_clients:
                await client.send_text(payload)
    except WebSocketDisconnect:
        _chat_clients.remove(websocket)
        leave_msg = json.dumps({"system": True, "message": f"{username} left"})
        for client in _chat_clients:
            await client.send_text(leave_msg)


# ── WebSocket: JSON calculator ─────────────────────────────────────────────

@app.websocket("/ws/calc")
@ws_endpoint(
    summary="JSON calculator",
    description='Send JSON like `{{"op": "add", "a": 5, "b": 3}}` and get results back.\n\n'
                'Ops: `add`, `sub`, `mul`, `div`',
    tags=["WebSocket"],
    path="/ws/calc",
)
async def ws_calc(websocket: WebSocket):
    """JSON-based calculator over WebSocket."""
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                req = json.loads(raw)
                a, b, op = req["a"], req["b"], req["op"]
                ops = {"add": a + b, "sub": a - b, "mul": a * b, "div": a / b if b != 0 else None}
                result = ops.get(op)
                await websocket.send_text(json.dumps({"result": result, "op": op}))
            except Exception as e:
                await websocket.send_text(json.dumps({"error": str(e)}))
    except WebSocketDisconnect:
        pass


# ── SSE: Unreliable stream (simulates network drops) ───────────────────────

@app.get("/events/unreliable", tags=["Streaming"])
@sse_endpoint(
    summary="Unreliable stream (network drops)",
    description="Simulates a flaky network connection. "
                "Every ~10 events the stream drops and reconnects automatically. "
                "Useful for testing reconnection handling in the UI.",
    tags=["Streaming"],
)
async def unreliable_stream():
    """SSE stream that periodically drops and reconnects."""

    async def generate() -> AsyncIterator[str]:
        counter = 0
        reconnect_count = 0
        while True:
            counter += 1
            if counter % 10 == 0:
                reconnect_count += 1
                yield f"event: reconnect\ndata: {json.dumps({'attempt': reconnect_count})}\n\n"
                break
            payload = json.dumps({
                "counter": counter,
                "message": "still connected" if counter % 5 != 0 else "drop incoming",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            yield f"data: {payload}\n\n"
            await asyncio.sleep(0.5)
        return

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── WebSocket: Flaky connection (heartbeat + drops) ───────────────────────

@app.websocket("/ws/flaky")
@ws_endpoint(
    summary="Flaky WebSocket (heartbeat + drops)",
    description="Simulates an unstable WebSocket connection. "
                "Sends periodic heartbeat messages and occasionally drops the connection. "
                "Useful for testing reconnection logic in the UI.\n\n"
                "Heartbeats are sent every 3 seconds. Connection drops every ~5 heartbeats.",
    tags=["WebSocket"],
    path="/ws/flaky",
)
async def ws_flaky(websocket: WebSocket):
    """WebSocket that sends heartbeats and periodically drops."""
    await websocket.accept()
    heartbeat_count = 0
    try:
        while True:
            heartbeat_count += 1
            await websocket.send_text(json.dumps({
                "type": "heartbeat",
                "count": heartbeat_count,
                "ts": datetime.now(timezone.utc).isoformat(),
            }))
            if heartbeat_count % 5 == 0:
                await websocket.send_text(json.dumps({
                    "type": "dropping",
                    "reason": "simulated_network_drop",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }))
                break
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass


# ── Mount Stream-ui ───────────────────────────────────────────────────────

stream_ui = StreamUI(
    app,
    path="/stream-ui",
    title="Stream-ui Example",
    enable_api_key=True,
)

stream_ui.mount()

# ── Health check ───────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("example.app:app", host="0.0.0.0", port=8000, reload=True)