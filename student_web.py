#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import html
import http.cookies
import os
import secrets
import socketserver
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.dat")
STUDENTS_FILE = os.path.join(BASE_DIR, "students.dat")

USERNAME_LEN = 32
PASSWORD_HASH_LEN = 65
USER_RECORD_SIZE = USERNAME_LEN + PASSWORD_HASH_LEN - 1

SESSION_COOKIE = "student_session"
SESSION_TTL_SECONDS = 8 * 60 * 60

HOST = "127.0.0.1"
PORT = 8000

sessions: dict[str, dict[str, float | str]] = {}
session_lock = threading.Lock()
data_lock = threading.Lock()


def normalize_value(value: str) -> str:
    return "".join(ch.lower() for ch in value if not ch.isspace())


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def legacy_hash_hex(value: str) -> str:
    digest = 0x811C9DC5
    for byte in value.encode("utf-8"):
        digest ^= byte
        digest = (digest * 0x01000193) & 0xFFFFFFFF

    return (
        f"{digest:08x}"
        f"{digest >> 4:08x}"
        f"{digest >> 8:08x}"
        f"{digest >> 12:08x}"
        f"{digest >> 16:08x}"
        f"{digest >> 20:08x}"
        f"{digest >> 24:08x}"
        f"{digest >> 28:08x}"
    )


def ensure_default_admin() -> None:
    if os.path.exists(USERS_FILE) and os.path.getsize(USERS_FILE) >= USER_RECORD_SIZE:
        return

    save_users([{"username": "admin", "password_hash": sha256_hex("admin123")}])


def load_users() -> list[dict[str, str]]:
    users: list[dict[str, str]] = []

    ensure_default_admin()
    with open(USERS_FILE, "rb") as fp:
        while True:
            chunk = fp.read(USER_RECORD_SIZE)
            if len(chunk) != USER_RECORD_SIZE:
                break

            raw_username = chunk[:USERNAME_LEN]
            raw_hash = chunk[USERNAME_LEN:]

            username = raw_username.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            password_hash = raw_hash.decode("ascii", errors="ignore").rstrip("\x00")
            if username:
                users.append({"username": username, "password_hash": password_hash})

    if not users:
        users = [{"username": "admin", "password_hash": sha256_hex("admin123")}]
        save_users(users)

    return users


def save_users(users: list[dict[str, str]]) -> None:
    with open(USERS_FILE, "wb") as fp:
        for user in users:
            username_bytes = user["username"].encode("utf-8", errors="ignore")[: USERNAME_LEN - 1]
            username_chunk = username_bytes + b"\x00" * (USERNAME_LEN - len(username_bytes))
            hash_bytes = user["password_hash"].encode("ascii", errors="ignore")[: PASSWORD_HASH_LEN - 1]
            hash_chunk = hash_bytes + b"\x00" * ((PASSWORD_HASH_LEN - 1) - len(hash_bytes))
            fp.write(username_chunk)
            fp.write(hash_chunk)


def authenticate(username: str, password: str) -> str | None:
    normalized_username = normalize_value(username)
    new_hash = sha256_hex(password)
    old_hash = legacy_hash_hex(password)

    with data_lock:
        users = load_users()
        upgraded = False

        for user in users:
            if normalize_value(user["username"]) != normalized_username:
                continue

            if user["password_hash"] == new_hash:
                return user["username"]
            if user["password_hash"] == old_hash:
                user["password_hash"] = new_hash
                upgraded = True
                matched_username = user["username"]
                if upgraded:
                    save_users(users)
                return matched_username
            return None

    return None


def load_students() -> list[dict[str, str]]:
    if not os.path.exists(STUDENTS_FILE):
        return []

    with open(STUDENTS_FILE, "r", encoding="utf-8", errors="ignore") as fp:
        lines = [line.rstrip("\n") for line in fp]

    students: list[dict[str, str]] = []
    for index in range(0, len(lines), 3):
        chunk = lines[index:index + 3]
        if len(chunk) < 3:
            break
        students.append(
            {
                "student_id": chunk[0],
                "full_name": chunk[1],
                "class_name": chunk[2],
            }
        )
    return students


def save_students(students: list[dict[str, str]]) -> None:
    with open(STUDENTS_FILE, "w", encoding="utf-8") as fp:
        for student in students:
            fp.write(f"{student['student_id']}\n")
            fp.write(f"{student['full_name']}\n")
            fp.write(f"{student['class_name']}\n")


def create_session(username: str) -> str:
    token = secrets.token_hex(24)
    expires_at = time.time() + SESSION_TTL_SECONDS

    with session_lock:
        sessions[token] = {"username": username, "expires_at": expires_at}

    return token


