"""
Local web control panel for Spike (voice_commands.py's command/knowledge
system) -- a second front-end alongside discord_bot.py, same pattern:
imports voice_commands directly, own in-memory TOTP unlock state, own
response-capture sink. Runs as its own separate process, so it does not
share unlock/session state with a concurrently-running Discord bot -- each
front-end has its own copy of the module's globals, same as the existing
local-console vs Discord split.

SECURITY:
  - Binds to 127.0.0.1 only -- never 0.0.0.0. Not reachable from another
    machine on your network, let alone the internet, unless you explicitly
    change the bind address yourself (don't, unless you also add real auth
    beyond the TOTP admin gate -- this has none for the non-sensitive
    endpoints).
  - Sensitive commands still go through the same TOTP gate as every other
    front-end (send the code via the Unlock box in the UI).
  - Command execution reuses process_text() as-is -- same destructive/
    financial/credential refusals, same admin gate, nothing bypassed.

RUN: python control_panel.py
Then open http://127.0.0.1:5757 in a browser.
"""
import os
import re
import sys
import datetime
from flask import Flask, request, jsonify, send_file, Response

import voice_commands as vc

PORT = int(os.environ.get("CONTROL_PANEL_PORT", "5757"))

_unlocked = False


def webui_auth_check():
    return _unlocked


vc.set_admin_auth_check(webui_auth_check)

_responses = []


def webui_response_sink(text):
    _responses.append(text)


vc.set_response_sink(webui_response_sink)

app = Flask(__name__)


@app.route("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/api/status")
def api_status():
    return jsonify({
        "unlocked": _unlocked,
        "health": vc.do_health_check() if hasattr(vc, "do_health_check") else None,
    })


@app.route("/api/unlock", methods=["POST"])
def api_unlock():
    global _unlocked
    code = (request.json or {}).get("code", "").strip()
    if vc.check_admin_code(code):
        _unlocked = True
        return jsonify({"ok": True, "message": "unlocked, bro."})
    return jsonify({"ok": False, "message": "wrong or expired code -- still locked."})


@app.route("/api/command", methods=["POST"])
def api_command():
    global _responses
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify({"ok": False, "message": "empty command"})
    _responses = []
    vc._last_attachment_path = None
    try:
        vc.process_text(text.lower(), 0.0, "webui", text)
    except Exception as e:
        return jsonify({"ok": False, "message": f"hit an error running that: {e}"})
    attachment_url = None
    if vc._last_attachment_path and os.path.exists(vc._last_attachment_path):
        attachment_url = "/api/attachment?path=" + vc._last_attachment_path.replace("\\", "/")
    return jsonify({
        "ok": True,
        "responses": _responses or ["(didn't match anything)"],
        "attachment_url": attachment_url,
    })


@app.route("/api/attachment")
def api_attachment():
    # Only ever serves a path this same process just set via
    # _last_attachment_path (i.e. something process_text() itself produced),
    # not an arbitrary user-supplied path -- but double-check it's actually
    # under the experiments or vault dir before serving, as defense in depth.
    path = request.args.get("path", "")
    allowed_roots = [os.path.abspath(vc.EXPERIMENTS_DIR), os.path.abspath(vc.VAULT_DIR)]
    abspath = os.path.abspath(path)
    if not any(abspath.startswith(root) for root in allowed_roots) or not os.path.exists(abspath):
        return "not found", 404
    return send_file(abspath)


def _list_vault_notes():
    notes = []
    if not os.path.isdir(vc.VAULT_DIR):
        return notes
    for root, dirs, fnames in os.walk(vc.VAULT_DIR):
        if os.path.basename(root) == "attachments":
            continue
        for fname in fnames:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            title_m = re.search(r"^# (.+)$", content, re.M)
            status_m = re.search(r"^status: (.+)$", content, re.M)
            date_m = re.search(r"^date: (.+)$", content, re.M)
            notes.append({
                "file": fpath.replace("\\", "/"),
                "category": os.path.basename(root),
                "title": title_m.group(1) if title_m else fname,
                "status": status_m.group(1) if status_m else "",
                "date": date_m.group(1) if date_m else "",
            })
    notes.sort(key=lambda n: n["date"], reverse=True)
    return notes


