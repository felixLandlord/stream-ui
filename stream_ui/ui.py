"""
Stream-ui UI renderer.

Produces a single self-contained HTML page (inline CSS + JS, no external deps
at runtime) that is served by FastAPI at the configured path.

The design is deliberately terminal/monitor-esque — dark, monospaced, precise.
Think: htop meets Postman, stripped to essentials.
"""

from __future__ import annotations

import json
from typing import Any, Dict


def render_ui(config: Dict[str, Any]) -> str:
    config_json = json.dumps(config)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{config["title"]}</title>
<style>
  /* ── Reset & Base ─────────────────────────────────────────────── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg:         #0d0f12;
    --bg-panel:   #13161b;
    --bg-input:   #1a1e26;
    --bg-hover:   #1e232d;
    --border:     #252b38;
    --border-lit: #3a4256;
    --text:       #c8d0e0;
    --text-dim:   #5c677d;
    --text-bright:#e8edf8;
    --accent-sse: #00d9a3;
    --accent-ws:  #7c6af7;
    --accent-err: #f05050;
    --accent-warn:#e8a93a;
    --accent-ok:  #3dd68c;
    --font-mono:  'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
    --font-ui:    'Inter', 'DM Sans', system-ui, sans-serif;
    --radius:     6px;
    --sidebar-w:  310px;
  }}

  html, body {{
    height: 100%; background: var(--bg); color: var(--text);
    font-family: var(--font-ui); font-size: 13px; line-height: 1.5;
    overflow: hidden;
  }}

  /* ── Layout ───────────────────────────────────────────────────── */
  #app {{ display: flex; height: 100vh; }}

  #sidebar {{
    width: var(--sidebar-w); flex-shrink: 0;
    background: var(--bg-panel);
    border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
    overflow: hidden;
  }}

  #main {{
    flex: 1; display: flex; flex-direction: column; overflow: hidden;
  }}

  /* ── Sidebar Header ───────────────────────────────────────────── */
  .sidebar-header {{
    padding: 16px 16px 12px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }}

  .logo {{
    display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
  }}

  .logo-icon {{
    width: 28px; height: 28px; flex-shrink: 0;
  }}

  .logo-text {{
    font-family: var(--font-mono); font-size: 15px; font-weight: 600;
    color: var(--text-bright); letter-spacing: -0.3px;
  }}

  .logo-version {{
    font-family: var(--font-mono); font-size: 10px; color: var(--text-dim);
    margin-left: auto;
  }}

  /* ── Auth Panel ───────────────────────────────────────────────── */
  .auth-panel {{
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 10px 12px;
  }}

  .auth-label {{
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text-dim); margin-bottom: 6px;
    display: flex; align-items: center; gap: 6px;
  }}

  .auth-label::before {{
    content: ''; width: 6px; height: 6px; border-radius: 50%;
    background: var(--accent-warn); display: inline-block;
    transition: background 0.2s;
  }}

  .auth-label.authed::before {{ background: var(--accent-ok); }}

  .auth-input {{
    width: 100%; background: transparent; border: none; outline: none;
    color: var(--text-bright); font-family: var(--font-mono); font-size: 11px;
    padding: 2px 0;
  }}

  .auth-input::placeholder {{ color: var(--text-dim); }}

  .auth-row {{ display: flex; gap: 6px; align-items: center; }}

  .auth-prefix {{
    font-family: var(--font-mono); font-size: 10px; color: var(--text-dim);
    white-space: nowrap;
  }}

  .auth-divider {{
    height: 1px; background: var(--border); margin: 6px 0;
  }}

  /* ── Endpoint List ────────────────────────────────────────────── */
  .ep-list-header {{
    padding: 10px 16px 6px;
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text-dim);
    display: flex; justify-content: space-between; align-items: center;
    flex-shrink: 0;
  }}

  #ep-count {{
    background: var(--bg-input); border: 1px solid var(--border);
    border-radius: 10px; padding: 1px 7px; font-size: 10px;
    color: var(--text-dim); font-family: var(--font-mono);
  }}

  #ep-list {{
    flex: 1; overflow-y: auto; padding: 4px 8px 16px;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}

  .ep-group-label {{
    padding: 8px 8px 4px;
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text-dim);
  }}

  .ep-item {{
    display: flex; align-items: center; gap: 8px;
    padding: 8px 10px; border-radius: var(--radius);
    cursor: pointer; transition: background 0.12s; margin-bottom: 2px;
    border: 1px solid transparent;
  }}

  .ep-item:hover {{ background: var(--bg-hover); border-color: var(--border); }}

  .ep-item.active {{
    background: var(--bg-hover); border-color: var(--border-lit);
  }}

  .ep-badge {{
    font-family: var(--font-mono); font-size: 9px; font-weight: 700;
    padding: 2px 6px; border-radius: 3px; letter-spacing: 0.5px;
    flex-shrink: 0; text-transform: uppercase;
  }}

  .ep-badge.sse {{
    background: rgba(0, 217, 163, 0.12); color: var(--accent-sse);
    border: 1px solid rgba(0, 217, 163, 0.25);
  }}

  .ep-badge.ws {{
    background: rgba(124, 106, 247, 0.12); color: var(--accent-ws);
    border: 1px solid rgba(124, 106, 247, 0.25);
  }}

  .ep-info {{ flex: 1; min-width: 0; }}

  .ep-path {{
    font-family: var(--font-mono); font-size: 11px; color: var(--text-bright);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}

  .ep-summary {{
    font-size: 11px; color: var(--text-dim);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}

  .ep-status-dot {{
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--border-lit); flex-shrink: 0;
    transition: background 0.2s;
  }}

  .ep-status-dot.live {{ background: var(--accent-ok); box-shadow: 0 0 6px var(--accent-ok); animation: pulse 1.5s infinite; }}
  .ep-status-dot.error {{ background: var(--accent-err); }}

  @keyframes pulse {{
    0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }}
  }}

  .empty-state {{
    text-align: center; padding: 32px 16px; color: var(--text-dim);
  }}
  .empty-state code {{
    font-family: var(--font-mono); font-size: 11px;
    background: var(--bg-input); padding: 2px 6px; border-radius: 3px;
  }}

  /* ── Main Toolbar ─────────────────────────────────────────────── */
  #toolbar {{
    padding: 12px 20px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 10px; flex-shrink: 0;
    background: var(--bg-panel);
  }}

  .toolbar-path {{
    flex: 1; font-family: var(--font-mono); font-size: 12px;
    color: var(--text-bright); background: var(--bg-input);
    border: 1px solid var(--border); border-radius: var(--radius);
    padding: 7px 12px; outline: none;
    transition: border-color 0.15s;
  }}
  .toolbar-path:focus {{ border-color: var(--border-lit); }}

  .btn {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 14px; border-radius: var(--radius); cursor: pointer;
    font-size: 12px; font-weight: 600; border: 1px solid transparent;
    transition: all 0.12s; white-space: nowrap; font-family: var(--font-ui);
  }}

  .btn-connect-sse {{
    background: rgba(0, 217, 163, 0.1); color: var(--accent-sse);
    border-color: rgba(0, 217, 163, 0.3);
  }}
  .btn-connect-sse:hover {{ background: rgba(0, 217, 163, 0.18); }}

  .btn-connect-ws {{
    background: rgba(124, 106, 247, 0.1); color: var(--accent-ws);
    border-color: rgba(124, 106, 247, 0.3);
  }}
  .btn-connect-ws:hover {{ background: rgba(124, 106, 247, 0.18); }}

  .btn-disconnect {{
    background: rgba(240, 80, 80, 0.1); color: var(--accent-err);
    border-color: rgba(240, 80, 80, 0.3);
  }}
  .btn-disconnect:hover {{ background: rgba(240, 80, 80, 0.18); }}

  .btn-clear {{
    background: transparent; color: var(--text-dim);
    border-color: var(--border);
  }}
  .btn-clear:hover {{ color: var(--text); border-color: var(--border-lit); }}

  .status-pill {{
    font-family: var(--font-mono); font-size: 10px; font-weight: 600;
    padding: 3px 10px; border-radius: 12px; letter-spacing: 0.3px;
    flex-shrink: 0;
  }}
  .status-pill.idle    {{ background: var(--bg-input); color: var(--text-dim); border: 1px solid var(--border); }}
  .status-pill.live    {{ background: rgba(61,214,140,0.12); color: var(--accent-ok); border: 1px solid rgba(61,214,140,0.3); animation: pulse 1.5s infinite; }}
  .status-pill.error   {{ background: rgba(240,80,80,0.12); color: var(--accent-err); border: 1px solid rgba(240,80,80,0.3); }}
  .status-pill.waiting {{ background: rgba(232,169,58,0.12); color: var(--accent-warn); border: 1px solid rgba(232,169,58,0.3); }}

  .status-pill.reconnecting {{ background: rgba(124,106,247,0.12); color: var(--accent-ws); border: 1px solid rgba(124,106,247,0.3); animation: pulse 0.8s infinite; }}

  /* ── Reconnect toggle ─────────────────────────────────────────── */
  .reconnect-row {{ display: flex; gap: 8px; align-items: center; margin-top: 6px; }}
  .reconnect-label {{ font-size: 10px; color: var(--text-dim); display: flex; align-items: center; gap: 4px; cursor: pointer; }}
  .reconnect-label input {{ accent-color: var(--accent-sse); }}

  /* ── Params Panel ─────────────────────────────────────────────── */
  #params-panel {{
    border-bottom: 1px solid var(--border); padding: 12px 20px;
    background: var(--bg-panel); flex-shrink: 0;
    display: none;
  }}

  #params-panel.visible {{ display: block; }}

  .params-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 8px;
  }}

  .param-field {{ display: flex; flex-direction: column; gap: 3px; }}

  .param-label {{
    font-size: 10px; font-weight: 600; color: var(--text-dim);
    display: flex; gap: 4px; align-items: center;
  }}

  .param-required {{
    color: var(--accent-err); font-size: 10px;
  }}

  .param-in {{
    font-size: 9px; background: var(--bg-input); border-radius: 3px;
    padding: 1px 5px; color: var(--text-dim); border: 1px solid var(--border);
  }}

  .param-input {{
    background: var(--bg-input); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 5px 9px;
    color: var(--text-bright); font-family: var(--font-mono); font-size: 11px;
    outline: none; transition: border-color 0.15s;
  }}
  .param-input:focus {{ border-color: var(--border-lit); }}

  /* ── WS Send Bar ──────────────────────────────────────────────── */
  #ws-send-bar {{
    display: none; padding: 10px 20px; border-bottom: 1px solid var(--border);
    background: var(--bg-panel); gap: 8px; align-items: center;
    flex-shrink: 0;
  }}
  #ws-send-bar.visible {{ display: flex; }}

  #ws-message {{
    flex: 1; background: var(--bg-input); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 7px 12px;
    color: var(--text-bright); font-family: var(--font-mono); font-size: 12px;
    outline: none; transition: border-color 0.15s;
  }}
  #ws-message:focus {{ border-color: var(--border-lit); }}
  #ws-message::placeholder {{ color: var(--text-dim); }}

  .btn-send {{
    background: rgba(124,106,247,0.12); color: var(--accent-ws);
    border-color: rgba(124,106,247,0.3);
    padding: 7px 14px;
  }}
  .btn-send:hover {{ background: rgba(124,106,247,0.22); }}

  /* ── Event Stream ─────────────────────────────────────────────── */
  #stream-container {{
    flex: 1; overflow: hidden; display: flex; flex-direction: column;
  }}

  #stream-header {{
    padding: 8px 20px; display: flex; align-items: center; gap: 10px;
    border-bottom: 1px solid var(--border); flex-shrink: 0;
  }}

  .stream-label {{
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text-dim); flex: 1;
  }}

  #event-count {{
    font-family: var(--font-mono); font-size: 10px; color: var(--text-dim);
  }}

  #stream-output {{
    flex: 1; overflow-y: auto; padding: 12px 20px;
    font-family: var(--font-mono); font-size: 12px; line-height: 1.8;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}

  .ev {{
    display: flex; gap: 12px; align-items: flex-start;
    padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.02);
    animation: fadeIn 0.12s ease;
  }}

  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(2px); }} to {{ opacity: 1; transform: none; }} }}

  .ev-time  {{ color: var(--text-dim); flex-shrink: 0; width: 70px; font-size: 11px; }}
  .ev-dir   {{ flex-shrink: 0; width: 14px; }}
  .ev-dir.in  {{ color: var(--accent-sse); }}
  .ev-dir.in-ws {{ color: var(--accent-ws); }}
  .ev-dir.out {{ color: var(--accent-warn); }}
  .ev-dir.sys {{ color: var(--text-dim); }}
  .ev-dir.err {{ color: var(--accent-err); }}
  .ev-data  {{ flex: 1; color: var(--text); word-break: break-all; white-space: pre-wrap; }}
  .ev-data.err {{ color: var(--accent-err); }}
  .ev-data.sys {{ color: var(--text-dim); font-style: italic; }}
  .ev-event {{ color: var(--accent-warn); font-size: 10px; }}

  .placeholder {{
    color: var(--text-dim); padding: 40px 0; text-align: center;
    font-size: 12px;
  }}

  /* ── Detail panel below main ──────────────────────────────────── */
  #description-bar {{
    padding: 8px 20px; border-top: 1px solid var(--border);
    background: var(--bg-panel); font-size: 11px; color: var(--text-dim);
    flex-shrink: 0; display: none; min-height: 32px;
  }}
  #description-bar.visible {{ display: block; }}

  /* ── Scrollbar global ─────────────────────────────────────────── */
  ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
  ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}

  /* ── Responsive ───────────────────────────────────────────────── */
  @media (max-width: 700px) {{
    :root {{ --sidebar-w: 240px; }}
    .logo-text {{ font-size: 13px; }}
  }}
