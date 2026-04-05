#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import html
import http.cookies
import json
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
GPA_TRIALS_FILE = os.path.join(BASE_DIR, "gpa_trials.json")

USERNAME_LEN = 32
PASSWORD_HASH_LEN = 65
USER_RECORD_SIZE = USERNAME_LEN + PASSWORD_HASH_LEN - 1

SESSION_COOKIE = "student_session"
SESSION_TTL_SECONDS = 8 * 60 * 60

HOST = "127.0.0.1"
PORT = 8000
STUDENT_FILE_HEADER = "STUDENT_V2"

sessions: dict[str, dict[str, float | str]] = {}
session_lock = threading.Lock()
data_lock = threading.Lock()


def collapse_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_value(value: str) -> str:
    return "".join(ch.lower() for ch in value if not ch.isspace())


def is_admin_username(username: str) -> bool:
    return normalize_value(username) == "admin"


def normalize_student_code(value: str) -> str:
    return "".join(collapse_spaces(value).split()).upper()


def normalize_full_name(value: str) -> str:
    collapsed = collapse_spaces(value)
    if not collapsed:
        return ""
    return " ".join(part[:1].upper() + part[1:].lower() for part in collapsed.split(" "))


def normalize_free_text(value: str) -> str:
    return collapse_spaces(value)


def normalize_phone(value: str) -> str:
    return collapse_spaces(value)


def parse_gpa(value: str) -> float | None:
    normalized = collapse_spaces(value).replace(",", ".")
    if not normalized:
        return None
    parsed = float(normalized)
    if parsed < 0 or parsed > 10:
        raise ValueError("GPA must be between 0 and 10")
    return parsed


def normalize_gpa(value: str) -> str:
    parsed = parse_gpa(value)
    return "" if parsed is None else f"{parsed:.2f}"


def parse_course_score(value: str) -> float:
    normalized = collapse_spaces(value).replace(",", ".")
    parsed = float(normalized)
    if parsed < 0 or parsed > 10:
        raise ValueError("Score must be between 0 and 10")
    return parsed


def normalize_course_score(value: str) -> str:
    return f"{parse_course_score(value):.2f}"


def parse_course_credits(value: str) -> int:
    normalized = collapse_spaces(value)
    parsed = int(normalized)
    if parsed <= 0:
        raise ValueError("Credits must be positive")
    return parsed


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


def find_user(users: list[dict[str, str]], username: str) -> dict[str, str] | None:
    normalized_username = normalize_student_code(username) if not is_admin_username(username) else "admin"
    for user in users:
        candidate = normalize_student_code(user["username"]) if not is_admin_username(user["username"]) else "admin"
        if candidate == normalized_username:
            return user
    return None


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
    if not lines:
        return students

    if lines[0] == STUDENT_FILE_HEADER:
        for index in range(1, len(lines), 7):
            chunk = lines[index:index + 7]
            if len(chunk) < 7:
                break
            students.append(
                {
                    "student_id": normalize_student_code(chunk[0]),
                    "full_name": normalize_full_name(chunk[1]),
                    "class_name": normalize_student_code(chunk[2]),
                    "address": normalize_free_text(chunk[3]),
                    "phone": normalize_phone(chunk[4]),
                    "major": normalize_free_text(chunk[5]),
                    "gpa": chunk[6],
                }
            )
            try:
                students[-1]["gpa"] = normalize_gpa(chunk[6]) if collapse_spaces(chunk[6]) else ""
            except ValueError:
                students[-1]["gpa"] = ""
        return students

    for index in range(0, len(lines), 3):
        chunk = lines[index:index + 3]
        if len(chunk) < 3:
            break
        students.append(
            {
                "student_id": normalize_student_code(chunk[0]),
                "full_name": normalize_full_name(chunk[1]),
                "class_name": normalize_student_code(chunk[2]),
                "address": "",
                "phone": "",
                "major": "",
                "gpa": "",
            }
        )
    return students


def save_students(students: list[dict[str, str]]) -> None:
    with open(STUDENTS_FILE, "w", encoding="utf-8") as fp:
        fp.write(f"{STUDENT_FILE_HEADER}\n")
        for student in students:
            fp.write(f"{student['student_id']}\n")
            fp.write(f"{student['full_name']}\n")
            fp.write(f"{student['class_name']}\n")
            fp.write(f"{student.get('address', '')}\n")
            fp.write(f"{student.get('phone', '')}\n")
            fp.write(f"{student.get('major', '')}\n")
            fp.write(f"{student.get('gpa', '')}\n")