@app.route("/api/vault")
def api_vault():
    return jsonify(_list_vault_notes()[:50])


@app.route("/api/vault/note")
def api_vault_note():
    path = request.args.get("file", "")
    abspath = os.path.abspath(path)
    if not abspath.startswith(os.path.abspath(vc.VAULT_DIR)) or not os.path.exists(abspath):
        return "not found", 404
    with open(abspath, encoding="utf-8") as f:
        content = f.read()
    return jsonify({"content": content})


INDEX_HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Spike Control Panel</title>
<style>
  :root {
    --bg: #0f1117; --panel: #161925; --border: #2a2f42; --text: #e4e7f0;
    --dim: #8a90a8; --accent: #7c9cff; --accent2: #ff7c9c; --good: #5ce6a0; --bad: #ff6b6b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", sans-serif; font-size: 14px;
  }
  header {
    padding: 16px 24px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
  }
  header h1 { font-size: 18px; margin: 0; letter-spacing: 0.5px; }
  header h1 span { color: var(--accent); }
  #statusPill {
    padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 600;
    border: 1px solid var(--border);
  }
  .layout { display: grid; grid-template-columns: 1fr 380px; gap: 0; height: calc(100vh - 57px); }
  .col { padding: 20px 24px; overflow-y: auto; }
  .col + .col { border-left: 1px solid var(--border); }
  @media (max-width: 820px) {
    .layout { grid-template-columns: 1fr; height: auto; }
    .col + .col { border-left: none; border-top: 1px solid var(--border); }
    #console { max-height: 40vh; }
  }
  .panel {
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 16px; margin-bottom: 16px;
  }
  .panel h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: var(--dim); margin: 0 0 12px; }
  #console { min-height: 200px; max-height: 45vh; overflow-y: auto; font-family: ui-monospace, monospace; font-size: 13px; }
  .msg { padding: 8px 0; border-bottom: 1px solid var(--border); white-space: pre-wrap; }
  .msg.you { color: var(--accent2); }
  .msg.spike { color: var(--text); }
  .msg img { max-width: 100%; border-radius: 6px; margin-top: 8px; display: block; }
  #cmdRow { display: flex; gap: 8px; margin-top: 12px; }
  input, button {
    background: #0d0f16; border: 1px solid var(--border); color: var(--text);
    border-radius: 6px; padding: 10px 12px; font-size: 14px; font-family: inherit;
  }
  #cmdInput { flex: 1; }
  button { cursor: pointer; background: var(--accent); color: #0d0f16; font-weight: 600; border: none; }
  button:hover { filter: brightness(1.1); }
  button.secondary { background: #0d0f16; color: var(--text); border: 1px solid var(--border); }
  .healthGrid { display: grid; grid-template-columns: 1fr auto; gap: 6px 12px; font-size: 13px; }
  .healthGrid .ok { color: var(--good); }
  .healthGrid .no { color: var(--bad); }
  .vaultItem {
    padding: 10px; border-radius: 8px; cursor: pointer; margin-bottom: 6px;
    border: 1px solid transparent;
  }
  .vaultItem:hover { background: #1d2130; border-color: var(--border); }
  .vaultItem .t { font-size: 13px; font-weight: 600; }
  .vaultItem .meta { font-size: 11px; color: var(--dim); margin-top: 2px; }
  #unlockRow { display: flex; gap: 8px; }
  #unlockRow input { width: 110px; }
  pre { white-space: pre-wrap; font-size: 12px; color: var(--dim); }
</style>
</head>
<body>
<header>
  <h1>&#9889; <span>Spike</span> Control Panel</h1>
  <div id="statusPill">checking...</div>
</header>
<div class="layout">
  <div class="col">
    <div class="panel">
      <h2>Console</h2>
      <div id="console"></div>
      <div id="cmdRow">
        <input id="cmdInput" placeholder="type a command, same as Discord..." autofocus>
        <button onclick="sendCommand()">Send</button>
      </div>
    </div>
  </div>
  <div class="col">
    <div class="panel">
      <h2>Admin Unlock</h2>
      <div id="unlockRow">
        <input id="unlockCode" placeholder="6-digit code" maxlength="6">
        <button class="secondary" onclick="unlock()">Unlock</button>
      </div>
    </div>
    <div class="panel">
      <h2>Health</h2>
      <div class="healthGrid" id="healthGrid">loading...</div>
    </div>
    <div class="panel">
      <h2>Vault History</h2>
      <div id="vaultList">loading...</div>
    </div>
  </div>
</div>
<script>
function addMsg(who, text, imgUrl) {
  const c = document.getElementById('console');
  const d = document.createElement('div');
  d.className = 'msg ' + who;
  d.textContent = (who === 'you' ? '> ' : '') + text;
  if (imgUrl) {
    const img = document.createElement('img');
    img.src = imgUrl;
    d.appendChild(img);
  }
  c.appendChild(d);
  c.scrollTop = c.scrollHeight;
}

async function sendCommand() {
  const input = document.getElementById('cmdInput');
  const text = input.value.trim();
  if (!text) return;
  addMsg('you', text);
  input.value = '';
  const r = await fetch('/api/command', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text})
  });
  const data = await r.json();
  if (data.ok) {
    (data.responses || []).forEach((resp, i) => {
      addMsg('spike', resp, i === data.responses.length - 1 ? data.attachment_url : null);
    });
  } else {
    addMsg('spike', data.message || 'error');
  }
  refreshVault();
}
document.getElementById('cmdInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendCommand();
});