</style>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600&display=swap" />
</head>
<body>

<div id="app">

  <!-- ── Sidebar ─────────────────────────────────────────── -->
  <aside id="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <svg class="logo-icon" viewBox="0 0 28 28" fill="none">
          <rect width="28" height="28" rx="7" fill="#1a1e26"/>
          <rect x="6" y="8" width="3" height="12" rx="1.5" fill="#00d9a3"/>
          <rect x="11" y="5" width="3" height="18" rx="1.5" fill="#7c6af7"/>
          <rect x="16" y="10" width="3" height="8" rx="1.5" fill="#00d9a3" opacity="0.6"/>
          <rect x="21" y="7" width="3" height="14" rx="1.5" fill="#7c6af7" opacity="0.6"/>
        </svg>
        <span class="logo-text">Stream-ui</span>
        <span class="logo-version">v0.1</span>
      </div>

      <!-- Auth panel -->
      <div class="auth-panel">
        <div class="auth-label" id="auth-label">Authorization</div>
        <div class="auth-row">
          <span class="auth-prefix">Bearer</span>
          <input class="auth-input" id="bearer-token" type="password"
                 placeholder="paste token..." autocomplete="off"
                 oninput="onAuthChange()" />
        </div>
        <div class="auth-divider" id="apikey-divider" style="display:none"></div>
        <div id="apikey-row" style="display:none">
          <div class="auth-row">
            <span class="auth-prefix">API Key</span>
            <input class="auth-input" id="api-key" type="password"
                   placeholder="X-API-Key value..." autocomplete="off"
                   oninput="onAuthChange()" />
          </div>
        </div>
      </div>
    </div>

    <div class="ep-list-header">
      Endpoints <span id="ep-count">0</span>
    </div>

    <div id="ep-list">
      <div class="placeholder" id="ep-placeholder">
        Loading endpoints…
      </div>
    </div>
  </aside>

  <!-- ── Main ────────────────────────────────────────────── -->
  <main id="main">

    <!-- Toolbar -->
    <div id="toolbar">
      <input id="url-bar" class="toolbar-path" type="text"
             placeholder="Select an endpoint or type a path…"
             onkeydown="onUrlKeydown(event)" />
      <button class="btn btn-connect-sse" id="btn-sse" onclick="connectSSE()">
        ▶ Connect SSE
      </button>
      <button class="btn btn-connect-ws" id="btn-ws" onclick="connectWS()" style="display:none">
        ▶ Connect WS
      </button>
      <button class="btn btn-disconnect" id="btn-disconnect" onclick="disconnect()" style="display:none">
        ■ Disconnect
      </button>
      <button class="btn btn-clear" onclick="clearOutput()">Clear</button>
      <span class="status-pill idle" id="status-pill">idle</span>
    </div>

    <!-- Response headers display (shown when SSE connects) -->
    <div id="headers-panel" style="display:none; padding: 6px 20px; background: var(--bg-panel); border-bottom: 1px solid var(--border); font-family: var(--font-mono); font-size: 10px;">
      <span style="color: var(--text-dim);">Response headers:</span>
      <span id="response-headers" style="color: var(--text); margin-left: 8px;"></span>
    </div>

    <!-- Reconnect toggle (shown for SSE) -->
    <div id="reconnect-toggle" style="display:none; padding: 6px 20px; background: var(--bg-panel); border-bottom: 1px solid var(--border);">
      <label class="reconnect-label">
        <input type="checkbox" id="auto-reconnect" checked />
        Auto-reconnect on disconnect
      </label>
      <span id="reconnect-count" style="font-size:10px; color: var(--text-dim); margin-left: 16px; display:none">
        Reconnected <span id="reconnect-num">0</span>x
      </span>
    </div>

    <!-- Message queue (shown when WS disconnected with queued messages) -->
    <div id="msg-queue-bar" style="display:none; padding: 6px 20px; background: rgba(232,169,58,0.08); border-bottom: 1px solid var(--border);">
      <span id="queue-count" style="font-size:11px; color: var(--accent-warn);"></span>
      <button class="btn" style="padding:3px 10px; font-size:10px; margin-left:12px; background: var(--bg-input); border: 1px solid var(--border); color: var(--text); cursor:pointer" onclick="clearQueue()">Clear queue</button>
    </div>

    <!-- Params -->
    <div id="params-panel">
      <div class="params-grid" id="params-grid"></div>
    </div>

    <!-- WS send bar -->
    <div id="ws-send-bar">
      <input id="ws-message" type="text" placeholder='Send a message… (Enter to send, or JSON)'
             onkeydown="onWsMessageKey(event)" />
      <button class="btn btn-send" onclick="wsSend()">Send ↑</button>
    </div>

    <!-- Stream output -->
    <div id="stream-container">
      <div id="stream-header">
        <span class="stream-label">Event Stream</span>
        <span id="event-count" style="display:none">0 events</span>
        <button class="btn btn-clear" style="padding:3px 10px; font-size:11px"
                onclick="clearOutput()">↺ Clear</button>
      </div>
      <div id="stream-output">
        <div class="placeholder" id="output-placeholder">
          Select an endpoint from the sidebar and click Connect.
        </div>
      </div>
    </div>

    <!-- Description bar -->
    <div id="description-bar" id="desc-bar"></div>

  </main>