def load_gpa_trials() -> dict[str, list[dict[str, str]]]:
    if not os.path.exists(GPA_TRIALS_FILE):
        return {}
    try:
        with open(GPA_TRIALS_FILE, "r", encoding="utf-8") as fp:
            raw = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(raw, dict):
        return {}

    trials: dict[str, list[dict[str, str]]] = {}
    for student_id, courses in raw.items():
        normalized_student_id = normalize_student_code(student_id)
        if not isinstance(courses, list):
            continue
        normalized_courses: list[dict[str, str]] = []
        for course in courses:
            if not isinstance(course, dict):
                continue
            name = normalize_free_text(str(course.get("course_name", "")))
            credits_raw = str(course.get("credits", ""))
            score_raw = str(course.get("score", ""))
            if not name:
                continue
            try:
                normalized_courses.append(
                    {
                        "course_name": name,
                        "credits": str(parse_course_credits(credits_raw)),
                        "score": normalize_course_score(score_raw),
                    }
                )
            except (ValueError, TypeError):
                continue
        trials[normalized_student_id] = normalized_courses
    return trials


def save_gpa_trials(trials: dict[str, list[dict[str, str]]]) -> None:
    serializable: dict[str, list[dict[str, str]]] = {}
    for student_id, courses in trials.items():
        serializable[normalize_student_code(student_id)] = [
            {
                "course_name": normalize_free_text(course["course_name"]),
                "credits": str(parse_course_credits(course["credits"])),
                "score": normalize_course_score(course["score"]),
            }
            for course in courses
        ]
    with open(GPA_TRIALS_FILE, "w", encoding="utf-8") as fp:
        json.dump(serializable, fp, ensure_ascii=True, indent=2)


def rename_gpa_trial_owner(old_student_id: str, new_student_id: str) -> None:
    old_key = normalize_student_code(old_student_id)
    new_key = normalize_student_code(new_student_id)
    if old_key == new_key:
        return

    trials = load_gpa_trials()
    if old_key not in trials:
        return
    trials[new_key] = trials.pop(old_key)
    save_gpa_trials(trials)


def calculate_trial_gpa(courses: list[dict[str, str]]) -> str:
    total_points = 0.0
    total_credits = 0
    for course in courses:
        credits = parse_course_credits(course["credits"])
        score = parse_course_score(course["score"])
        total_points += credits * score
        total_credits += credits
    if total_credits == 0:
        return "0.00"
    return f"{(total_points / total_credits):.2f}"


def find_student_by_username(username: str, students: list[dict[str, str]]) -> dict[str, str] | None:
    normalized_username = normalize_value(username)
    for student in students:
        if normalize_value(student["student_id"]) == normalized_username:
            return student
    return None


def verify_user_password(user: dict[str, str], password: str) -> bool:
    current_hash = sha256_hex(password)
    legacy_hash = legacy_hash_hex(password)
    return user["password_hash"] in {current_hash, legacy_hash}


def change_user_password(username: str, current_password: str, new_password: str) -> tuple[bool, str]:
    users = load_users()
    user = find_user(users, username)

    if user is None:
        return False, "Khong tim thay tai khoan can doi mat khau."
    if not verify_user_password(user, current_password):
        return False, "Mat khau cu khong dung."

    user["password_hash"] = sha256_hex(new_password)
    save_users(users)
    return True, ""


def create_student_account(student_id: str, password: str) -> tuple[bool, str]:
    users = load_users()
    normalized_student_id = normalize_student_code(student_id)
    if find_user(users, normalized_student_id) is not None:
        return False, "Ma sinh vien da ton tai trong users.dat."

    users.append({"username": normalized_student_id, "password_hash": sha256_hex(password)})
    save_users(users)
    return True, ""


def update_student_account(old_student_id: str, new_student_id: str) -> tuple[bool, str]:
    users = load_users()
    user = find_user(users, old_student_id)
    normalized_new_id = normalize_student_code(new_student_id)

    if user is None:
        return False, "Khong tim thay tai khoan sinh vien tuong ung."

    if normalize_student_code(old_student_id) != normalized_new_id and find_user(users, normalized_new_id) is not None:
        return False, "Ma sinh vien moi bi trung voi mot tai khoan khac."

    user["username"] = normalized_new_id
    save_users(users)
    return True, ""