def lookup_session(token: str | None) -> str | None:
    if not token:
        return None

    with session_lock:
        session = sessions.get(token)
        if session is None:
            return None
        if float(session["expires_at"]) < time.time():
            sessions.pop(token, None)
            return None
        session["expires_at"] = time.time() + SESSION_TTL_SECONDS
        return str(session["username"])


def destroy_session(token: str | None) -> None:
    if not token:
        return
    with session_lock:
        sessions.pop(token, None)


def page_template(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f5efe6;
      --bg-soft: #fffaf2;
      --panel: rgba(255, 250, 242, 0.88);
      --panel-strong: #fffaf2;
      --text: #1e1d1a;
      --muted: #666052;
      --accent: #14532d;
      --accent-2: #c2410c;
      --line: rgba(20, 83, 45, 0.12);
      --shadow: 0 20px 50px rgba(72, 49, 26, 0.12);
      --radius: 24px;
      --radius-sm: 16px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(194, 65, 12, 0.16), transparent 30%),
        radial-gradient(circle at top right, rgba(20, 83, 45, 0.12), transparent 28%),
        linear-gradient(145deg, #f1e6d5 0%, #fdf9f2 40%, #efe7d7 100%);
      display: flex;
      align-items: stretch;
      justify-content: center;
      padding: 32px 20px;
    }}
    .shell {{
      width: min(1120px, 100%);
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.5);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
      overflow: hidden;
    }}
    .hero {{
      padding: 28px 32px 18px;
      border-bottom: 1px solid var(--line);
      background:
        linear-gradient(120deg, rgba(20, 83, 45, 0.95), rgba(22, 101, 52, 0.82)),
        linear-gradient(45deg, rgba(255,255,255,0.06), transparent);
      color: #f8f5ef;
    }}
    .eyebrow {{
      margin: 0 0 8px;
      letter-spacing: 0.18em;
      font-size: 12px;
      text-transform: uppercase;
      opacity: 0.75;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1.05;
    }}
    .subtitle {{
      margin: 10px 0 0;
      max-width: 760px;
      color: rgba(248, 245, 239, 0.84);
      font-size: 15px;
    }}
    .content {{
      padding: 28px 32px 32px;
    }}
    .grid {{
      display: grid;
      gap: 20px;
    }}
    .grid.two {{
      grid-template-columns: 1.2fr 0.8fr;
    }}
    .card {{
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid rgba(20, 83, 45, 0.1);
      border-radius: var(--radius-sm);
      padding: 22px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
    }}
    .card h2 {{
      margin: 0 0 8px;
      font-size: 20px;
    }}
    .card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    form {{
      display: grid;
      gap: 14px;
    }}
    label {{
      display: grid;
      gap: 7px;
      font-size: 14px;
      color: var(--muted);
    }}
    input {{
      width: 100%;
      border: 1px solid rgba(30, 29, 26, 0.12);
      border-radius: 14px;
      padding: 13px 14px;
      font-size: 15px;
      color: var(--text);
      background: rgba(255, 255, 255, 0.92);
      outline: none;
      transition: border-color 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease;
    }}
    input:focus {{
      border-color: rgba(20, 83, 45, 0.5);
      box-shadow: 0 0 0 4px rgba(20, 83, 45, 0.08);
      transform: translateY(-1px);
    }}
    .actions {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}
    button, .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
      transition: transform 0.18s ease, opacity 0.18s ease, box-shadow 0.18s ease;
    }}
    button:hover, .button:hover {{
      transform: translateY(-1px);
      box-shadow: 0 10px 24px rgba(20, 83, 45, 0.18);
    }}
    .primary {{
      color: #fffaf2;
      background: linear-gradient(135deg, #166534, #14532d);
    }}
    .secondary {{
      color: #7c2d12;
      background: rgba(194, 65, 12, 0.12);
    }}
    .flash {{
      padding: 14px 16px;
      border-radius: 16px;
      margin-bottom: 18px;
      font-size: 14px;
    }}
    .flash.error {{
      background: rgba(220, 38, 38, 0.1);
      color: #991b1b;
      border: 1px solid rgba(220, 38, 38, 0.12);
    }}
    .flash.success {{
      background: rgba(22, 101, 52, 0.12);
      color: #14532d;
      border: 1px solid rgba(22, 101, 52, 0.12);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }}
    .stat {{
      border-radius: 18px;
      padding: 18px;
      background: linear-gradient(160deg, rgba(255,255,255,0.94), rgba(247, 241, 232, 0.9));
      border: 1px solid rgba(20, 83, 45, 0.08);
    }}
    .stat strong {{
      display: block;
      font-size: 28px;
      line-height: 1;
      margin-bottom: 8px;
      color: var(--accent);
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }}
    .search {{
      max-width: 320px;
      margin-left: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 18px;
    }}
    thead th {{
      text-align: left;
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      padding: 14px 12px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.58);
    }}
    tbody td {{
      padding: 14px 12px;
      border-bottom: 1px solid rgba(20, 83, 45, 0.08);
      font-size: 15px;
    }}
    tbody tr:hover {{
      background: rgba(20, 83, 45, 0.035);
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(20, 83, 45, 0.08);
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
    }}
    .muted {{
      color: var(--muted);
      font-size: 14px;
    }}
    @media (max-width: 860px) {{
      .grid.two {{
        grid-template-columns: 1fr;
      }}
      .stats {{
        grid-template-columns: 1fr;
      }}
      body {{
        padding: 18px 12px;
      }}
      .hero, .content {{
        padding-left: 18px;
        padding-right: 18px;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {content}
  </div>
</body>
</html>
"""


def login_page(message: str = "", is_error: bool = False) -> str:
    flash = ""
    if message:
        klass = "error" if is_error else "success"
        flash = f'<div class="flash {klass}">{html.escape(message)}</div>'

    content = f"""
    <section class="hero">
      <p class="eyebrow">Student Management</p>
      <h1>Dang nhap vao bang dieu khien sinh vien</h1>
      <p class="subtitle">Giao dien local chay tren trinh duyet, dung chung du lieu cua du an C va khong can mo terminal de thao tac menu.</p>
    </section>
    <div class="content">
      <div class="grid two">
        <div class="card">
          <h2>Chao mung</h2>
          <p>Dang nhap de xem danh sach sinh vien, them ban ghi moi va luu du lieu vao file <code>students.dat</code>.</p>
        </div>
        <div class="card">
          {flash}
          <form method="post" action="/login">
            <label>
              Username
              <input name="username" autocomplete="username" placeholder="admin" required>
            </label>
            <label>
              Password
              <input name="password" type="password" autocomplete="current-password" placeholder="admin123" required>
            </label>
            <div class="actions">
              <button class="primary" type="submit">Dang nhap</button>
              <span class="muted">Tai khoan mac dinh: <strong>admin / admin123</strong></span>
            </div>
          </form>
        </div>
      </div>
    </div>
    """
    return page_template("Dang nhap", content)


def dashboard_page(username: str, students: list[dict[str, str]], message: str = "") -> str:
    total_classes = len({student["class_name"] for student in students if student["class_name"]})
    newest_student = students[-1]["student_id"] if students else "chua co"
    flash = f'<div class="flash success">{html.escape(message)}</div>' if message else ""

    rows = []
    for index, student in enumerate(students, start=1):
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(student['student_id'])}</td>"
            f"<td>{html.escape(student['full_name'])}</td>"
            f"<td>{html.escape(student['class_name'])}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="4" class="muted">Chua co sinh vien nao.</td></tr>')

    content = f"""
    <section class="hero">
      <p class="eyebrow">Dashboard</p>
      <h1>Quan ly sinh vien tren giao dien web</h1>
      <p class="subtitle">Xin chao {html.escape(username)}. Du lieu van duoc doc va ghi truc tiep tu file cua du an goc.</p>
    </section>
    <div class="content">
      {flash}
      <div class="stats">
        <div class="stat"><strong>{len(students)}</strong> Tong sinh vien</div>
        <div class="stat"><strong>{total_classes}</strong> Lop khac nhau</div>
        <div class="stat"><strong>{html.escape(newest_student)}</strong> Ma SV gan nhat</div>
      </div>
      <div class="grid two">
        <div class="card">
          <div class="toolbar">
            <div>
              <h2>Danh sach sinh vien</h2>
              <p>Tim nhanh, xem du lieu hien co va theo doi file <code>students.dat</code>.</p>
            </div>
            <input class="search" id="searchBox" placeholder="Loc theo ma, ten, lop...">
          </div>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Ma SV</th>
                <th>Ho va ten</th>
                <th>Lop</th>
              </tr>
            </thead>
            <tbody id="studentRows">
              {''.join(rows)}
            </tbody>
          </table>
        </div>
        <div class="card">
          <div class="actions" style="justify-content: space-between; margin-bottom: 14px;">
            <span class="chip">Dang nhap voi {html.escape(username)}</span>
            <a class="button secondary" href="/logout">Dang xuat</a>
          </div>
          <h2>Them sinh vien moi</h2>
          <p>Form nay giu hanh vi luu du lieu tuong thich voi chuong trinh C: gia tri se duoc bo khoang trang va chuyen ve chu thuong.</p>
          <form method="post" action="/students">
            <label>
              Ma sinh vien
              <input name="student_id" placeholder="sv001" required>
            </label>
            <label>
              Ho va ten
              <input name="full_name" placeholder="nguyenvana" required>
            </label>
            <label>
              Lop
              <input name="class_name" placeholder="k66" required>
            </label>
            <button class="primary" type="submit">Luu sinh vien</button>
          </form>
        </div>
      </div>
    </div>
    <script>
      const searchBox = document.getElementById("searchBox");
      const rows = Array.from(document.querySelectorAll("#studentRows tr"));
      if (searchBox) {{
        searchBox.addEventListener("input", () => {{
          const query = searchBox.value.trim().toLowerCase();
          rows.forEach((row) => {{
            row.style.display = row.textContent.toLowerCase().includes(query) ? "" : "none";
          }});
        }});
      }}
    </script>
    """
    return page_template("Quan ly sinh vien", content)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


class StudentWebHandler(BaseHTTPRequestHandler):
    server_version = "StudentWeb/1.0"

    def do_GET(self) -> None:
        if self.path == "/":
            username = self.current_username()
            if username:
                self.render_dashboard(username)
            else:
                self.respond_html(login_page())
            return

        if self.path == "/logout":
            token = self.session_token()
            destroy_session(token)
            self.respond_redirect("/", expired_cookie=True)
            return

        self.respond_html(page_template("Not found", '<div class="content"><div class="flash error">Khong tim thay trang.</div></div>'), status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path == "/login":
            self.handle_login()
            return
        if self.path == "/students":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            self.handle_add_student(username)
            return
        self.respond_html(page_template("Not found", '<div class="content"><div class="flash error">Khong tim thay duong dan POST.</div></div>'), status=HTTPStatus.NOT_FOUND)

    def handle_login(self) -> None:
        form = self.read_form()
        username = form.get("username", "").strip()
        password = form.get("password", "")
        matched_username = authenticate(username, password)

        if matched_username is None:
            self.respond_html(login_page("Sai username hoac password.", is_error=True), status=HTTPStatus.UNAUTHORIZED)
            return

        token = create_session(matched_username)
        self.respond_redirect("/", cookie_token=token)

    def handle_add_student(self, username: str) -> None:
        form = self.read_form()
        student_id = normalize_value(form.get("student_id", ""))
        full_name = normalize_value(form.get("full_name", ""))
        class_name = normalize_value(form.get("class_name", ""))

        if not student_id or not full_name or not class_name:
            self.respond_html(
                dashboard_page(username, load_students(), "Can nhap day du ma SV, ho ten va lop."),
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        with data_lock:
            students = load_students()
            if len(students) >= 256:
                self.respond_html(
                    dashboard_page(username, students, "Danh sach da day, khong them duoc nua."),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            students.append(
                {
                    "student_id": student_id,
                    "full_name": full_name,
                    "class_name": class_name,
                }
            )
            save_students(students)

        self.respond_html(dashboard_page(username, load_students(), f"Da luu sinh vien {student_id}."))

    def render_dashboard(self, username: str) -> None:
        with data_lock:
            students = load_students()
        self.respond_html(dashboard_page(username, students))

    def read_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8", errors="ignore")
        parsed = urllib.parse.parse_qs(payload, keep_blank_values=True)
        return {key: values[0] if values else "" for key, values in parsed.items()}

    def respond_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body_bytes = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def respond_redirect(self, location: str, cookie_token: str | None = None, expired_cookie: bool = False) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        if cookie_token is not None:
            cookie = http.cookies.SimpleCookie()
            cookie[SESSION_COOKIE] = cookie_token
            cookie[SESSION_COOKIE]["httponly"] = True
            cookie[SESSION_COOKIE]["path"] = "/"
            self.send_header("Set-Cookie", cookie.output(header="").strip())
        elif expired_cookie:
            cookie = http.cookies.SimpleCookie()
            cookie[SESSION_COOKIE] = ""
            cookie[SESSION_COOKIE]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
            cookie[SESSION_COOKIE]["path"] = "/"
            self.send_header("Set-Cookie", cookie.output(header="").strip())
        self.end_headers()

    def session_token(self) -> str | None:
        raw_cookie = self.headers.get("Cookie")
        if not raw_cookie:
            return None
        cookie = http.cookies.SimpleCookie()
        cookie.load(raw_cookie)
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def current_username(self) -> str | None:
        return lookup_session(self.session_token())

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    ensure_default_admin()
    with ThreadingHTTPServer((HOST, PORT), StudentWebHandler) as httpd:
        print(f"Student web UI running at http://{HOST}:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
