#!/usr/bin/env python3
"""
RTM Cloud — local cloud store for Industrial Numpad uploads.

- Creates the RTM Cloud on first run (if it does not exist)
- Accepts number uploads from the ESP32 (HTTP POST)
- Serves a small live dashboard in the browser

Usage:
  python server.py
  open http://127.0.0.1:8080
"""

from __future__ import annotations

import csv
import io
import json
import socket
import threading
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

HOST = "0.0.0.0"
PORT = 8080
CLOUD_NAME = "Industrial_Numpad_Cloud"
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
STORE_PATH = DATA_DIR / "cloud_store.json"
SIM_PATH = ROOT.parent / "simulation" / "index.html"
_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_cloud() -> dict:
    """Create RTM Cloud storage if missing; return cloud metadata + values."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        cloud = {
            "cloud": CLOUD_NAME,
            "created_at": utc_now(),
            "status": "active",
            "values": [],
        }
        STORE_PATH.write_text(json.dumps(cloud, indent=2), encoding="utf-8")
        print(f"[RTM Cloud] Created new cloud: {CLOUD_NAME}")
        return cloud

    with STORE_PATH.open(encoding="utf-8") as f:
        cloud = json.load(f)
    return cloud


def save_cloud(cloud: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cloud, indent=2), encoding="utf-8")
    tmp.replace(STORE_PATH)


def upload_value(value: str, device: str = "industrial-numpad") -> dict:
    with _lock:
        cloud = ensure_cloud()
        record = {
            "id": len(cloud.get("values", [])) + 1,
            "value": str(value),
            "device": device,
            "stored_at": utc_now(),
        }
        cloud.setdefault("values", []).append(record)
        cloud["updated_at"] = record["stored_at"]
        save_cloud(cloud)
        print(f"[RTM Cloud] Stored VALUE={record['value']} (id={record['id']})")
        return {"ok": True, "cloud": cloud["cloud"], "record": record}


def _xlsx_col(index: int) -> str:
    """1-based column index -> Excel column letters (1=A)."""
    name = ""
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def build_xlsx(values: list[dict], cloud_name: str) -> bytes:
    """Build a minimal .xlsx workbook with stdlib only (no pip packages)."""
    headers = ["ID", "Value", "Device", "Stored At (UTC)"]
    rows = [headers]
    for item in values:
        rows.append(
            [
                str(item.get("id", "")),
                str(item.get("value", "")),
                str(item.get("device", "")),
                str(item.get("stored_at", "")),
            ]
        )

    sheet_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, cell in enumerate(row, start=1):
            ref = f"{_xlsx_col(c_idx)}{r_idx}"
            # Keep values as text so leading zeros / long numbers stay intact
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{escape(cell)}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(cloud_name)[:31] or "Data"}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def build_csv(values: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Value", "Device", "Stored At (UTC)"])
    for item in values:
        writer.writerow(
            [
                item.get("id", ""),
                item.get("value", ""),
                item.get("device", ""),
                item.get("stored_at", ""),
            ]
        )
    return buf.getvalue().encode("utf-8-sig")  # BOM helps Excel open UTF-8


def local_ips() -> list[str]:
    ips = ["127.0.0.1"]
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    # also try UDP trick for primary LAN IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in ips:
            ips.insert(1, ip)
    except OSError:
        pass
    return ips


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RTM Cloud — Industrial Numpad</title>
  <style>
    :root {
      --bg: #10141c; --card: #1a2130; --line: #2c3648;
      --text: #e8eef8; --muted: #8b97ab; --ok: #3ecf8e; --accent: #4ea1ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
      background: radial-gradient(ellipse at top, #1a2740, var(--bg));
      color: var(--text); min-height: 100vh; padding: 28px 18px;
    }
    .wrap { max-width: 820px; margin: 0 auto; }
    h1 { margin: 0 0 6px; font-size: 1.5rem; }
    .sub { color: var(--muted); margin-bottom: 22px; }
    .card {
      background: var(--card); border: 1px solid var(--line);
      border-radius: 12px; padding: 16px 18px; margin-bottom: 16px;
    }
    .row { display: flex; gap: 18px; flex-wrap: wrap; }
    .pill {
      display: inline-block; padding: 4px 10px; border-radius: 999px;
      background: #143528; color: var(--ok); font-size: 0.82rem; font-weight: 600;
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
    th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line); }
    th { color: var(--muted); font-weight: 600; }
    code { color: var(--accent); }
    .empty { color: var(--muted); padding: 12px 0; }
    .btn {
      display: inline-block; padding: 8px 14px; border-radius: 6px;
      text-decoration: none; font-weight: 600; font-size: 0.9rem; border: 0; cursor: pointer;
    }
    .btn-excel { background: #217346; color: #fff; }
    .btn-excel:hover { filter: brightness(1.08); }
    .btn-csv { background: #333b4a; color: var(--text); border: 1px solid var(--line); }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-top: 12px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>RTM Cloud</h1>
    <p class="sub">Live store for Industrial Numpad submissions (press <b>A</b> on the keypad).</p>

    <div class="card row">
      <div>
        <div style="color:var(--muted);font-size:.8rem">Cloud</div>
        <div id="cloudName">—</div>
      </div>
      <div>
        <div style="color:var(--muted);font-size:.8rem">Status</div>
        <span class="pill" id="status">—</span>
      </div>
      <div>
        <div style="color:var(--muted);font-size:.8rem">Entries</div>
        <div id="count">0</div>
      </div>
      <div>
        <div style="color:var(--muted);font-size:.8rem">Created</div>
        <div id="created">—</div>
      </div>
    </div>

    <div class="card">
      <h2 style="margin:0;font-size:1.05rem">Download data</h2>
      <p style="color:var(--muted);font-size:.85rem;margin:8px 0 0">
        Export all stored numpad values for Excel.
      </p>
      <div class="actions">
        <a class="btn btn-excel" href="/api/export.xlsx">Download Excel (.xlsx)</a>
        <a class="btn btn-csv" href="/api/export.csv">Download CSV</a>
      </div>
    </div>

    <div class="card">
      <h2 style="margin:0 0 12px;font-size:1.05rem">Quick test upload</h2>
      <form id="testForm" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <input id="testValue" value="35" maxlength="16"
          style="padding:8px 10px;border-radius:6px;border:1px solid var(--line);background:#10141c;color:var(--text)" />
        <button type="submit"
          style="padding:8px 14px;border:0;border-radius:6px;background:var(--accent);color:#041018;font-weight:600;cursor:pointer">
          Upload to RTM Cloud
        </button>
        <a href="/sim" style="color:var(--accent)">Open keypad simulator →</a>
      </form>
      <div id="testMsg" style="margin-top:10px;color:var(--muted);font-size:.85rem"></div>
    </div>

    <div class="card">
      <h2 style="margin:0 0 12px;font-size:1.05rem">Stored numbers</h2>
      <div id="tableWrap"><div class="empty">Waiting for uploads…</div></div>
    </div>

    <div class="card" style="color:var(--muted);font-size:.85rem">
      Use the keypad at <code>/sim</code> (not the local file). ESP32:
      <code>POST /api/upload</code> · body
      <code>{"value":"35","device":"industrial-numpad"}</code>
    </div>
  </div>
  <script>
    async function refresh() {
      const r = await fetch('/api/cloud');
      const data = await r.json();
      document.getElementById('cloudName').textContent = data.cloud;
      document.getElementById('status').textContent = data.status || 'active';
      document.getElementById('created').textContent = data.created_at || '—';
      const values = (data.values || []).slice().reverse();
      document.getElementById('count').textContent = values.length;
      const wrap = document.getElementById('tableWrap');
      if (!values.length) {
        wrap.innerHTML = '<div class="empty">Waiting for uploads…</div>';
        return;
      }
      wrap.innerHTML = `<table>
        <thead><tr><th>#</th><th>Value</th><th>Device</th><th>Stored at (UTC)</th></tr></thead>
        <tbody>${values.map(v =>
          `<tr><td>${v.id}</td><td><strong>${v.value}</strong></td><td>${v.device||''}</td><td>${v.stored_at||''}</td></tr>`
        ).join('')}</tbody></table>`;
    }
    document.getElementById('testForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const value = document.getElementById('testValue').value.trim();
      const msg = document.getElementById('testMsg');
      try {
        const r = await fetch('/api/upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value, device: 'dashboard-test' }),
        });
        const data = await r.json();
        msg.textContent = r.ok ? ('Stored OK: ' + JSON.stringify(data.record)) : ('FAIL: ' + JSON.stringify(data));
        msg.style.color = r.ok ? 'var(--ok)' : '#ff6b6b';
        refresh();
      } catch (err) {
        msg.textContent = 'ERROR: ' + err.message;
        msg.style.color = '#ff6b6b';
      }
    });
    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "RTMCloud/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[HTTP] {self.address_string()} - {fmt % args}")

    def _send(
        self,
        code: int,
        body: bytes,
        content_type: str,
        filename: str | None = None,
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{filename}"'
            )
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _send_export(self, kind: str) -> None:
        with _lock:
            cloud = ensure_cloud()
            values = list(cloud.get("values", []))
            cloud_name = str(cloud.get("cloud") or CLOUD_NAME)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if kind == "xlsx":
            body = build_xlsx(values, cloud_name)
            self._send(
                200,
                body,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=f"{cloud_name}_{stamp}.xlsx",
            )
            print(f"[RTM Cloud] Excel export: {len(values)} rows")
            return

        body = build_csv(values)
        self._send(
            200,
            body,
            "text/csv; charset=utf-8",
            filename=f"{cloud_name}_{stamp}.csv",
        )
        print(f"[RTM Cloud] CSV export: {len(values)} rows")

    def do_OPTIONS(self) -> None:
        self._send(204, b"", "text/plain")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, DASHBOARD_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path in ("/sim", "/sim/", "/simulator"):
            if SIM_PATH.exists():
                html = SIM_PATH.read_text(encoding="utf-8")
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            else:
                self._json(404, {"ok": False, "error": "sim_missing", "path": str(SIM_PATH)})
            return
        if path == "/api/cloud":
            with _lock:
                cloud = ensure_cloud()
            self._json(200, cloud)
            return
        if path == "/api/values":
            with _lock:
                cloud = ensure_cloud()
            self._json(200, {"cloud": cloud["cloud"], "values": cloud.get("values", [])})
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "service": "RTM Cloud", "cloud": CLOUD_NAME})
            return
        if path in ("/api/export.xlsx", "/download/excel", "/api/export/excel"):
            self._send_export("xlsx")
            return
        if path in ("/api/export.csv", "/download/csv", "/api/export/csv"):
            self._send_export("csv")
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "invalid_json"})
            return

        if path == "/api/cloud/create":
            with _lock:
                cloud = ensure_cloud()
            self._json(200, {"ok": True, "created": True, "cloud": cloud["cloud"], "meta": cloud})
            return

        if path == "/api/upload":
            value = payload.get("value")
            if value is None or str(value).strip() == "":
                self._json(400, {"ok": False, "error": "missing_value"})
                return
            device = str(payload.get("device") or "industrial-numpad")
            result = upload_value(str(value).strip(), device)
            self._json(200, result)
            return

        self._json(404, {"ok": False, "error": "not_found"})


def main() -> None:
    cloud = ensure_cloud()
    ips = local_ips()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 56)
    print(f" RTM Cloud ready: {cloud['cloud']}")
    print(f" Status: {cloud.get('status', 'active')}")
    print(f" Entries: {len(cloud.get('values', []))}")
    print("-" * 56)
    print(" Dashboard:")
    for ip in ips:
        print(f"   http://{ip}:{PORT}/")
    print(" Keypad simulator (use this — NOT the local .html file):")
    for ip in ips[:2]:
        print(f"   http://{ip}:{PORT}/sim")
    print(" Excel download:")
    print(f"   http://127.0.0.1:{PORT}/api/export.xlsx")
    print(" ESP32 upload URL (set this in config.h):")
    lan = next((ip for ip in ips if not ip.startswith("127.")), "127.0.0.1")
    print(f'   #define RTM_CLOUD_HOST "{lan}"')
    print(f"   #define RTM_CLOUD_PORT {PORT}")
    print("=" * 56)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[RTM Cloud] Stopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