def delete_student_account(student_id: str) -> None:
    users = load_users()
    normalized_student_id = normalize_student_code(student_id)
    filtered = [
        user for user in users
        if normalize_student_code(user["username"]) != normalized_student_id or is_admin_username(user["username"])
    ]
    save_users(filtered)


def public_student_rows(students: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "student_id": student["student_id"],
            "full_name": student["full_name"],
            "class_name": student["class_name"],
            "major": student.get("major", ""),
        }
        for student in students
    ]


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


def update_session_username(token: str | None, username: str) -> None:
    if not token:
        return
    with session_lock:
        session = sessions.get(token)
        if session is not None:
            session["username"] = username


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


def flash_html(message: str = "", is_error: bool = False) -> str:
    if not message:
        return ""
    klass = "error" if is_error else "success"
    return f'<div class="flash {klass}">{html.escape(message)}</div>'


def render_student_form(student: dict[str, str] | None = None, include_gpa: bool = True) -> str:
    student = student or {
        "student_id": "",
        "full_name": "",
        "class_name": "",
        "address": "",
        "phone": "",
        "major": "",
        "gpa": "",
    }
    gpa_field = ""
    if include_gpa:
        gpa_field = f"""
        <label>
          GPA
          <input name="gpa" placeholder="0.00 - 10.00" value="{html.escape(student.get('gpa', ''))}">
        </label>
        """

    return f"""
    <label>
      Ma sinh vien
      <input name="student_id" placeholder="CT070001" value="{html.escape(student.get('student_id', ''))}" required>
    </label>
    <label>
      Ho va ten
      <input name="full_name" placeholder="Nguyen Van A" value="{html.escape(student.get('full_name', ''))}" required>
    </label>
    <label>
      Lop
      <input name="class_name" placeholder="CT7A" value="{html.escape(student.get('class_name', ''))}" required>
    </label>
    <label>
      Dia chi
      <input name="address" placeholder="So nha, duong, quan/huyen..." value="{html.escape(student.get('address', ''))}">
    </label>
    <label>
      So dien thoai
      <input name="phone" placeholder="0901234567" value="{html.escape(student.get('phone', ''))}">
    </label>
    <label>
      Nganh hoc
      <input name="major" placeholder="Cong nghe thong tin" value="{html.escape(student.get('major', ''))}">
    </label>
    {gpa_field}
    """


def password_page(username: str, message: str = "", is_error: bool = False) -> str:
    content = f"""
    <section class="hero">
      <p class="eyebrow">Security</p>
      <h1>Doi mat khau</h1>
      <p class="subtitle">Tai khoan dang nhap: {html.escape(username)}</p>
    </section>
    <div class="content">
      <div class="grid two">
        <div class="card">
          <div class="actions" style="justify-content: space-between; margin-bottom: 14px;">
            <span class="chip">{html.escape(username)}</span>
            <a class="button secondary" href="/">Quay lai</a>
          </div>
          {flash_html(message, is_error)}
          <form method="post" action="/password">
            <label>
              Mat khau cu
              <input name="current_password" type="password" required>
            </label>
            <label>
              Mat khau moi
              <input name="new_password" type="password" required>
            </label>
            <label>
              Xac nhan mat khau moi
              <input name="confirm_password" type="password" required>
            </label>
            <div class="actions">
              <button class="primary" type="submit">Luu mat khau moi</button>
              <a class="button secondary" href="/logout">Dang xuat</a>
            </div>
          </form>
        </div>
      </div>
    </div>
    """
    return page_template("Doi mat khau", content)


def profile_edit_page(username: str, student: dict[str, str], message: str = "", is_error: bool = False) -> str:
    content = f"""
    <section class="hero">
      <p class="eyebrow">Profile</p>
      <h1>Cap nhat thong tin ca nhan</h1>
      <p class="subtitle">Sinh vien duoc sua ma SV, ho ten, lop, dia chi, so dien thoai va nganh hoc. GPA chi admin moi sua duoc.</p>
    </section>
    <div class="content">
      <div class="grid two">
        <div class="card">
          <div class="actions" style="justify-content: space-between; margin-bottom: 14px;">
            <span class="chip">{html.escape(username)}</span>
            <a class="button secondary" href="/">Quay lai</a>
          </div>
          {flash_html(message, is_error)}
          <form method="post" action="/profile">
            {render_student_form(student, include_gpa=False)}
            <div class="actions">
              <button class="primary" type="submit">Cap nhat ho so</button>
              <a class="button secondary" href="/password">Doi mat khau</a>
            </div>
          </form>
        </div>
        <div class="card">
          <h2>Thong tin hien tai</h2>
          <p><strong>GPA:</strong> {html.escape(student.get('gpa', ''))}</p>
          <p><strong>So dien thoai:</strong> {html.escape(student.get('phone', ''))}</p>
          <p><strong>Dia chi:</strong> {html.escape(student.get('address', ''))}</p>
        </div>
      </div>
    </div>
    """
    return page_template("Cap nhat ho so", content)


