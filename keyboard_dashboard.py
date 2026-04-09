#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = 8081
PROC_FILE = "/proc/kb_driver"
STATUS_SCRIPT = os.path.join(BASE_DIR, "keyboard_status.sh")
BIND_SCRIPT = os.path.join(BASE_DIR, "bind_kb_driver.sh")
UNBIND_SCRIPT = os.path.join(BASE_DIR, "unbind_kb_driver.sh")

HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bang Dieu Khien Driver Ban Phim USB</title>
  <style>
    :root {
      --bg: #f2ede2;
      --panel: rgba(255, 250, 243, 0.88);
      --ink: #1f2430;
      --muted: #6b7280;
      --accent: #0b6e4f;
      --accent-soft: #d8efe7;
      --warn: #b45309;
      --border: rgba(31, 36, 48, 0.12);
      --shadow: 0 18px 40px rgba(50, 50, 70, 0.12);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "DejaVu Sans", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(11, 110, 79, 0.15), transparent 32%),
        radial-gradient(circle at top right, rgba(212, 136, 65, 0.15), transparent 28%),
        linear-gradient(180deg, #f7f1e6 0%, var(--bg) 100%);
    }
    .shell {
      width: min(1180px, calc(100vw - 32px));
      margin: 28px auto;
      display: grid;
      gap: 18px;
    }
    .hero, .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }
    .hero {
      padding: 24px;
      display: grid;
      gap: 16px;
    }
    .hero h1 {
      margin: 0;
      font-size: clamp(1.8rem, 4vw, 3rem);
      line-height: 1;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      max-width: 760px;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    button {
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      font: inherit;
      cursor: pointer;
      background: #1f2430;
      color: #fff;
      transition: transform 120ms ease, opacity 120ms ease;
    }
    button.secondary {
      background: #fff;
      color: var(--ink);
      border: 1px solid var(--border);
    }
    button.warn { background: var(--warn); }
    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.6; cursor: wait; transform: none; }
    .grid {
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(12, minmax(0, 1fr));
    }
    .panel {
      padding: 18px;
    }
    .stats {
      grid-column: span 12;
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .stat {
      padding: 16px;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(240,247,243,0.92));
      border: 1px solid rgba(11, 110, 79, 0.12);
    }
    .stat strong {
      display: block;
      font-size: 1.8rem;
      margin-top: 6px;
    }
    .two-col { grid-column: span 6; }
    .full { grid-column: span 12; }
    h2 {
      margin: 0 0 12px;
      font-size: 1.1rem;
    }
    .note {
      color: var(--muted);
      font-size: 0.95rem;
      margin-bottom: 14px;
    }
    .status-line {
      padding: 10px 14px;
      border-radius: 14px;
      background: var(--accent-soft);
      color: #124134;
      min-height: 42px;
      display: flex;
      align-items: center;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }
    th, td {
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid rgba(31, 36, 48, 0.08);
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-weight: 600;
    }
    .mono {
      font-family: "Cascadia Mono", "Fira Code", monospace;
      font-size: 0.9rem;
    }
    .scroll {
      overflow: auto;
      max-height: 420px;
    }
    .device-card {
      padding: 14px;
      border-radius: 16px;
      border: 1px solid rgba(31, 36, 48, 0.08);
      background: rgba(255,255,255,0.72);
    }
    .device-list {
      display: grid;
      gap: 12px;
    }
    @media (max-width: 920px) {
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .two-col { grid-column: span 12; }
    }
    @media (max-width: 640px) {
      .shell { width: min(100vw - 20px, 1180px); margin: 10px auto 18px; }
      .stats { grid-template-columns: 1fr; }
      .toolbar { flex-direction: column; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <h1>Bang Dieu Khien Driver Ban Phim USB</h1>
        <p>Giao dien local cho bai 2: theo doi driver, xem su kien phim theo thoi gian thuc, thong ke va dieu khien bind/unbind.</p>
      </div>
      <div class="toolbar">
        <button onclick="runAction('bind_all')">Gan Tat Ca</button>
        <button class="secondary" onclick="runAction('unbind_all')">Go Gan Tat Ca</button>
        <button class="secondary" onclick="runAction('logging_on')">Bat Ghi Log</button>
        <button class="secondary" onclick="runAction('logging_off')">Tat Ghi Log</button>
        <button class="secondary" onclick="runAction('clear_history')">Xoa Lich Su</button>
        <button class="warn" onclick="runAction('reset_stats')">Dat Lai Thong Ke</button>
      </div>
      <div class="status-line" id="message">Dang cho lan cap nhat dau tien...</div>
    </section>

    <section class="grid">
      <div class="panel stats">
        <div class="stat"><span>Trang Thai Module</span><strong id="moduleLoaded">-</strong></div>
        <div class="stat"><span>Thiet Bi Dang Hoat Dong</span><strong id="activeDevices">0</strong></div>
        <div class="stat"><span>So Lan Nhan Phim</span><strong id="pressCount">0</strong></div>
        <div class="stat"><span>So Lan Nha Phim</span><strong id="releaseCount">0</strong></div>
      </div>

      <section class="panel two-col">
        <h2>Trang Thai Driver</h2>
        <div class="note">Doc tu <span class="mono">/proc/kb_driver</span>. Luu y: thao tac bind/unbind va ghi vao proc de dieu khien co the can quyen root.</div>
        <table>
          <tbody>
            <tr><th>Ghi log</th><td id="loggingEnabled">-</td></tr>
            <tr><th>So muc lich su</th><td id="historyEntries">0</td></tr>
            <tr><th>Tep proc</th><td class="mono">/proc/kb_driver</td></tr>
            <tr><th>Dia chi dashboard</th><td class="mono">http://127.0.0.1:8081</td></tr>
          </tbody>
        </table>
      </section>

      <section class="panel two-col">
        <h2>Giao Dien Ban Phim USB</h2>
        <div class="note">Doc tu script trang thai de xac dinh thiet bi va driver hien tai.</div>
        <div class="device-list" id="devices"></div>
      </section>

      <section class="panel full">
        <h2>Su Kien Gan Day</h2>
        <div class="scroll">
          <table>
            <thead>
              <tr>
                <th>STT</th>
                <th>Thoi Gian</th>
                <th>Giao Dien</th>
                <th>Hanh Dong</th>
                <th>Phim</th>
                <th>Ma Usage</th>
              </tr>
            </thead>
            <tbody id="historyRows"></tbody>
          </table>
        </div>
      </section>

      <section class="panel full">
        <h2>Thong Ke Phim</h2>
        <div class="scroll">
          <table>
            <thead>
              <tr>
                <th>Ma Usage</th>
                <th>Ten Phim</th>
                <th>So Lan Nhan</th>
                <th>So Lan Nha</th>
              </tr>
            </thead>
            <tbody id="statsRows"></tbody>
          </table>
        </div>
      </section>
    </section>
  </main>

  <script>
    let busy = false;

    async function fetchDashboard() {
      const response = await fetch('/api/status');
      if (!response.ok) {
        throw new Error('status request failed');
      }
      return response.json();
    }

    function setMessage(text, isError = false) {
      const message = document.getElementById('message');
      message.textContent = text;
      message.style.background = isError ? 'rgba(180, 83, 9, 0.14)' : 'var(--accent-soft)';
      message.style.color = isError ? '#7c2d12' : '#124134';
    }

    function translateAction(action) {
      if (action === 'pressed') return 'Nhan';
      if (action === 'released') return 'Nha';
      return action || '-';
    }

    function renderDevices(devices) {
      const container = document.getElementById('devices');
      container.innerHTML = '';
      if (!devices.length) {
        container.innerHTML = '<div class="device-card">Khong tim thay USB boot keyboard interface nao.</div>';
        return;
      }

      for (const device of devices) {
        const card = document.createElement('div');
        card.className = 'device-card';
        card.innerHTML = `
          <div><strong>${device.interface || '-'}</strong></div>
          <div>Driver: <span class="mono">${device.driver || '-'}</span></div>
          <div>VID:PID: <span class="mono">${device.vendor_product || '-'}</span></div>
          <div>Thiet bi: ${device.device || '-'}</div>
        `;
        container.appendChild(card);
      }
    }

    function renderHistory(history) {
      const body = document.getElementById('historyRows');
      body.innerHTML = '';
      if (!history.length) {
        body.innerHTML = '<tr><td colspan="6">Chua co su kien nao duoc ghi.</td></tr>';
        return;
      }
      for (const event of history.slice().reverse()) {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td class="mono">${event.seq}</td>
          <td class="mono">${event.timestamp}</td>
          <td class="mono">${event.interface}</td>
          <td>${translateAction(event.action)}</td>
          <td>${event.key}</td>
          <td class="mono">${event.usage}</td>
        `;
        body.appendChild(row);
      }
    }

    function renderStats(stats) {
      const body = document.getElementById('statsRows');
      body.innerHTML = '';
      if (!stats.length) {
        body.innerHTML = '<tr><td colspan="4">Chua co thong ke phim.</td></tr>';
        return;
      }
      for (const stat of stats) {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td class="mono">${stat.usage}</td>
          <td>${stat.name}</td>
          <td>${stat.pressed}</td>
          <td>${stat.released}</td>
        `;
        body.appendChild(row);
      }
    }

    async function refresh() {
      try {
        const data = await fetchDashboard();
        document.getElementById('moduleLoaded').textContent = data.module_loaded ? 'Da nap' : 'Chua nap';
        document.getElementById('activeDevices').textContent = data.proc.active_devices ?? 0;
        document.getElementById('pressCount').textContent = data.proc.total_press_events ?? 0;
        document.getElementById('releaseCount').textContent = data.proc.total_release_events ?? 0;
        document.getElementById('loggingEnabled').textContent = data.proc.logging_enabled ? 'Bat' : 'Tat';
        document.getElementById('historyEntries').textContent = data.proc.history_entries ?? 0;
        renderDevices(data.devices);
        renderHistory(data.proc.history || []);
        renderStats(data.proc.key_stats || []);
        setMessage(data.message || 'Dashboard da duoc cap nhat');
      } catch (error) {
        setMessage('Khong doc duoc dashboard data. Kiem tra module va quyen truy cap.', true);
      }
    }

    async function runAction(action) {
      if (busy) {
        return;
      }
      busy = true;
      for (const button of document.querySelectorAll('button')) {
        button.disabled = true;
      }
      try {
        const response = await fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({ action }),
        });
        const result = await response.json();
        setMessage(result.message || 'Thao tac da hoan tat', !result.ok);
        await refresh();
      } catch (error) {
        setMessage('Thao tac that bai', true);
      } finally {
        busy = false;
        for (const button of document.querySelectorAll('button')) {
          button.disabled = false;
        }
      }
    }

    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>