</div>

<script>
// ─────────────────────────────────────────────────────────────────────────────
// Stream-ui UI — self-contained, no external JS dependencies
// ─────────────────────────────────────────────────────────────────────────────

const CONFIG = {config_json};

// ── State ──────────────────────────────────────────────────────────────────
let state = {{
  endpoints: [],
  active: null,       // selected endpoint descriptor
  connection: null,   // EventSource | WebSocket | null
  kind: null,         // "sse" | "ws"
  eventCount: 0,
  dotRefs: {{}},       // path -> status dot element
  lastEventId: null,
  reconnectCount: 0,
  gracefulClose: false,
  msgQueue: [],
  wsTimeout: null,
}};

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {{
  if (CONFIG.default_token) {{
    document.getElementById('bearer-token').value = CONFIG.default_token;
    onAuthChange();
  }}
  if (CONFIG.enable_api_key) {{
    document.getElementById('apikey-divider').style.display = '';
    document.getElementById('apikey-row').style.display = '';
  }}
  await loadEndpoints();
}});

async function loadEndpoints() {{
  try {{
    const res = await fetch(`${{CONFIG.base_path}}/_endpoints`);
    state.endpoints = await res.json();
    renderSidebar();
  }} catch (e) {{
    document.getElementById('ep-placeholder').textContent = '⚠ Could not load endpoints';
  }}
}}