def admin_student_edit_page(username: str, student: dict[str, str], message: str = "", is_error: bool = False) -> str:
    content = f"""
    <section class="hero">
      <p class="eyebrow">Admin</p>
      <h1>Sua thong tin sinh vien</h1>
      <p class="subtitle">Admin co quyen sua day du thong tin, bao gom GPA.</p>
    </section>
    <div class="content">
      <div class="grid two">
        <div class="card">
          <div class="actions" style="justify-content: space-between; margin-bottom: 14px;">
            <span class="chip">{html.escape(username)}</span>
            <a class="button secondary" href="/">Quay lai</a>
          </div>
          {flash_html(message, is_error)}
          <form method="post" action="/students/update">
            <input type="hidden" name="old_student_id" value="{html.escape(student['student_id'])}">
            {render_student_form(student, include_gpa=True)}
            <div class="actions">
              <button class="primary" type="submit">Luu thay doi</button>
              <a class="button secondary" href="/students/delete?id={urllib.parse.quote(student['student_id'])}">Xoa sinh vien</a>
            </div>
          </form>
        </div>
      </div>
    </div>
    """
    return page_template("Sua sinh vien", content)


def gpa_trial_page(username: str, student: dict[str, str], courses: list[dict[str, str]], message: str = "", is_error: bool = False) -> str:
    rows = []
    for index, course in enumerate(courses, start=1):
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(course['course_name'])}</td>"
            f"<td>{html.escape(course['credits'])}</td>"
            f"<td>{html.escape(course['score'])}</td>"
            f'<td><a class="button secondary" href="/gpa-trial/delete?index={index - 1}">Xoa</a></td>'
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5" class="muted">Chua co mon hoc nao trong bang tinh thu GPA.</td></tr>')

    content = f"""
    <section class="hero">
      <p class="eyebrow">GPA Trial</p>
      <h1>Tinh GPA du kien</h1>
      <p class="subtitle">Sinh vien tu nhap mon hoc de tinh thu GPA. Du lieu nay duoc luu rieng va khong ghi de GPA chinh thuc.</p>
    </section>
    <div class="content">
      <div class="grid two">
        <div class="card">
          <div class="actions" style="justify-content: space-between; margin-bottom: 14px;">
            <span class="chip">{html.escape(student['student_id'])}</span>
            <div class="actions">
              <a class="button secondary" href="/">Quay lai</a>
              <a class="button secondary" href="/password">Doi mat khau</a>
            </div>
          </div>
          {flash_html(message, is_error)}
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Ten mon</th>
                <th>So tin</th>
                <th>Diem</th>
                <th>Hanh dong</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rows)}
            </tbody>
          </table>
          <div class="stats" style="margin-top: 18px;">
            <div class="stat"><strong>{html.escape(calculate_trial_gpa(courses))}</strong> GPA du kien</div>
          </div>
        </div>
        <div class="card">
          <h2>Nhap diem mon hoc</h2>
          <p>Them mon hoc de he thong tinh GPA theo tong(diem * so tin) / tong so tin.</p>
          <form method="post" action="/gpa-trial">
            <label>
              Mon hoc
              <input name="course_name" placeholder="Cau truc du lieu" required>
            </label>
            <label>
              Diem
              <input name="score" placeholder="0.00 - 10.00" required>
            </label>
            <label>
              So tin
              <input name="credits" placeholder="3" required>
            </label>
            <button class="primary" type="submit">Nhap diem mon hoc</button>
          </form>
        </div>
      </div>
    </div>
    """
    return page_template("Tinh GPA du kien", content)