"""


def read_proc_state() -> dict:
    result = {
        "logging_enabled": False,
        "active_devices": 0,
        "total_press_events": 0,
        "total_release_events": 0,
        "history_entries": 0,
        "devices": [],
        "history": [],
        "key_stats": [],
    }
    if not os.path.exists(PROC_FILE):
        return result

    with open(PROC_FILE, "r", encoding="utf-8", errors="ignore") as handle:
        lines = [line.rstrip("\n") for line in handle]

    section = ""
    for line in lines:
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue

        if section == "kb_driver" and "=" in line:
            key, value = line.split("=", 1)
            if key in {"active_devices", "history_entries"}:
                result[key] = int(value)
            elif key in {"total_press_events", "total_release_events"}:
                result[key] = int(value)
            elif key == "logging_enabled":
                result[key] = value == "1"
        elif section == "devices":
            iface, vendor, product = (line.split("|") + ["", "", ""])[:3]
            if iface:
                result["devices"].append({
                    "interface": iface,
                    "vendor_id": vendor,
                    "product_id": product,
                })
        elif section == "history":
            parts = (line.split("|") + ["", "", "", "", "", ""])[:6]
            if parts[0]:
                result["history"].append({
                    "seq": int(parts[0]),
                    "timestamp": int(parts[1]),
                    "interface": parts[2],
                    "action": parts[3],
                    "key": parts[4],
                    "usage": parts[5],
                })
        elif section == "key_stats":
            usage, name, pressed, released = (line.split("|") + ["", "", "0", "0"])[:4]
            if usage:
                result["key_stats"].append({
                    "usage": usage,
                    "name": name,
                    "pressed": int(pressed),
                    "released": int(released),
                })

    result["key_stats"].sort(key=lambda item: (-item["pressed"], item["usage"]))
    return result


def parse_status_output(raw_output: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line in raw_output.splitlines():
        line = line.strip()
        if not line:
            if current:
                devices.append(current)
                current = {}
            continue
        if line.startswith("Interface :"):
            current["interface"] = line.split(":", 1)[1].strip()
        elif line.startswith("USB device :"):
            current["usb_device"] = line.split(":", 1)[1].strip()
        elif line.startswith("Vendor:Prod:"):
            current["vendor_product"] = line.split(":", 1)[1].strip()
        elif line.startswith("Device    :"):
            current["device"] = line.split(":", 1)[1].strip()
        elif line.startswith("Driver    :"):
            current["driver"] = line.split(":", 1)[1].strip()

    if current:
        devices.append(current)

    normalized_devices = []
    for device in devices:
        normalized_devices.append({
            "interface": device.get("interface", ""),
            "device": device.get("device", ""),
            "vendor_product": device.get("vendor_product", ""),
            "driver": device.get("driver", ""),
        })
    return normalized_devices


def run_command(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=BASE_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return False, str(exc)

    output = (completed.stdout or "") + (completed.stderr or "")
    message = output.strip() or f"exit code {completed.returncode}"
    return completed.returncode == 0, message


def write_proc_command(command: str) -> tuple[bool, str]:
    try:
        with open(PROC_FILE, "w", encoding="utf-8") as handle:
            handle.write(command)
    except OSError as exc:
        return False, str(exc)
    return True, f"Sent '{command}' to {PROC_FILE}"


def collect_dashboard_data() -> dict:
    proc_state = read_proc_state()
    status_ok, status_text = run_command([STATUS_SCRIPT])
    module_loaded = os.path.isdir("/sys/bus/usb/drivers/kb_driver")
    message = "Dashboard da duoc cap nhat"
    if not module_loaded:
        message = "kb_driver chua duoc nap. Can insmod va bind thiet bi de xem su kien."
    elif not status_ok:
        message = status_text

    return {
        "message": message,
        "module_loaded": module_loaded,
        "devices": parse_status_output(status_text) if status_ok else [],
        "proc": proc_state,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if self.path == "/api/status":
            payload = json.dumps(collect_dashboard_data()).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/action":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8", errors="ignore")
        params = urllib.parse.parse_qs(raw_body)
        action = params.get("action", [""])[0]

        actions = {
            "bind_all": lambda: run_command([BIND_SCRIPT]),
            "unbind_all": lambda: run_command([UNBIND_SCRIPT]),
            "clear_history": lambda: write_proc_command("clear_history"),
            "reset_stats": lambda: write_proc_command("reset_stats"),
            "logging_on": lambda: write_proc_command("logging=1"),
            "logging_off": lambda: write_proc_command("logging=0"),
        }

        if action not in actions:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "message": f"Unknown action: {action}"}).encode("utf-8"))
            return

        ok, message = actions[action]()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": ok, "message": message}).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"USB keyboard dashboard running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