// ── Auth ───────────────────────────────────────────────────────────────────
function onAuthChange() {{
  const token = document.getElementById('bearer-token').value.trim();
  const key   = document.getElementById('api-key')?.value.trim() ?? '';
  const label = document.getElementById('auth-label');
  if (token || key) {{
    label.classList.add('authed');
  }} else {{
    label.classList.remove('authed');
  }}
}}

function getAuthHeaders() {{
  const headers = {{}};
  const token = document.getElementById('bearer-token').value.trim();
  const key   = document.getElementById('api-key')?.value.trim() ?? '';
  if (token) headers['Authorization'] = `Bearer ${{token}}`;
  if (key)   headers['X-API-Key'] = key;
  return headers;
}}

function getAuthQueryString() {{
  // For SSE (EventSource doesn't support custom headers natively in all browsers)
  // — append token as query param as a fallback. Server must check both.
  const token = document.getElementById('bearer-token').value.trim();
  const params = [];
  if (token) params.push(`_token=${{encodeURIComponent(token)}}`);
  return params.length ? '&' + params.join('&') : '';
}}

// ── Sidebar ────────────────────────────────────────────────────────────────
function renderSidebar() {{
  const list = document.getElementById('ep-list');
  const countEl = document.getElementById('ep-count');

  if (!state.endpoints.length) {{
    list.innerHTML = `<div class="empty-state">
      No streaming endpoints found.<br><br>
      Annotate your routes with<br>
      <code>@sse_endpoint</code> or <code>@ws_endpoint</code>
    </div>`;
    countEl.textContent = '0';
    return;
  }}

  countEl.textContent = state.endpoints.length;

  // Group by first tag, ungrouped last
  const groups = {{}};
  for (const ep of state.endpoints) {{
    const group = ep.tags?.[0] ?? 'General';
    if (!groups[group]) groups[group] = [];
    groups[group].push(ep);
  }}

  list.innerHTML = '';

  for (const [group, eps] of Object.entries(groups)) {{
    const labelEl = document.createElement('div');
    labelEl.className = 'ep-group-label';
    labelEl.textContent = group;
    list.appendChild(labelEl);

    for (const ep of eps) {{
      list.appendChild(makeEpItem(ep));
    }}
  }}
}}