def dashboard_page(username: str, students: list[dict[str, str]], message: str = "", is_error: bool = False) -> str:
    admin_mode = is_admin_username(username)
    total_classes = len({student["class_name"] for student in students if student["class_name"]})
    newest_student = students[-1]["student_id"] if students else "chua co"
    flash = flash_html(message, is_error)
    visible_students = students if admin_mode else public_student_rows(students)
    own_profile = None if admin_mode else find_student_by_username(username, students)

    rows = []
    for index, student in enumerate(visible_students, start=1):
        action_cell = ""
        extra_cells = ""
        if admin_mode:
            extra_cells = (
                f"<td>{html.escape(student.get('address', ''))}</td>"
                f"<td>{html.escape(student.get('phone', ''))}</td>"
                f"<td>{html.escape(student.get('major', ''))}</td>"
                f"<td>{html.escape(student.get('gpa', ''))}</td>"
            )
            action_cell = (
                '<td><div class="actions">'
                f'<a class="button secondary" href="/students/edit?id={urllib.parse.quote(student["student_id"])}">Sua</a>'
                f'<a class="button secondary" href="/students/delete?id={urllib.parse.quote(student["student_id"])}">Xoa</a>'
                '</div></td>'
            )
        else:
            extra_cells = f"<td>{html.escape(student.get('major', ''))}</td>"
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(student['student_id'])}</td>"
            f"<td>{html.escape(student['full_name'])}</td>"
            f"<td>{html.escape(student['class_name'])}</td>"
            f"{extra_cells}"
            f"{action_cell}"
            "</tr>"
        )
    if not rows:
        rows.append(f'<tr><td colspan="{"9" if admin_mode else "5"}" class="muted">Chua co sinh vien nao.</td></tr>')

    right_card = ""
    if admin_mode:
        right_card = f"""
        <div class="card">
          <div class="actions" style="justify-content: space-between; margin-bottom: 14px;">
            <span class="chip">Dang nhap voi {html.escape(username)}</span>
            <div class="actions">
              <a class="button secondary" href="/password">Doi mat khau</a>
              <a class="button secondary" href="/logout">Dang xuat</a>
            </div>
          </div>
          <h2>Them sinh vien moi</h2>
          <p>Admin tao sinh vien va tu dong tao tai khoan voi mat khau mac dinh la "1".</p>
          <form method="post" action="/students">
            {render_student_form(include_gpa=True)}
            <button class="primary" type="submit">Luu sinh vien</button>
          </form>
        </div>
        """
    else:
        if own_profile is None:
            profile_details = '<p class="muted">Khong tim thay ho so sinh vien cua tai khoan nay.</p>'
        else:
            profile_details = f"""
            <div class="stack">
              <p><strong>Ma SV:</strong> {html.escape(own_profile['student_id'])}</p>
              <p><strong>Ho va ten:</strong> {html.escape(own_profile['full_name'])}</p>
              <p><strong>Lop:</strong> {html.escape(own_profile['class_name'])}</p>
              <p><strong>Nganh hoc:</strong> {html.escape(own_profile.get('major', ''))}</p>
              <p><strong>GPA:</strong> {html.escape(own_profile.get('gpa', ''))}</p>
              <p><strong>So dien thoai:</strong> {html.escape(own_profile.get('phone', ''))}</p>
              <p><strong>Dia chi:</strong> {html.escape(own_profile.get('address', ''))}</p>
            </div>
            """
        right_card = f"""
        <div class="card">
          <div class="actions" style="justify-content: space-between; margin-bottom: 14px;">
            <span class="chip">Dang nhap voi {html.escape(username)}</span>
            <div class="actions">
              <a class="button secondary" href="/profile">Sua ho so</a>
              <a class="button secondary" href="/gpa-trial">Tinh GPA du kien</a>
              <a class="button secondary" href="/password">Doi mat khau</a>
              <a class="button secondary" href="/logout">Dang xuat</a>
            </div>
          </div>
          <h2>Thong tin ca nhan</h2>
          <p>Sinh vien chi xem duoc thong tin cong khai cua ban khac. So dien thoai, dia chi va GPA chi hien thi trong ho so cua chinh ban.</p>
          {profile_details}
        </div>
        """

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
            <input class="search" id="searchBox" placeholder="Loc theo ma, ten, lop, nganh...">
          </div>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Ma SV</th>
                <th>Ho va ten</th>
                <th>Lop</th>
                {"<th>Dia chi</th><th>So dien thoai</th><th>Nganh hoc</th><th>GPA</th><th>Hanh dong</th>" if admin_mode else "<th>Nganh hoc</th>"}
              </tr>
            </thead>
            <tbody id="studentRows">
              {''.join(rows)}
            </tbody>
          </table>
        </div>
        {right_card}
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
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

        if path == "/":
            username = self.current_username()
            if username:
                self.render_dashboard(username)
            else:
                self.respond_html(login_page())
            return

        if path == "/logout":
            token = self.session_token()
            destroy_session(token)
            self.respond_redirect("/", expired_cookie=True)
            return

        if path == "/password":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            self.respond_html(password_page(username))
            return

        if path == "/profile":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            if is_admin_username(username):
                self.respond_redirect("/")
                return
            with data_lock:
                student = find_student_by_username(username, load_students())
            if student is None:
                self.respond_html(dashboard_page(username, load_students(), "Khong tim thay ho so sinh vien.", is_error=True), status=HTTPStatus.NOT_FOUND)
                return
            self.respond_html(profile_edit_page(username, student))
            return

        if path == "/gpa-trial":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            if is_admin_username(username):
                self.respond_redirect("/")
                return
            with data_lock:
                students = load_students()
                student = find_student_by_username(username, students)
                courses = load_gpa_trials().get(normalize_student_code(username), [])
            if student is None:
                self.respond_html(dashboard_page(username, students, "Khong tim thay ho so sinh vien.", is_error=True), status=HTTPStatus.NOT_FOUND)
                return
            self.respond_html(gpa_trial_page(username, student, courses))
            return

        if path == "/gpa-trial/delete":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            if is_admin_username(username):
                self.respond_redirect("/")
                return
            index_raw = query.get("index", [""])[0]
            try:
                index = int(index_raw)
            except ValueError:
                self.respond_redirect("/gpa-trial")
                return
            with data_lock:
                students = load_students()
                student = find_student_by_username(username, students)
                trials = load_gpa_trials()
                key = normalize_student_code(username)
                courses = list(trials.get(key, []))
                if 0 <= index < len(courses):
                    courses.pop(index)
                    trials[key] = courses
                    save_gpa_trials(trials)
            self.respond_redirect("/gpa-trial")
            return

        if path == "/students/edit":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            if not is_admin_username(username):
                self.respond_html(dashboard_page(username, load_students(), "Chi admin moi duoc sua sinh vien.", is_error=True), status=HTTPStatus.FORBIDDEN)
                return
            student_id = query.get("id", [""])[0]
            with data_lock:
                student = find_student_by_username(student_id, load_students())
            if student is None:
                self.respond_html(dashboard_page(username, load_students(), "Khong tim thay sinh vien.", is_error=True), status=HTTPStatus.NOT_FOUND)
                return
            self.respond_html(admin_student_edit_page(username, student))
            return

        if path == "/students/delete":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            if not is_admin_username(username):
                self.respond_html(dashboard_page(username, load_students(), "Chi admin moi duoc xoa sinh vien.", is_error=True), status=HTTPStatus.FORBIDDEN)
                return
            student_id = query.get("id", [""])[0]
            if not student_id:
                self.respond_redirect("/")
                return
            with data_lock:
                students = load_students()
                target = find_student_by_username(student_id, students)
                if target is None:
                    self.respond_html(dashboard_page(username, students, "Khong tim thay sinh vien.", is_error=True), status=HTTPStatus.NOT_FOUND)
                    return
                filtered = [item for item in students if normalize_student_code(item["student_id"]) != normalize_student_code(student_id)]
                save_students(filtered)
                delete_student_account(student_id)
            self.respond_html(dashboard_page(username, load_students(), f"Da xoa sinh vien {normalize_student_code(student_id)}."))
            return

        self.respond_html(page_template("Not found", '<div class="content"><div class="flash error">Khong tim thay trang.</div></div>'), status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/login":
            self.handle_login()
            return
        if path == "/students":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            if not is_admin_username(username):
                self.respond_html(
                    dashboard_page(username, load_students(), "Chi admin moi duoc them sinh vien."),
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            self.handle_add_student(username)
            return
        if path == "/students/update":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            if not is_admin_username(username):
                self.respond_html(dashboard_page(username, load_students(), "Chi admin moi duoc sua sinh vien.", is_error=True), status=HTTPStatus.FORBIDDEN)
                return
            self.handle_update_student(username)
            return
        if path == "/profile":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            if is_admin_username(username):
                self.respond_redirect("/")
                return
            self.handle_update_profile(username)
            return
        if path == "/gpa-trial":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            if is_admin_username(username):
                self.respond_redirect("/")
                return
            self.handle_add_gpa_trial_course(username)
            return
        if path == "/password":
            username = self.current_username()
            if not username:
                self.respond_redirect("/")
                return
            self.handle_change_password(username)
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
        student_id = normalize_student_code(form.get("student_id", ""))
        full_name = normalize_full_name(form.get("full_name", ""))
        class_name = normalize_student_code(form.get("class_name", ""))
        address = normalize_free_text(form.get("address", ""))
        phone = normalize_phone(form.get("phone", ""))
        major = normalize_free_text(form.get("major", ""))
        try:
            gpa = normalize_gpa(form.get("gpa", ""))
        except ValueError:
            self.respond_html(dashboard_page(username, load_students(), "GPA phai la so trong khoang 0 den 10.", is_error=True), status=HTTPStatus.BAD_REQUEST)
            return

        if not student_id or not full_name or not class_name:
            self.respond_html(
                dashboard_page(username, load_students(), "Can nhap day du ma SV, ho ten va lop.", is_error=True),
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        with data_lock:
            students = load_students()
            if len(students) >= 256:
                self.respond_html(
                    dashboard_page(username, students, "Danh sach da day, khong them duoc nua.", is_error=True),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            if any(normalize_student_code(student["student_id"]) == student_id for student in students):
                self.respond_html(
                    dashboard_page(username, students, "Ma sinh vien da ton tai.", is_error=True),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            ok, error = create_student_account(student_id, "1")
            if not ok:
                self.respond_html(dashboard_page(username, students, error, is_error=True), status=HTTPStatus.BAD_REQUEST)
                return

            students.append(
                {
                    "student_id": student_id,
                    "full_name": full_name,
                    "class_name": class_name,
                    "address": address,
                    "phone": phone,
                    "major": major,
                    "gpa": gpa,
                }
            )
            save_students(students)

        self.respond_html(dashboard_page(username, load_students(), f'Da them sinh vien {student_id}. Tai khoan duoc tao voi mat khau mac dinh "1".'))

    def handle_update_student(self, username: str) -> None:
        form = self.read_form()
        old_student_id = normalize_student_code(form.get("old_student_id", ""))
        student_id = normalize_student_code(form.get("student_id", ""))
        full_name = normalize_full_name(form.get("full_name", ""))
        class_name = normalize_student_code(form.get("class_name", ""))
        address = normalize_free_text(form.get("address", ""))
        phone = normalize_phone(form.get("phone", ""))
        major = normalize_free_text(form.get("major", ""))

        try:
            gpa = normalize_gpa(form.get("gpa", ""))
        except ValueError:
            with data_lock:
                student = find_student_by_username(old_student_id, load_students())
            self.respond_html(admin_student_edit_page(username, student or {"student_id": old_student_id, "full_name": full_name, "class_name": class_name, "address": address, "phone": phone, "major": major, "gpa": form.get("gpa", "")}, "GPA phai la so trong khoang 0 den 10.", is_error=True), status=HTTPStatus.BAD_REQUEST)
            return

        if not student_id or not full_name or not class_name:
            with data_lock:
                student = find_student_by_username(old_student_id, load_students())
            self.respond_html(admin_student_edit_page(username, student or {"student_id": old_student_id, "full_name": full_name, "class_name": class_name, "address": address, "phone": phone, "major": major, "gpa": gpa}, "Thong tin sua khong duoc de trong.", is_error=True), status=HTTPStatus.BAD_REQUEST)
            return

        with data_lock:
            students = load_students()
            student = find_student_by_username(old_student_id, students)
            if student is None:
                self.respond_html(dashboard_page(username, students, "Khong tim thay sinh vien.", is_error=True), status=HTTPStatus.NOT_FOUND)
                return
            for other in students:
                if normalize_student_code(other["student_id"]) == student_id and normalize_student_code(other["student_id"]) != normalize_student_code(old_student_id):
                    self.respond_html(admin_student_edit_page(username, student, "Ma sinh vien moi da ton tai.", is_error=True), status=HTTPStatus.BAD_REQUEST)
                    return
            ok, error = update_student_account(old_student_id, student_id)
            if not ok:
                self.respond_html(admin_student_edit_page(username, student, error, is_error=True), status=HTTPStatus.BAD_REQUEST)
                return
            student["student_id"] = student_id
            student["full_name"] = full_name
            student["class_name"] = class_name
            student["address"] = address
            student["phone"] = phone
            student["major"] = major
            student["gpa"] = gpa
            save_students(students)

        self.respond_html(dashboard_page(username, load_students(), f"Da cap nhat sinh vien {student_id}."))

    def handle_update_profile(self, username: str) -> None:
        form = self.read_form()
        student_id = normalize_student_code(form.get("student_id", ""))
        full_name = normalize_full_name(form.get("full_name", ""))
        class_name = normalize_student_code(form.get("class_name", ""))
        address = normalize_free_text(form.get("address", ""))
        phone = normalize_phone(form.get("phone", ""))
        major = normalize_free_text(form.get("major", ""))

        with data_lock:
            students = load_students()
            current_student = find_student_by_username(username, students)
            if current_student is None:
                self.respond_html(dashboard_page(username, students, "Khong tim thay ho so sinh vien.", is_error=True), status=HTTPStatus.NOT_FOUND)
                return
            if not student_id or not full_name or not class_name:
                temp = dict(current_student)
                temp.update({"student_id": student_id, "full_name": full_name, "class_name": class_name, "address": address, "phone": phone, "major": major})
                self.respond_html(profile_edit_page(username, temp, "Thong tin khong duoc de trong.", is_error=True), status=HTTPStatus.BAD_REQUEST)
                return
            for other in students:
                if normalize_student_code(other["student_id"]) == student_id and normalize_student_code(other["student_id"]) != normalize_student_code(username):
                    temp = dict(current_student)
                    temp.update({"student_id": student_id, "full_name": full_name, "class_name": class_name, "address": address, "phone": phone, "major": major})
                    self.respond_html(profile_edit_page(username, temp, "Ma sinh vien moi da ton tai.", is_error=True), status=HTTPStatus.BAD_REQUEST)
                    return
            ok, error = update_student_account(username, student_id)
            if not ok:
                self.respond_html(profile_edit_page(username, current_student, error, is_error=True), status=HTTPStatus.BAD_REQUEST)
                return
            current_student["student_id"] = student_id
            current_student["full_name"] = full_name
            current_student["class_name"] = class_name
            current_student["address"] = address
            current_student["phone"] = phone
            current_student["major"] = major
            save_students(students)
        rename_gpa_trial_owner(username, student_id)
        update_session_username(self.session_token(), student_id)
        self.respond_redirect("/")

    def handle_change_password(self, username: str) -> None:
        form = self.read_form()
        current_password = form.get("current_password", "")
        new_password = form.get("new_password", "")
        confirm_password = form.get("confirm_password", "")

        if not current_password or not new_password or not confirm_password:
            self.respond_html(password_page(username, "Can nhap day du mat khau cu, mat khau moi va xac nhan.", is_error=True), status=HTTPStatus.BAD_REQUEST)
            return
        if new_password != confirm_password:
            self.respond_html(password_page(username, "Mat khau moi va xac nhan khong trung nhau.", is_error=True), status=HTTPStatus.BAD_REQUEST)
            return
        ok, error = change_user_password(username, current_password, new_password)
        if not ok:
            self.respond_html(password_page(username, error, is_error=True), status=HTTPStatus.BAD_REQUEST)
            return
        self.respond_html(password_page(username, "Da doi mat khau thanh cong."))

    def handle_add_gpa_trial_course(self, username: str) -> None:
        form = self.read_form()
        course_name = normalize_free_text(form.get("course_name", ""))
        score_raw = form.get("score", "")
        credits_raw = form.get("credits", "")

        with data_lock:
            students = load_students()
            student = find_student_by_username(username, students)
            trials = load_gpa_trials()
            key = normalize_student_code(username)
            courses = list(trials.get(key, []))

        if student is None:
            self.respond_html(dashboard_page(username, load_students(), "Khong tim thay ho so sinh vien.", is_error=True), status=HTTPStatus.NOT_FOUND)
            return
        if not course_name:
            self.respond_html(gpa_trial_page(username, student, courses, "Can nhap ten mon hoc.", is_error=True), status=HTTPStatus.BAD_REQUEST)
            return

        try:
            score = normalize_course_score(score_raw)
            credits = str(parse_course_credits(credits_raw))
        except ValueError:
            self.respond_html(gpa_trial_page(username, student, courses, "So tin phai la so nguyen duong va diem phai nam trong khoang 0 den 10.", is_error=True), status=HTTPStatus.BAD_REQUEST)
            return

        courses.append({"course_name": course_name, "credits": credits, "score": score})
        with data_lock:
            trials = load_gpa_trials()
            trials[key] = courses
            save_gpa_trials(trials)
        self.respond_html(gpa_trial_page(username, student, courses, "Da them mon hoc vao bang tinh GPA."))

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
