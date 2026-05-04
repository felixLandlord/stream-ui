# fastapi-stream-ui

**Interactive streaming API explorer for FastAPI** — built for SSE and WebSocket endpoints.

Stream-ui mounts directly into your FastAPI app (just like `/docs` or `/redoc`) and gives you a live UI to connect, test, and watch streaming endpoints in real time.

```bash
pip install fastapi-stream-ui
```

---

## Quickstart

```python
from fastapi import FastAPI
from stream_ui import StreamUI, sse_endpoint, ws_endpoint

app = FastAPI()

@app.get("/events")
@sse_endpoint(summary="Live event feed", tags=["Streaming"])
async def events():
    ...

@app.websocket("/ws/chat")
@ws_endpoint(summary="Chat socket", tags=["Streaming"], path="/ws/chat")
async def chat(websocket): ...

StreamUI(app).mount()
# → http://localhost:8000/stream-ui
```

---

## Decorators

### `@sse_endpoint(...)`

Marks a route as a Server-Sent Events endpoint for Stream-ui discovery.

```python
@app.get("/stream/prices")
@sse_endpoint(
    summary="Price ticker",
    description="Streams live market prices.",
    tags=["Market"],
    params=[
        {
            "name": "symbol",
            "in": "query",
            "description": "Asset symbol to track",
            "required": False,
            "default": "BTC",
            "type": "string",
        }
    ],
)
async def prices(symbol: str = "BTC"):
    async def gen():
        while True:
            yield f"data: {symbol}:{get_price()}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream")
```

### `@ws_endpoint(...)`

Marks a WebSocket route for Stream-ui discovery.

```python
@app.websocket("/ws/echo")
@ws_endpoint(
    summary="Echo socket",
    description="Echoes every message back.",
    tags=["Sockets"],
    path="/ws/echo",   # required — WS routes aren't in OpenAPI
)
async def echo(websocket: WebSocket):
    await websocket.accept()
    while True:
        msg = await websocket.receive_text()
        await websocket.send_text(f"echo: {msg}")
```

### Decorator parameters

| Parameter     | Type            | Description                                                |
|---------------|-----------------|------------------------------------------------------------|
| `summary`     | `str`           | Short label shown in the sidebar                           |
| `description` | `str`           | Longer description shown below the toolbar (markdown ok)  |
| `tags`        | `list[str]`     | Grouping tags (same convention as FastAPI)                 |
| `path`        | `str \| None`   | Override the route path (required for WS routes)          |
| `params`      | `list[dict]`    | Extra param hints (see below)                             |

#### Param dict shape

```python
{
    "name": "symbol",          # field name
    "in": "query",             # "query" | "path"
    "description": "...",      # tooltip / placeholder
    "required": False,
    "default": "BTC",
    "type": "string",          # for future type-aware inputs
}
```

> **Note:** For SSE routes, Stream-ui also auto-reads params from the OpenAPI schema — `params=` is for adding hints that FastAPI can't infer (e.g. dynamic query params), or for overriding descriptions.

---

## Stacking decorators

Decorators are **order-independent** and **non-interfering**. Both of these work:

```python
# @sse_endpoint above @app.get
@sse_endpoint(summary="Feed")
@app.get("/feed")
async def feed(): ...

# @sse_endpoint below @app.get  (more idiomatic)
@app.get("/feed")
@sse_endpoint(summary="Feed")
async def feed(): ...
```

Stream-ui walks the `__wrapped__` chain so the metadata is found regardless of position.

---

## Auth

Stream-ui handles auth the same way Swagger UI does — you provide credentials once in the sidebar, and they are injected into every connection.

**Bearer token:**  Injected as `Authorization: Bearer <token>` (HTTP header for SSE, query param `_token` as fallback, included in WS URL query string).

**API key:** Optional `X-API-Key` header field (enable with `enable_api_key=True`).

```python
StreamUI(
    app,
    default_token="dev-secret-token",  # pre-fills the auth panel
    enable_api_key=True,
).mount()
```

On the server side, check both header and fallback query param:

```python
def get_token(
    authorization: str | None = Header(default=None),
    _token: str | None = Query(default=None),
):
    if authorization:
        return authorization.removeprefix("Bearer ").strip()
    return _token
```

---

## `StreamUI` options

```python
StreamUI(
    app,
    path="/stream-ui",        # URL prefix (default: "/stream-ui")
    title="Stream-ui",        # Browser tab title
    default_token=None,       # Pre-fill bearer token field
    enable_api_key=True,      # Show API key field in auth panel
).mount()
```

---

## License

Apache License 2.0