function makeEpItem(ep) {{
  const div = document.createElement('div');
  div.className = 'ep-item';
  div.dataset.path = ep.path;

  const dot = document.createElement('div');
  dot.className = 'ep-status-dot';
  state.dotRefs[ep.path] = dot;

  div.innerHTML = `
    <span class="ep-badge ${{ep.kind}}">${{ep.kind.toUpperCase()}}</span>
    <div class="ep-info">
      <div class="ep-path" title="${{ep.path}}">${{ep.path}}</div>
      ${{ep.summary ? `<div class="ep-summary">${{ep.summary}}</div>` : ''}}
    </div>
  `;
  div.prepend(dot);
  div.onclick = () => selectEndpoint(ep);
  return div;
}}

// ── Endpoint selection ─────────────────────────────────────────────────────
function selectEndpoint(ep) {{
  if (state.connection) disconnect();

  state.active = ep;

  // Highlight sidebar item
  document.querySelectorAll('.ep-item').forEach(el => {{
    el.classList.toggle('active', el.dataset.path === ep.path);
  }});

  // URL bar
  document.getElementById('url-bar').value = ep.path;

  // Params panel
  renderParams(ep);

  // Show correct connect button
  document.getElementById('btn-sse').style.display = ep.kind === 'sse' ? '' : 'none';
  document.getElementById('btn-ws').style.display  = ep.kind === 'ws'  ? '' : 'none';
  document.getElementById('btn-disconnect').style.display = 'none';

  // WS send bar
  document.getElementById('ws-send-bar').classList.toggle('visible', ep.kind === 'ws');

  // Hide stale SSE / WS UI from previous connection
  document.getElementById('reconnect-toggle').style.display = 'none';
  document.getElementById('msg-queue-bar').style.display = 'none';
  document.getElementById('headers-panel').style.display = 'none';

  // Description
  const descBar = document.getElementById('description-bar');
  if (ep.description) {{
    descBar.textContent = ep.description;
    descBar.classList.add('visible');
  }} else {{
    descBar.classList.remove('visible');
  }}

  setStatus('idle', 'idle');
}}