async function unlock() {
  const code = document.getElementById('unlockCode').value.trim();
  const r = await fetch('/api/unlock', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({code})
  });
  const data = await r.json();
  addMsg('spike', data.message);
  document.getElementById('unlockCode').value = '';
  refreshStatus();
}

async function refreshStatus() {
  const r = await fetch('/api/status');
  const data = await r.json();
  const pill = document.getElementById('statusPill');
  pill.textContent = data.unlocked ? 'unlocked' : 'locked';
  pill.style.color = data.unlocked ? 'var(--good)' : 'var(--bad)';
  const grid = document.getElementById('healthGrid');
  if (data.health) {
    // e.g. "status: Claude CLI yes, Node yes, Playwright scripts no."
    const parts = data.health.replace(/^status:\s*/, '').replace(/\.$/, '').split(', ');
    grid.innerHTML = parts.map(p => {
      const m = p.match(/^(.*)\s+(yes|no)$/i);
      const label = m ? m[1] : p;
      const val = m ? m[2].toLowerCase() : '';
      return `<div>${label}</div><div class="${val === 'yes' ? 'ok' : val === 'no' ? 'no' : ''}">${val}</div>`;
    }).join('');
  } else {
    grid.textContent = 'unavailable';
  }
}

async function refreshVault() {
  const r = await fetch('/api/vault');
  const notes = await r.json();
  const list = document.getElementById('vaultList');
  list.innerHTML = '';
  notes.forEach(n => {
    const d = document.createElement('div');
    d.className = 'vaultItem';
    d.innerHTML = `<div class="t">${n.title}</div><div class="meta">${n.category} &middot; ${n.status} &middot; ${n.date.slice(0,16).replace('T',' ')}</div>`;
    d.onclick = () => showNote(n.file);
    list.appendChild(d);
  });
  if (!notes.length) list.innerHTML = '<div style="color:var(--dim)">nothing logged yet</div>';
}

async function showNote(file) {
  const r = await fetch('/api/vault/note?file=' + encodeURIComponent(file));
  const data = await r.json();
  addMsg('spike', data.content);
}

refreshStatus();
refreshVault();
setInterval(refreshStatus, 15000);
setInterval(refreshVault, 20000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"Spike control panel starting on http://127.0.0.1:{PORT}", flush=True)
    app.run(host="127.0.0.1", port=PORT, debug=False)