// ── Params ─────────────────────────────────────────────────────────────────
function renderParams(ep) {{
  const panel = document.getElementById('params-panel');
  const grid  = document.getElementById('params-grid');

  if (!ep.params?.length) {{
    panel.classList.remove('visible');
    return;
  }}

  grid.innerHTML = '';
  for (const p of ep.params) {{
    const field = document.createElement('div');
    field.className = 'param-field';
    field.innerHTML = `
      <label class="param-label">
        ${{p.name}}
        ${{p.required ? '<span class="param-required">*</span>' : ''}}
        <span class="param-in">${{p.in ?? 'query'}}</span>
      </label>
      <input class="param-input" id="param-${{p.name}}"
             placeholder="${{p.default ?? p.description ?? ''}}"
             title="${{p.description ?? p.name}}" />
    `;
    grid.appendChild(field);
  }}

  panel.classList.add('visible');
}}

function collectParams(ep) {{
  if (!ep?.params?.length) return {{}};
  const values = {{}};
  for (const p of ep.params) {{
    const el = document.getElementById(`param-${{p.name}}`);
    if (el?.value.trim()) values[p.name] = el.value.trim();
  }}
  return values;
}}

function buildUrl(basePath, params) {{
  const qs = new URLSearchParams(params).toString();
  return qs ? `${{basePath}}?${{qs}}` : basePath;
}}

// ── SSE ────────────────────────────────────────────────────────────────────
function connectSSE() {{
  const ep = state.active;
  const path = document.getElementById('url-bar').value.trim() || ep?.path;
  if (!path) return;

  if (state.connection) disconnect();

  state.lastEventId = null;
  state.reconnectCount = 0;
  state.gracefulClose = false;

  document.getElementById('reconnect-toggle').style.display = '';
  document.getElementById('reconnect-count').style.display = 'none';
  document.getElementById('reconnect-num').textContent = '0';
  document.getElementById('headers-panel').style.display = 'none';

  const params = ep ? collectParams(ep) : {{}};
  const url = buildUrl(path, params) + getAuthQueryString();

  clearOutput();
  setStatus('waiting', 'connecting…');
  appendEvent('sys', null, `Connecting to ${{path}} …`);

  const es = new EventSource(url);
  state.connection = es;
  state.kind = 'sse';

  es.onopen = () => {{
    setStatus('live', 'connected');
    if (state.reconnectCount > 0) {{
      appendEvent('sys', null, `Reconnected (${{state.reconnectCount}}x)${{state.lastEventId ? ', last-id: ' + state.lastEventId : ''}}`);
    }} else {{
      appendEvent('sys', null, 'Connection established');
    }}
    setDot(path, 'live');
    toggleButtons(true);

    // Show headers (fetched via separate request since EventSource doesn't expose them)
    fetchHeaders(path, params);
  }};

  es.onmessage = (e) => {{
    if (e.lastEventId) state.lastEventId = e.lastEventId;
    appendEvent('in', e.lastEventId ? `id:${{e.lastEventId}}` : null, e.data);
  }};

  es.onerror = () => {{
    const autoReconnect = document.getElementById('auto-reconnect')?.checked ?? true;

    if (state.gracefulClose) {{
      setStatus('idle', 'closed by server');
      appendEvent('sys', null, 'Server ended the stream');
      setDot(path, '');
      state.connection = null;
      es.close();
      toggleButtons(false);
      return;
    }}

    // EventSource fires onerror with readyState=CONNECTING (not CLOSED) when the
    // server drops — the browser is natively retrying. We take over immediately.
    if (es.readyState !== EventSource.OPEN) {{
      es.close(); // stop the browser's own reconnect loop
      state.connection = null;

      if (!autoReconnect) {{
        setStatus('error', 'disconnected');
        appendEvent('err', null, 'Connection closed (auto-reconnect disabled)');
        setDot(path, 'error');
        toggleButtons(false);
        return;
      }}

      // Auto-reconnect with Last-Event-ID
      state.reconnectCount++;
      document.getElementById('reconnect-count').style.display = '';
      document.getElementById('reconnect-num').textContent = state.reconnectCount;

      setStatus('reconnecting', `reconnecting… (${{state.reconnectCount}})`);
      appendEvent('sys', null, `Connection lost, reconnecting…${{state.lastEventId ? ' (last-id: ' + state.lastEventId + ')' : ''}}`);
      setDot(path, 'error');
      toggleButtons(false);

      const newUrl = buildUrl(path, collectParams(ep)) + getAuthQueryString();
      setTimeout(() => {{
        if (state.kind === 'sse' && !state.connection) connectSSEWithUrl(path, newUrl, ep);
      }}, 2000);
    }}
  }};

  // Handle graceful close event
  es.addEventListener('close', () => {{
    state.gracefulClose = true;
    appendEvent('sys', null, 'Received close event from server');
  }}, true);

  // Named events via patch
  const origAdd = es.addEventListener.bind(es);
  es.addEventListener = (type, handler, opts) => {{
    if (type !== 'message' && type !== 'error' && type !== 'open' && type !== 'close') {{
      origAdd(type, (e) => {{
        appendEvent('in', `event:${{type}}`, e.data);
      }}, opts);
    }} else {{
      origAdd(type, handler, opts);
    }}
  }};
}}

function connectSSEWithUrl(path, url, ep) {{
  // null out any stale reference before creating a new one
  state.connection = null;
  state.gracefulClose = false;

  setStatus('waiting', 'reconnecting…');

  const es = new EventSource(url);
  state.connection = es;
  state.kind = 'sse';

  // Make sure the reconnect toggle stays visible
  document.getElementById('reconnect-toggle').style.display = '';

  es.onopen = () => {{
    setStatus('live', 'connected');
    appendEvent('sys', null, `Reconnected (${{state.reconnectCount}}x)${{state.lastEventId ? ', last-id: ' + state.lastEventId : ''}}`);
    // Update reconnect counter display
    document.getElementById('reconnect-count').style.display = '';
    document.getElementById('reconnect-num').textContent = state.reconnectCount;
    setDot(path, 'live');
    toggleButtons(true);
  }};

  es.onmessage = (e) => {{
    if (e.lastEventId) state.lastEventId = e.lastEventId;
    appendEvent('in', e.lastEventId ? `id:${{e.lastEventId}}` : null, e.data);
  }};

  es.onerror = () => {{
    const autoReconnect = document.getElementById('auto-reconnect')?.checked ?? true;

    if (state.gracefulClose) {{
      setStatus('idle', 'closed by server');
      appendEvent('sys', null, 'Server ended the stream');
      setDot(path, '');
      state.connection = null;
      es.close();
      toggleButtons(false);
      return;
    }}

    if (es.readyState !== EventSource.OPEN) {{
      es.close();
      state.connection = null;

      if (!autoReconnect) {{
        setStatus('error', 'disconnected');
        appendEvent('err', null, 'Connection closed (auto-reconnect disabled)');
        setDot(path, 'error');
        toggleButtons(false);
        return;
      }}

      // Continue auto-reconnecting
      state.reconnectCount++;
      document.getElementById('reconnect-count').style.display = '';
      document.getElementById('reconnect-num').textContent = state.reconnectCount;

      setStatus('reconnecting', `reconnecting… (${{state.reconnectCount}})`);
      appendEvent('sys', null, `Connection lost, reconnecting…${{state.lastEventId ? ' (last-id: ' + state.lastEventId + ')' : ''}}`);
      setDot(path, 'error');
      toggleButtons(false);

      const newUrl = buildUrl(path, collectParams(ep)) + getAuthQueryString();
      setTimeout(() => {{
        if (state.kind === 'sse' && !state.connection) connectSSEWithUrl(path, newUrl, ep);
      }}, 2000);
    }}
  }};

  // Handle graceful close event
  es.addEventListener('close', () => {{
    state.gracefulClose = true;
    appendEvent('sys', null, 'Received close event from server');
  }}, true);
}}

async function fetchHeaders(path, params) {{
  try {{
    const url = new URL(path, location.origin);
    const mergedParams = {{...collectParams(state.active), ...params}};
    Object.entries(mergedParams).forEach(([k, v]) => url.searchParams.append(k, v));
    const res = await fetch(url.toString(), {{ method: 'HEAD' }});
    const headers = [];
    res.headers.forEach((v, k) => headers.push(`${{k}}: ${{v}}`));
    if (headers.length) {{
      document.getElementById('headers-panel').style.display = '';
      document.getElementById('response-headers').textContent = headers.join(', ');
    }}
  }} catch (e) {{}}
}}

// ── WebSocket ──────────────────────────────────────────────────────────────
function connectWS() {{
  const ep = state.active;
  const path = document.getElementById('url-bar').value.trim() || ep?.path;
  if (!path) return;

  if (state.connection) disconnect();

  updateQueueBar();

  const params = ep ? collectParams(ep) : {{}};
  const token = document.getElementById('bearer-token').value.trim();
  if (token) params['_token'] = token;

  const wsPath = buildUrl(path, params);
  const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${{wsProto}}://${{location.host}}${{wsPath}}`;

  clearOutput();
  setStatus('waiting', 'connecting…');
  appendEvent('sys', null, `Connecting to ${{wsUrl}} …`);

  const ws = new WebSocket(wsUrl);
  state.connection = ws;
  state.kind = 'ws';

  ws.onopen = () => {{
    setStatus('live', 'connected');
    appendEvent('sys', null, 'WebSocket opened');
    setDot(path, 'live');
    toggleButtons(true);

    // Send queued messages
    if (state.msgQueue.length > 0) {{
      appendEvent('sys', null, `Sending ${{state.msgQueue.length}} queued message(s)…`);
      state.msgQueue.forEach((msg, i) => {{
        ws.send(msg);
        appendEvent('out', null, msg);
      }});
      appendEvent('sys', null, `${{state.msgQueue.length}} queued message(s) sent`);
      state.msgQueue = [];
      updateQueueBar();
    }}

    // Start idle timeout (disabled by default - set to 0 to enable, e.g. 30000 for 30s)
    // clearTimeout(state.wsTimeout);
    // state.wsTimeout = setTimeout(() => {{
    //   if (ws.readyState === WebSocket.OPEN) {{
    //     ws.close(1000, 'idle timeout');
    //   }}
    // }}, 30000);
  }};

  ws.onmessage = (e) => {{
    appendEvent('in-ws', null, e.data);
  }};

  ws.onclose = (e) => {{
    clearTimeout(state.wsTimeout);
    setStatus('idle', `closed (${{e.code}})`);
    appendEvent('sys', null, `WebSocket closed — code ${{e.code}}`);
    setDot(path, '');
    toggleButtons(false);
    state.connection = null;
    updateQueueBar();
  }};

  ws.onerror = () => {{
    setStatus('error', 'error');
    appendEvent('err', null, 'WebSocket error');
    setDot(path, 'error');
  }};
}};

function wsSend() {{
  const ws = state.connection;
  const input = document.getElementById('ws-message');
  const msg = input.value.trim();
  if (!msg) return;

  if (!ws || ws.readyState !== WebSocket.OPEN) {{
    // Queue message for when connection is restored
    state.msgQueue.push(msg);
    appendEvent('out', null, `[queued] ${{msg}}`);
    updateQueueBar();
    input.value = '';
    return;
  }}

  ws.send(msg);
  appendEvent('out', null, msg);
  input.value = '';
}}

function updateQueueBar() {{
  const bar = document.getElementById('msg-queue-bar');
  const count = document.getElementById('queue-count');
  if (state.msgQueue.length > 0) {{
    bar.style.display = '';
    count.textContent = `${{state.msgQueue.length}} message(s) queued — will send on reconnect`;
  }} else {{
    bar.style.display = 'none';
  }}
}}

function clearQueue() {{
  state.msgQueue = [];
  updateQueueBar();
  appendEvent('sys', null, 'Message queue cleared');
}}

function onWsMessageKey(e) {{
  if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); wsSend(); }}
}}

// ── Disconnect ─────────────────────────────────────────────────────────────
function disconnect() {{
  if (!state.connection) return;
  if (state.kind === 'sse') state.connection.close();
  if (state.kind === 'ws' && state.connection.readyState < 2)
    state.connection.close(1000, 'user disconnect');
  state.connection = null;
  clearTimeout(state.wsTimeout);
  setStatus('idle', 'disconnected');
  appendEvent('sys', null, 'Disconnected');
  toggleButtons(false);
  document.getElementById('reconnect-toggle').style.display = 'none';
  document.getElementById('headers-panel').style.display = 'none';
  const path = state.active?.path ?? '';
  if (path) setDot(path, '');
}}

// ── URL bar keyboard shortcut ──────────────────────────────────────────────
function onUrlKeydown(e) {{
  if (e.key === 'Enter') {{
    if (state.active?.kind === 'ws') connectWS();
    else connectSSE();
  }}
}}

// ── Output ─────────────────────────────────────────────────────────────────
function appendEvent(dir, label, data) {{
  const placeholder = document.getElementById('output-placeholder');
  if (placeholder) placeholder.remove();

  state.eventCount++;
  const countEl = document.getElementById('event-count');
  countEl.style.display = '';
  countEl.textContent = `${{state.eventCount}} event${{state.eventCount !== 1 ? 's' : ''}}`;

  const out = document.getElementById('stream-output');
  const now = new Date();
  const ts  = now.toTimeString().slice(0, 8) + '.' + String(now.getMilliseconds()).padStart(3, '0');

  const dirSymbols = {{
    'in':    '▼',
    'in-ws': '▼',
    'out':   '▲',
    'sys':   '·',
    'err':   '✕',
  }};

  const row = document.createElement('div');
  row.className = 'ev';
  row.innerHTML = `
    <span class="ev-time">${{ts}}</span>
    <span class="ev-dir ${{dir}}">${{dirSymbols[dir] ?? '?'}}</span>
    <span class="ev-data ${{dir === 'err' ? 'err' : dir === 'sys' ? 'sys' : ''}}">${{
      label ? `<span class="ev-event">[${{label}}]</span> ` : ''
    }}${{escHtml(data)}}</span>
  `;
  out.appendChild(row);

  // Auto-scroll to bottom
  out.scrollTop = out.scrollHeight;
}}

function clearOutput() {{
  const out = document.getElementById('stream-output');
  out.innerHTML = '<div class="placeholder" id="output-placeholder">Stream cleared. Ready to connect.</div>';
  state.eventCount = 0;
  document.getElementById('event-count').style.display = 'none';
}}

function escHtml(s) {{
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}}

// ── UI helpers ─────────────────────────────────────────────────────────────
function setStatus(cls, text) {{
  const el = document.getElementById('status-pill');
  el.className = `status-pill ${{cls}}`;
  el.textContent = text;
}}

function toggleButtons(isConnected) {{
  const ep = state.active;
  document.getElementById('btn-sse').style.display
    = (!isConnected && ep?.kind === 'sse') ? '' : 'none';
  document.getElementById('btn-ws').style.display
    = (!isConnected && ep?.kind === 'ws') ? '' : 'none';
  document.getElementById('btn-disconnect').style.display
    = isConnected ? '' : 'none';
}}

function setDot(path, cls) {{
  const dot = state.dotRefs[path];
  if (!dot) return;
  dot.className = 'ep-status-dot' + (cls ? ` ${{cls}}` : '');
}}
</script>
</body>
</html>"""