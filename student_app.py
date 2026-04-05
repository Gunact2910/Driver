#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QHeaderView,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.dat")
STUDENTS_FILE = os.path.join(BASE_DIR, "students.dat")
GPA_TRIALS_FILE = os.path.join(BASE_DIR, "gpa_trials.json")

USERNAME_LEN = 32
PASSWORD_HASH_LEN = 65
MAX_STUDENTS = 256
ADMIN_USERNAME = "admin"
STUDENT_FILE_HEADER = "STUDENT_V2"
STUDENT_FIELD_ORDER = (
    "student_id",
    "full_name",
    "class_name",
    "address",
    "phone",
    "major",
    "gpa",
)
SEARCH_FIELD_OPTIONS = [
    ("Tat ca", "all"),
    ("Ma SV", "student_id"),
    ("Ho va ten", "full_name"),
    ("Lop", "class_name"),
    ("Dia chi", "address"),
    ("So dien thoai", "phone"),
    ("Nganh hoc", "major"),
    ("GPA", "gpa"),
]
PUBLIC_SEARCH_FIELD_OPTIONS = [
    ("Tat ca", "all"),
    ("Ma SV", "student_id"),
    ("Ho va ten", "full_name"),
    ("Lop", "class_name"),
    ("Nganh hoc", "major"),
]


def collapse_spaces(value: str) -> str:
    return " ".join(value.strip().split())


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


def normalize_search_text(value: str) -> str:
    return " ".join(collapse_spaces(value).lower().split())


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


def normalize_login_username(value: str) -> str:
    collapsed = "".join(collapse_spaces(value).split())
    if collapsed.lower() == ADMIN_USERNAME:
        return ADMIN_USERNAME
    return collapsed.upper()


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
    if os.path.exists(USERS_FILE) and os.path.getsize(USERS_FILE) >= USERNAME_LEN + PASSWORD_HASH_LEN - 1:
        return
    save_users([{"username": ADMIN_USERNAME, "password_hash": sha256_hex("admin123")}])


def load_users() -> list[dict[str, str]]:
    users: list[dict[str, str]] = []

    ensure_default_admin()
    with open(USERS_FILE, "rb") as fp:
        while True:
            username_chunk = fp.read(USERNAME_LEN)
            password_chunk = fp.read(PASSWORD_HASH_LEN - 1)
            if len(username_chunk) != USERNAME_LEN or len(password_chunk) != PASSWORD_HASH_LEN - 1:
                break

            username = username_chunk.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            password_hash = password_chunk.decode("ascii", errors="ignore").rstrip("\x00")
            if username:
                users.append({"username": username, "password_hash": password_hash})

    if not users:
        users = [{"username": ADMIN_USERNAME, "password_hash": sha256_hex("admin123")}]
        save_users(users)
    return users


def save_users(users: list[dict[str, str]]) -> None:
    with open(USERS_FILE, "wb") as fp:
        for user in users:
            username_bytes = user["username"].encode("utf-8", errors="ignore")[: USERNAME_LEN - 1]
            hash_bytes = user["password_hash"].encode("ascii", errors="ignore")[: PASSWORD_HASH_LEN - 1]
            fp.write(username_bytes.ljust(USERNAME_LEN, b"\x00"))
            fp.write(hash_bytes.ljust(PASSWORD_HASH_LEN - 1, b"\x00"))


def load_students() -> list[dict[str, str]]:
    if not os.path.exists(STUDENTS_FILE):
        return []

    with open(STUDENTS_FILE, "r", encoding="utf-8", errors="ignore") as fp:
        lines = [line.rstrip("\n") for line in fp]

    students: list[dict[str, str]] = []
    if not lines:
        return students

    if lines[0] == STUDENT_FILE_HEADER:
        start_index = 1
        step = len(STUDENT_FIELD_ORDER)
        for index in range(start_index, len(lines), step):
            chunk = lines[index:index + step]
            if len(chunk) < step:
                break
            students.append(
                {
                    "student_id": normalize_student_code(chunk[0]),
                    "full_name": normalize_full_name(chunk[1]),
                    "class_name": normalize_student_code(chunk[2]),
                    "address": normalize_free_text(chunk[3]),
                    "phone": normalize_phone(chunk[4]),
                    "major": normalize_free_text(chunk[5]),
                    "gpa": "",
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
            fp.write(f"{student['address']}\n")
            fp.write(f"{student['phone']}\n")
            fp.write(f"{student['major']}\n")
            fp.write(f"{student['gpa']}\n")


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


def find_user(users: list[dict[str, str]], username: str) -> Optional[dict[str, str]]:
    normalized_username = normalize_login_username(username)
    for user in users:
        if normalize_login_username(user["username"]) == normalized_username:
            return user
    return None


def authenticate(username: str, password: str) -> Optional[str]:
    normalized_username = normalize_login_username(username)
    current_hash = sha256_hex(password)
    old_hash = legacy_hash_hex(password)
    users = load_users()

    for user in users:
        if normalize_login_username(user["username"]) != normalized_username:
            continue

        if user["password_hash"] == current_hash:
            return user["username"]
        if user["password_hash"] == old_hash:
            user["password_hash"] = current_hash
            save_users(users)
            return user["username"]
        return None

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


def student_gpa_value(student: dict[str, str]) -> float | None:
    try:
        return parse_gpa(student.get("gpa", ""))
    except ValueError:
        return None


def build_student_search_index(student: dict[str, str]) -> dict[str, str]:
    indexed = {
        "student_id": normalize_search_text(student["student_id"]),
        "full_name": normalize_search_text(student["full_name"]),
        "class_name": normalize_search_text(student["class_name"]),
        "address": normalize_search_text(student["address"]),
        "phone": normalize_search_text(student["phone"]),
        "major": normalize_search_text(student["major"]),
        "gpa": normalize_search_text(student["gpa"]),
        "username": normalize_search_text(student.get("username", "")),
        "password_hash": normalize_search_text(student.get("password_hash", "")),
    }
    indexed["all"] = " ".join(
        value for key, value in indexed.items() if key not in {"all"} and value
    )
    return indexed


def build_public_student_search_index(student: dict[str, str]) -> dict[str, str]:
    indexed = {
        "student_id": normalize_search_text(student["student_id"]),
        "full_name": normalize_search_text(student["full_name"]),
        "class_name": normalize_search_text(student["class_name"]),
        "major": normalize_search_text(student["major"]),
    }
    indexed["all"] = " ".join(value for value in indexed.values() if value)
    return indexed


def build_student_rows() -> list[dict[str, str]]:
    users = load_users()
    students = load_students()
    rows: list[dict[str, str]] = []

    for student in students:
        account = find_user(users, student["student_id"])
        rows.append(
            {
                "student_id": student["student_id"],
                "full_name": student["full_name"],
                "class_name": student["class_name"],
                "address": student["address"],
                "phone": student["phone"],
                "major": student["major"],
                "gpa": student["gpa"],
                "username": student["student_id"],
                "password_hash": account["password_hash"] if account else "",
            }
        )
        rows[-1]["_search_index"] = build_student_search_index(rows[-1])
    return rows


def create_student_account(student_id: str, password: str) -> tuple[bool, str]:
    users = load_users()
    normalized_student_id = normalize_student_code(student_id)

    if find_user(users, normalized_student_id) is not None:
        return False, "Ma sinh vien da ton tai trong users.dat."

    users.append(
        {
            "username": normalized_student_id,
            "password_hash": sha256_hex(password),
        }
    )
    save_users(users)
    return True, ""


def update_student_account(old_student_id: str, new_student_id: str, new_password: str) -> tuple[bool, str]:
    users = load_users()
    user = find_user(users, old_student_id)
    normalized_new_id = normalize_student_code(new_student_id)

    if user is None:
        return False, "Khong tim thay tai khoan sinh vien tuong ung."

    if normalize_student_code(old_student_id) != normalized_new_id and find_user(users, normalized_new_id) is not None:
        return False, "Ma sinh vien moi bi trung voi mot tai khoan khac."

    user["username"] = normalized_new_id
    if new_password:
        user["password_hash"] = sha256_hex(new_password)
    save_users(users)
    return True, ""


def delete_student_account(student_id: str) -> None:
    users = load_users()
    filtered = [user for user in users if normalize_login_username(user["username"]) != normalize_student_code(student_id)]
    save_users(filtered)


def configure_line_edit(widget: QLineEdit, placeholder: str = "") -> None:
    if placeholder:
        widget.setPlaceholderText(placeholder)
    widget.setFixedHeight(44)


def configure_form_layout(form: QFormLayout) -> None:
    form.setContentsMargins(0, 4, 0, 4)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(12)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)


class EditStudentDialog(QDialog):
    def __init__(self, student: dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.student = student
        self.setWindowTitle("Sua thong tin sinh vien")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        configure_form_layout(form)

        self.student_id_input = QLineEdit(student["student_id"])
        self.full_name_input = QLineEdit(student["full_name"])
        self.class_name_input = QLineEdit(student["class_name"])
        self.address_input = QLineEdit(student["address"])
        self.phone_input = QLineEdit(student["phone"])
        self.major_input = QLineEdit(student["major"])
        self.gpa_input = QLineEdit(student["gpa"])
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        configure_line_edit(self.student_id_input)
        configure_line_edit(self.full_name_input)
        configure_line_edit(self.class_name_input)
        configure_line_edit(self.address_input)
        configure_line_edit(self.phone_input)
        configure_line_edit(self.major_input)
        configure_line_edit(self.gpa_input, "0.00 - 10.00")
        configure_line_edit(self.password_input, "De trong neu giu nguyen mat khau")

        form.addRow("Ma SV", self.student_id_input)
        form.addRow("Ho va ten", self.full_name_input)
        form.addRow("Lop", self.class_name_input)
        form.addRow("Dia chi", self.address_input)
        form.addRow("So dien thoai", self.phone_input)
        form.addRow("Nganh hoc", self.major_input)
        form.addRow("GPA", self.gpa_input)
        form.addRow("Mat khau moi", self.password_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "student_id": normalize_student_code(self.student_id_input.text()),
            "full_name": normalize_full_name(self.full_name_input.text()),
            "class_name": normalize_student_code(self.class_name_input.text()),
            "address": normalize_free_text(self.address_input.text()),
            "phone": normalize_phone(self.phone_input.text()),
            "major": normalize_free_text(self.major_input.text()),
            "gpa": collapse_spaces(self.gpa_input.text()),
            "password": self.password_input.text(),
        }


class EditOwnProfileDialog(QDialog):
    def __init__(self, student: dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cap nhat thong tin ca nhan")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        configure_form_layout(form)

        self.student_id_input = QLineEdit(student["student_id"])
        self.full_name_input = QLineEdit(student["full_name"])
        self.class_name_input = QLineEdit(student["class_name"])
        self.address_input = QLineEdit(student["address"])
        self.phone_input = QLineEdit(student["phone"])
        self.major_input = QLineEdit(student["major"])
        configure_line_edit(self.student_id_input)
        configure_line_edit(self.full_name_input)
        configure_line_edit(self.class_name_input)
        configure_line_edit(self.address_input)
        configure_line_edit(self.phone_input)
        configure_line_edit(self.major_input)

        form.addRow("Ma SV", self.student_id_input)
        form.addRow("Ho va ten", self.full_name_input)
        form.addRow("Lop", self.class_name_input)
        form.addRow("Dia chi", self.address_input)
        form.addRow("So dien thoai", self.phone_input)
        form.addRow("Nganh hoc", self.major_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "student_id": normalize_student_code(self.student_id_input.text()),
            "full_name": normalize_full_name(self.full_name_input.text()),
            "class_name": normalize_student_code(self.class_name_input.text()),
            "address": normalize_free_text(self.address_input.text()),
            "phone": normalize_phone(self.phone_input.text()),
            "major": normalize_free_text(self.major_input.text()),
        }


class ChangePasswordDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Doi mat khau")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        configure_form_layout(form)

        self.current_password_input = QLineEdit()
        self.current_password_input.setEchoMode(QLineEdit.Password)
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)

        configure_line_edit(self.current_password_input, "Nhap mat khau hien tai")
        configure_line_edit(self.new_password_input, "Nhap mat khau moi")
        configure_line_edit(self.confirm_password_input, "Nhap lai mat khau moi")

        form.addRow("Mat khau cu", self.current_password_input)
        form.addRow("Mat khau moi", self.new_password_input)
        form.addRow("Xac nhan mat khau", self.confirm_password_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "current_password": self.current_password_input.text(),
            "new_password": self.new_password_input.text(),
            "confirm_password": self.confirm_password_input.text(),
        }


class AddCourseDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nhap diem mon hoc")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        configure_form_layout(form)

        self.course_name_input = QLineEdit()
        self.score_input = QLineEdit()
        self.credits_input = QLineEdit()

        configure_line_edit(self.course_name_input, "Vi du: Cau truc du lieu")
        configure_line_edit(self.score_input, "0.00 - 10.00")
        configure_line_edit(self.credits_input, "Vi du: 3")

        form.addRow("Mon hoc", self.course_name_input)
        form.addRow("Diem", self.score_input)
        form.addRow("So tin", self.credits_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "course_name": normalize_free_text(self.course_name_input.text()),
            "score": collapse_spaces(self.score_input.text()),
            "credits": collapse_spaces(self.credits_input.text()),
        }


class GpaTrialDialog(QDialog):
    def __init__(self, student_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.student_id = normalize_student_code(student_id)
        self.setWindowTitle("Tinh GPA du kien")
        self.setMinimumSize(760, 520)
        trials = load_gpa_trials()
        self.courses: list[dict[str, str]] = list(trials.get(self.student_id, []))
        self.build_ui()
        self.refresh_table()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel(f"Tinh GPA du kien cho {self.student_id}")
        title.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
        note = QLabel("Du lieu nay chi de tham khao va duoc luu rieng theo tai khoan sinh vien. Khong ghi de GPA chinh thuc.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #6b6b6b;")

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Ten mon", "So tin", "Diem"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(12)
        summary_label = QLabel("Tong GPA du kien")
        summary_label.setFont(QFont("DejaVu Sans", 12, QFont.Bold))
        self.gpa_value_label = QLabel("0.00")
        self.gpa_value_label.setStyleSheet("font-size: 22px; font-weight: 700; color: #1d6b3a;")
        summary_row.addWidget(summary_label)
        summary_row.addWidget(self.gpa_value_label)
        summary_row.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        add_button = QPushButton("Nhap diem mon hoc")
        add_button.clicked.connect(self.add_course)
        delete_button = QPushButton("Xoa mon da chon")
        delete_button.setObjectName("danger")
        delete_button.clicked.connect(self.delete_selected_course)
        close_button = QPushButton("Dong")
        close_button.setObjectName("secondary")
        close_button.clicked.connect(self.accept)
        action_row.addWidget(add_button)
        action_row.addWidget(delete_button)
        action_row.addStretch(1)
        action_row.addWidget(close_button)

        layout.addWidget(title)
        layout.addWidget(note)
        layout.addWidget(self.table)
        layout.addLayout(summary_row)
        layout.addLayout(action_row)

    def refresh_table(self) -> None:
        self.table.setRowCount(len(self.courses))
        for row_index, course in enumerate(self.courses):
            values = [
                str(row_index + 1),
                course["course_name"],
                course["credits"],
                course["score"],
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index in {0, 2, 3}:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, col_index, item)

        self.gpa_value_label.setText(calculate_trial_gpa(self.courses) if self.courses else "0.00")
        self.persist_courses()

    def persist_courses(self) -> None:
        trials = load_gpa_trials()
        trials[self.student_id] = self.courses
        save_gpa_trials(trials)

    def add_course(self) -> None:
        dialog = AddCourseDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.values()
        if not values["course_name"]:
            QMessageBox.warning(self, "Thieu du lieu", "Can nhap ten mon hoc.")
            return

        try:
            credits = str(parse_course_credits(values["credits"]))
            score = normalize_course_score(values["score"])
        except ValueError:
            QMessageBox.warning(self, "Du lieu khong hop le", "So tin phai la so nguyen duong va diem phai nam trong khoang 0 den 10.")
            return

        self.courses.append(
            {
                "course_name": values["course_name"],
                "credits": credits,
                "score": score,
            }
        )
        self.refresh_table()

    def delete_selected_course(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.information(self, "Chua chon", "Hay chon mot mon hoc trong bang.")
            return
        row_index = indexes[0].row()
        if 0 <= row_index < len(self.courses):
            self.courses.pop(row_index)
            self.refresh_table()


class LoginWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.next_window: Optional[QWidget] = None
        self.setWindowTitle("Student Manager Login")
        self.setMinimumSize(420, 320)
        self.build_ui()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(18)

        title = QLabel("Student Manager")
        title.setFont(QFont("DejaVu Sans", 20, QFont.Bold))
        subtitle = QLabel("Dang nhap vao giao dien desktop quan ly sinh vien.")
        subtitle.setStyleSheet("color: #6b6b6b;")

        panel = QFrame()
        panel.setObjectName("panel")
        form = QFormLayout(panel)
        configure_form_layout(form)

        self.username_input = QLineEdit()
        configure_line_edit(self.username_input, "admin hoac ma sinh vien")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        configure_line_edit(self.password_input, "Nhap mat khau")
        self.password_input.returnPressed.connect(self.handle_login)

        form.addRow("Username", self.username_input)
        form.addRow("Password", self.password_input)

        login_button = QPushButton("Dang nhap")
        login_button.clicked.connect(self.handle_login)

        hint = QLabel("Admin mac dinh: admin / admin123")
        hint.setStyleSheet("color: #8a4b08; font-weight: 600;")

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(panel)
        root.addWidget(login_button)
        root.addWidget(hint)
        root.addStretch(1)

        self.setStyleSheet(
            """
            QWidget {
                background: #f6efe6;
                color: #1e1d1a;
                font-family: "DejaVu Sans";
                font-size: 14px;
            }
            QFrame#panel {
                background: #fffaf3;
                border: 1px solid #e7dccc;
                border-radius: 18px;
                padding: 12px;
            }
            QLineEdit {
                background: white;
                border: 1px solid #d9cbb7;
                border-radius: 10px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border: 1px solid #1d6b3a;
            }
            QPushButton {
                background: #1d6b3a;
                color: white;
                border: 0;
                border-radius: 12px;
                padding: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #14532d;
            }
            """
        )

    def handle_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        matched_username = authenticate(username, password)

        if matched_username is None:
            QMessageBox.warning(self, "Dang nhap that bai", "Sai username hoac password.")
            return

        if normalize_login_username(matched_username) == ADMIN_USERNAME:
            self.next_window = AdminDashboardWindow(matched_username)
        else:
            self.next_window = StudentDashboardWindow(matched_username)

        self.next_window.show()
        self.close()


class BaseWindow(QMainWindow):
    def open_login_window(self) -> None:
        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()

    def prompt_change_password(self, username: str) -> None:
        dialog = ChangePasswordDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.values()
        if not values["current_password"] or not values["new_password"] or not values["confirm_password"]:
            QMessageBox.warning(self, "Thieu du lieu", "Can nhap day du mat khau cu, mat khau moi va xac nhan.")
            return

        if values["new_password"] != values["confirm_password"]:
            QMessageBox.warning(self, "Khong khop", "Mat khau moi va xac nhan mat khau khong trung nhau.")
            return

        ok, error = change_user_password(username, values["current_password"], values["new_password"])
        if not ok:
            QMessageBox.warning(self, "Khong doi duoc mat khau", error)
            return

        QMessageBox.information(self, "Da doi mat khau", "Mat khau moi da duoc bam SHA-256 va luu vao users.dat.")

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6efe6;
                color: #1e1d1a;
                font-family: "DejaVu Sans";
                font-size: 14px;
            }
            QFrame#header {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #1d6b3a, stop:1 #14532d);
                border-radius: 16px;
            }
            QFrame#panel {
                background: #fffaf3;
                border: 1px solid #e7dccc;
                border-radius: 16px;
            }
            QFrame#metricPanel {
                background: #fcf6ee;
                border: 1px solid #e7dccc;
                border-radius: 14px;
            }
            QLabel#headerTitle {
                color: #f9f5ee;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#headerSubtitle {
                color: rgba(249,245,238,0.82);
                font-size: 12px;
            }
            QLabel#statValue {
                font-size: 15px;
                font-weight: 700;
                color: #1d6b3a;
            }
            QLabel#statLabel {
                color: #7a6e5d;
                font-size: 12px;
            }
            QLineEdit {
                background: white;
                border: 1px solid #d9cbb7;
                border-radius: 10px;
                padding: 8px 12px;
            }
            QComboBox {
                background: white;
                border: 1px solid #d9cbb7;
                border-radius: 10px;
                padding: 7px 12px;
                min-height: 34px;
            }
            QLineEdit:focus {
                border: 1px solid #1d6b3a;
            }
            QComboBox:focus {
                border: 1px solid #1d6b3a;
            }
            QPushButton {
                background: #1d6b3a;
                color: white;
                border: 0;
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: 700;
                min-height: 34px;
            }
            QPushButton:hover {
                background: #14532d;
            }
            QPushButton#secondary {
                background: #ebdfd0;
                color: #7d4514;
            }
            QPushButton#danger {
                background: #b91c1c;
                color: white;
            }
            QPushButton#danger:hover {
                background: #991b1b;
            }
            QLabel#hashBox {
                background: white;
                border: 1px solid #eadfce;
                border-radius: 12px;
                padding: 12px;
                color: #5b4d3d;
            }
            QTableWidget {
                background: white;
                border: 1px solid #eadfce;
                border-radius: 12px;
                gridline-color: #f1e8db;
                alternate-background-color: #fcf7f0;
            }
            QScrollArea {
                border: 0;
                background: transparent;
            }
            QHeaderView::section {
                background: #f3eadf;
                color: #6b6559;
                border: 0;
                border-bottom: 1px solid #e7dccc;
                padding: 10px;
                font-weight: 700;
            }
            """
        )

    def make_metric_card(self, label_text: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setObjectName("metricPanel")
        frame.setMaximumHeight(60)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(0)
        value = QLabel("0")
        value.setObjectName("statValue")
        label = QLabel(label_text)
        label.setObjectName("statLabel")
        layout.addWidget(value)
        layout.addWidget(label)
        return frame, value


class AdminDashboardWindow(BaseWindow):
    def __init__(self, username: str) -> None:
        super().__init__()
        self.username = username
        self.rows: list[dict[str, str]] = []
        self.setWindowTitle("Student Manager Desktop - Admin")
        self.setMinimumSize(1220, 720)
        self.build_ui()
        self.reload_data()
        self.apply_styles()

    def build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("header")
        header.setMaximumHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(12)
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("Bang dieu khien admin")
        title.setObjectName("headerTitle")
        subtitle = QLabel("Them, sua, xoa sinh vien va tai khoan sinh vien ngay trong giao dien desktop.")
        subtitle.setObjectName("headerSubtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        action_buttons = QHBoxLayout()
        action_buttons.setSpacing(8)
        change_password_button = QPushButton("Doi mat khau")
        change_password_button.setFixedSize(132, 34)
        change_password_button.clicked.connect(lambda: self.prompt_change_password(self.username))
        logout_button = QPushButton("Logout")
        logout_button.setFixedSize(94, 34)
        logout_button.setObjectName("secondary")
        logout_button.clicked.connect(self.open_login_window)
        action_buttons.addWidget(change_password_button)
        action_buttons.addWidget(logout_button)
        header_layout.addLayout(title_block, 1)
        header_layout.addLayout(action_buttons, 0)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)
        self.total_card = self.make_metric_card("Tong sinh vien")
        self.class_card = self.make_metric_card("So lop")
        self.account_card = self.make_metric_card("Tai khoan SV")
        metrics_row.addWidget(self.total_card[0])
        metrics_row.addWidget(self.class_card[0])
        metrics_row.addWidget(self.account_card[0])

        body = QHBoxLayout()
        body.setSpacing(12)

        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        left_title = QLabel("Danh sach sinh vien va tai khoan")
        left_title.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
        search_controls = QHBoxLayout()
        search_controls.setSpacing(8)
        self.search_field_combo = QComboBox()
        for label, value in SEARCH_FIELD_OPTIONS:
            self.search_field_combo.addItem(label, value)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tim theo truong duoc chon...")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Thu tu goc", "default")
        self.sort_combo.addItem("GPA cao den thap", "gpa_desc")
        self.sort_combo.addItem("GPA thap den cao", "gpa_asc")
        self.search_field_combo.currentIndexChanged.connect(self.refresh_table)
        self.search_input.textChanged.connect(self.refresh_table)
        self.sort_combo.currentIndexChanged.connect(self.refresh_table)
        search_controls.addWidget(self.search_field_combo)
        search_controls.addWidget(self.search_input, 1)
        search_controls.addWidget(self.sort_combo)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "#",
            "Ma SV",
            "Ho va ten",
            "Lop",
            "Nganh hoc",
            "GPA",
            "So dien thoai",
            "Dia chi",
            "Username",
            "Password hash",
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.update_detail_panel)

        action_row = QHBoxLayout()
        self.edit_button = QPushButton("Sua sinh vien")
        self.edit_button.clicked.connect(self.edit_selected_student)
        self.delete_button = QPushButton("Xoa sinh vien")
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self.delete_selected_student)
        reload_button = QPushButton("Tai lai")
        reload_button.setObjectName("secondary")
        reload_button.clicked.connect(self.reload_data)
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.delete_button)
        action_row.addWidget(reload_button)

        left_layout.addWidget(left_title)
        left_layout.addLayout(search_controls)
        left_layout.addWidget(self.table)
        left_layout.addLayout(action_row)

        right_panel = QFrame()
        right_panel.setObjectName("panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll_content = QWidget()
        right_scroll.setWidget(right_scroll_content)

        right_content_layout = QVBoxLayout(right_scroll_content)
        right_content_layout.setContentsMargins(16, 16, 16, 16)
        right_content_layout.setSpacing(12)

        right_title = QLabel("Them sinh vien moi")
        right_title.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
        right_note = QLabel('Khi them sinh vien, he thong se tao luon username = ma sinh vien, mat khau mac dinh la "1" va luu duoi dang SHA-256.')
        right_note.setWordWrap(True)
        right_note.setStyleSheet("color: #6b6b6b;")

        form = QFormLayout()
        configure_form_layout(form)
        self.student_id_input = QLineEdit()
        self.full_name_input = QLineEdit()
        self.class_name_input = QLineEdit()
        self.address_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.major_input = QLineEdit()
        self.gpa_input = QLineEdit()
        configure_line_edit(self.student_id_input, "Vi du: CT070346")
        configure_line_edit(self.full_name_input, "Nhap ho va ten")
        configure_line_edit(self.class_name_input, "Vi du: CT7C")
        configure_line_edit(self.address_input, "So nha, duong, quan/huyen...")
        configure_line_edit(self.phone_input, "Vi du: 0901234567")
        configure_line_edit(self.major_input, "Vi du: Cong nghe thong tin")
        configure_line_edit(self.gpa_input, "0.00 - 10.00")
        form.addRow("Ma SV", self.student_id_input)
        form.addRow("Ho va ten", self.full_name_input)
        form.addRow("Lop", self.class_name_input)
        form.addRow("Dia chi", self.address_input)
        form.addRow("So dien thoai", self.phone_input)
        form.addRow("Nganh hoc", self.major_input)
        form.addRow("GPA", self.gpa_input)

        add_button = QPushButton("Them sinh vien + tai khoan")
        add_button.clicked.connect(self.add_student)

        detail_title = QLabel("Thong tin tai khoan dang chon")
        detail_title.setFont(QFont("DejaVu Sans", 13, QFont.Bold))
        self.detail_labels: dict[str, QLabel] = {}
        detail_grid = QGridLayout()
        detail_grid.setHorizontalSpacing(10)
        detail_grid.setVerticalSpacing(8)

        for row_index, key in enumerate(["student_id", "full_name", "class_name", "address", "phone", "major", "gpa", "username", "password_hash"]):
            key_label = QLabel(
                {
                    "student_id": "Ma SV",
                    "full_name": "Ho va ten",
                    "class_name": "Lop",
                    "address": "Dia chi",
                    "phone": "So dien thoai",
                    "major": "Nganh hoc",
                    "gpa": "GPA",
                    "username": "Username",
                    "password_hash": "SHA-256",
                }[key]
            )
            value_label = QLabel("-")
            if key == "password_hash":
                value_label.setWordWrap(True)
                value_label.setObjectName("hashBox")
            detail_grid.addWidget(key_label, row_index, 0)
            detail_grid.addWidget(value_label, row_index, 1)
            self.detail_labels[key] = value_label

        right_content_layout.addWidget(right_title)
        right_content_layout.addWidget(right_note)
        right_content_layout.addLayout(form)
        right_content_layout.addWidget(add_button)
        right_content_layout.addSpacing(6)
        right_content_layout.addWidget(detail_title)
        right_content_layout.addLayout(detail_grid)
        right_content_layout.addStretch(1)
        right_layout.addWidget(right_scroll)

        body.addWidget(left_panel, 5)
        body.addWidget(right_panel, 4)

        root.addWidget(header)
        root.addLayout(metrics_row)
        root.addLayout(body)

    def filtered_rows(self) -> list[dict[str, str]]:
        query = normalize_search_text(self.search_input.text())
        selected_field = str(self.search_field_combo.currentData())

        if query:
            rows = [
                row for row in self.rows
                if query in row["_search_index"].get(selected_field, "")
            ]
        else:
            rows = list(self.rows)

        sort_mode = str(self.sort_combo.currentData())
        if sort_mode == "gpa_desc":
            rows.sort(
                key=lambda row: (
                    student_gpa_value(row) is None,
                    -(student_gpa_value(row) or 0.0),
                    row["student_id"],
                )
            )
        elif sort_mode == "gpa_asc":
            rows.sort(
                key=lambda row: (
                    student_gpa_value(row) is None,
                    student_gpa_value(row) if student_gpa_value(row) is not None else 0.0,
                    row["student_id"],
                )
            )
        return rows

    def reload_data(self) -> None:
        self.rows = build_student_rows()
        self.refresh_table()

    def refresh_stats(self) -> None:
        classes = {row["class_name"] for row in self.rows if row["class_name"]}
        accounts = len([row for row in self.rows if row["password_hash"]])
        self.total_card[1].setText(str(len(self.rows)))
        self.class_card[1].setText(str(len(classes)))
        self.account_card[1].setText(str(accounts))

    def refresh_table(self) -> None:
        rows = self.filtered_rows()
        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                str(row_index + 1),
                row["student_id"],
                row["full_name"],
                row["class_name"],
                row["major"],
                row["gpa"],
                row["phone"],
                row["address"],
                row["username"],
                row["password_hash"],
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, col_index, item)

        self.refresh_stats()
        self.update_detail_panel()

    def selected_student(self) -> Optional[dict[str, str]]:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None

        row_index = indexes[0].row()
        filtered = self.filtered_rows()
        if row_index >= len(filtered):
            return None
        return filtered[row_index]

    def update_detail_panel(self) -> None:
        student = self.selected_student()
        for key, label in self.detail_labels.items():
            label.setText(student[key] if student else "-")

    def add_student(self) -> None:
        if len(self.rows) >= MAX_STUDENTS:
            QMessageBox.warning(self, "Day danh sach", "Da dat gioi han 256 sinh vien.")
            return

        student_id = normalize_student_code(self.student_id_input.text())
        full_name = normalize_full_name(self.full_name_input.text())
        class_name = normalize_student_code(self.class_name_input.text())
        address = normalize_free_text(self.address_input.text())
        phone = normalize_phone(self.phone_input.text())
        major = normalize_free_text(self.major_input.text())
        gpa_raw = collapse_spaces(self.gpa_input.text())

        try:
            gpa = normalize_gpa(gpa_raw)
        except ValueError:
            QMessageBox.warning(self, "GPA khong hop le", "GPA phai la so trong khoang 0 den 10.")
            return

        if not student_id or not full_name or not class_name:
            QMessageBox.warning(self, "Thieu du lieu", "Can nhap ma SV, ho ten va lop.")
            return

        students = load_students()
        if any(normalize_student_code(student["student_id"]) == student_id for student in students):
            QMessageBox.warning(self, "Trung ma", "Ma sinh vien da ton tai.")
            return

        ok, error = create_student_account(student_id, "1")
        if not ok:
            QMessageBox.warning(self, "Khong tao duoc tai khoan", error)
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

        self.student_id_input.clear()
        self.full_name_input.clear()
        self.class_name_input.clear()
        self.address_input.clear()
        self.phone_input.clear()
        self.major_input.clear()
        self.gpa_input.clear()
        self.reload_data()
        QMessageBox.information(self, "Da them", f'Da them sinh vien {student_id}. Tai khoan duoc tao voi mat khau mac dinh "1" va luu SHA-256.')

    def edit_selected_student(self) -> None:
        student = self.selected_student()
        if student is None:
            QMessageBox.information(self, "Chua chon", "Hay chon mot sinh vien trong bang.")
            return

        dialog = EditStudentDialog(student, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.values()
        try:
            values["gpa"] = normalize_gpa(values["gpa"])
        except ValueError:
            QMessageBox.warning(self, "GPA khong hop le", "GPA phai la so trong khoang 0 den 10.")
            return

        if not values["student_id"] or not values["full_name"] or not values["class_name"]:
            QMessageBox.warning(self, "Thieu du lieu", "Thong tin sua khong duoc de trong.")
            return

        students = load_students()
        for other in students:
            if normalize_student_code(other["student_id"]) == values["student_id"] and normalize_student_code(other["student_id"]) != normalize_student_code(student["student_id"]):
                QMessageBox.warning(self, "Trung ma", "Ma sinh vien moi da ton tai.")
                return

        ok, error = update_student_account(student["student_id"], values["student_id"], values["password"])
        if not ok:
            QMessageBox.warning(self, "Khong cap nhat duoc tai khoan", error)
            return

        for item in students:
            if normalize_student_code(item["student_id"]) == normalize_student_code(student["student_id"]):
                item["student_id"] = values["student_id"]
                item["full_name"] = values["full_name"]
                item["class_name"] = values["class_name"]
                item["address"] = values["address"]
                item["phone"] = values["phone"]
                item["major"] = values["major"]
                item["gpa"] = values["gpa"]
                break
        save_students(students)
        self.reload_data()
        QMessageBox.information(self, "Da cap nhat", f"Da sua sinh vien {values['student_id']}.")

    def delete_selected_student(self) -> None:
        student = self.selected_student()
        if student is None:
            QMessageBox.information(self, "Chua chon", "Hay chon mot sinh vien de xoa.")
            return

        answer = QMessageBox.question(
            self,
            "Xac nhan xoa",
            f"Xoa sinh vien {student['student_id']} va tai khoan dang nhap cua sinh vien nay?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        students = [
            item for item in load_students()
            if normalize_student_code(item["student_id"]) != normalize_student_code(student["student_id"])
        ]
        save_students(students)
        delete_student_account(student["student_id"])
        self.reload_data()
        QMessageBox.information(self, "Da xoa", f"Da xoa sinh vien {student['student_id']}.")


class StudentDashboardWindow(BaseWindow):
    def __init__(self, username: str) -> None:
        super().__init__()
        self.username = normalize_login_username(username)
        self.setWindowTitle("Student Manager Desktop - Student")
        self.setMinimumSize(1080, 680)
        self.public_rows: list[dict[str, str]] = []
        self.build_ui()
        self.reload_data()
        self.apply_styles()

    def build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("header")
        header.setMaximumHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(12)
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("Khong gian sinh vien")
        title.setObjectName("headerTitle")
        subtitle = QLabel("Sinh vien xem duoc danh sach cong khai va chi sua thong tin cua chinh minh.")
        subtitle.setObjectName("headerSubtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        action_buttons = QHBoxLayout()
        action_buttons.setSpacing(8)
        change_password_button = QPushButton("Doi mat khau")
        change_password_button.setFixedSize(132, 34)
        change_password_button.clicked.connect(lambda: self.prompt_change_password(self.username))
        logout_button = QPushButton("Logout")
        logout_button.setFixedSize(94, 34)
        logout_button.setObjectName("secondary")
        logout_button.clicked.connect(self.open_login_window)
        action_buttons.addWidget(change_password_button)
        action_buttons.addWidget(logout_button)
        header_layout.addLayout(title_block, 1)
        header_layout.addLayout(action_buttons, 0)

        body = QHBoxLayout()
        body.setSpacing(12)

        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        left_title = QLabel("Danh sach sinh vien")
        left_title.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
        left_note = QLabel("Chi hien thi thong tin cong khai cua sinh vien khac: ma SV, ho ten, lop, nganh hoc.")
        left_note.setStyleSheet("color: #6b6b6b;")

        search_controls = QHBoxLayout()
        search_controls.setSpacing(8)
        self.search_field_combo = QComboBox()
        for label, value in PUBLIC_SEARCH_FIELD_OPTIONS:
            self.search_field_combo.addItem(label, value)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tim theo truong duoc chon...")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Thu tu goc", "default")
        self.search_field_combo.currentIndexChanged.connect(self.refresh_public_table)
        self.search_input.textChanged.connect(self.refresh_public_table)
        self.sort_combo.currentIndexChanged.connect(self.refresh_public_table)
        search_controls.addWidget(self.search_field_combo)
        search_controls.addWidget(self.search_input, 1)
        search_controls.addWidget(self.sort_combo)

        self.public_table = QTableWidget(0, 5)
        self.public_table.setHorizontalHeaderLabels(["#", "Ma SV", "Ho va ten", "Lop", "Nganh hoc"])
        self.public_table.horizontalHeader().setStretchLastSection(True)
        self.public_table.verticalHeader().setVisible(False)
        self.public_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.public_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.public_table.setAlternatingRowColors(True)

        left_layout.addWidget(left_title)
        left_layout.addWidget(left_note)
        left_layout.addLayout(search_controls)
        left_layout.addWidget(self.public_table)

        right_panel = QFrame()
        right_panel.setObjectName("panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll_content = QWidget()
        right_scroll.setWidget(right_scroll_content)

        right_content_layout = QVBoxLayout(right_scroll_content)
        right_content_layout.setContentsMargins(16, 16, 16, 16)
        right_content_layout.setSpacing(12)

        right_title = QLabel("Thong tin ca nhan")
        right_title.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
        right_note = QLabel("Ban chi sua duoc thong tin cua chinh minh. Khong hien thi mat khau hoac password hash.")
        right_note.setWordWrap(True)
        right_note.setStyleSheet("color: #6b6b6b;")

        self.profile_labels: dict[str, QLabel] = {}
        for key, title_text in [
            ("student_id", "Ma SV"),
            ("full_name", "Ho va ten"),
            ("class_name", "Lop"),
            ("address", "Dia chi"),
            ("phone", "So dien thoai"),
            ("major", "Nganh hoc"),
            ("gpa", "GPA"),
            ("username", "Username"),
        ]:
            block = QVBoxLayout()
            label_title = QLabel(title_text)
            value_label = QLabel("-")
            value_label.setStyleSheet("font-weight: 700;")
            block.addWidget(label_title)
            block.addWidget(value_label)
            right_content_layout.addLayout(block)
            self.profile_labels[key] = value_label

        self.edit_profile_button = QPushButton("Sua thong tin ca nhan")
        self.edit_profile_button.clicked.connect(self.edit_own_profile)
        self.gpa_trial_button = QPushButton("Tinh GPA du kien")
        self.gpa_trial_button.clicked.connect(self.open_gpa_trial_dialog)
        right_content_layout.insertWidget(0, right_title)
        right_content_layout.insertWidget(1, right_note)
        right_content_layout.addWidget(self.edit_profile_button)
        right_content_layout.addWidget(self.gpa_trial_button)
        right_content_layout.addStretch(1)
        right_layout.addWidget(right_scroll)

        body.addWidget(left_panel, 5)
        body.addWidget(right_panel, 3)

        root.addWidget(header)
        root.addLayout(body)

    def filtered_public_rows(self) -> list[dict[str, str]]:
        query = normalize_search_text(self.search_input.text())
        selected_field = str(self.search_field_combo.currentData())

        if query:
            rows = [
                row for row in self.public_rows
                if query in row["_search_index"].get(selected_field, "")
            ]
        else:
            rows = list(self.public_rows)

        return rows

    def load_profile(self) -> Optional[dict[str, str]]:
        row = None
        for student in build_student_rows():
            if normalize_student_code(student["student_id"]) == self.username:
                row = student
                break

        if row is None:
            QMessageBox.warning(self, "Khong tim thay", "Khong tim thay ho so sinh vien gan voi tai khoan nay.")
            return None

        for key, label in self.profile_labels.items():
            label.setText(row[key])
        return row

    def refresh_public_table(self) -> None:
        rows = self.filtered_public_rows()
        self.public_table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                str(row_index + 1),
                row["student_id"],
                row["full_name"],
                row["class_name"],
                row["major"],
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.public_table.setItem(row_index, col_index, item)

    def reload_data(self) -> None:
        self.public_rows = [
            {
                "student_id": row["student_id"],
                "full_name": row["full_name"],
                "class_name": row["class_name"],
                "major": row["major"],
                "_search_index": build_public_student_search_index(row),
            }
            for row in build_student_rows()
        ]
        self.refresh_public_table()
        self.load_profile()

    def edit_own_profile(self) -> None:
        current_profile = self.load_profile()
        if current_profile is None:
            return

        dialog = EditOwnProfileDialog(current_profile, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.values()
        if not values["student_id"] or not values["full_name"] or not values["class_name"]:
            QMessageBox.warning(self, "Thieu du lieu", "Thong tin khong duoc de trong.")
            return

        students = load_students()
        for other in students:
            if normalize_student_code(other["student_id"]) == values["student_id"] and normalize_student_code(other["student_id"]) != self.username:
                QMessageBox.warning(self, "Trung ma", "Ma sinh vien moi da ton tai.")
                return

        ok, error = update_student_account(self.username, values["student_id"], "")
        if not ok:
            QMessageBox.warning(self, "Khong cap nhat duoc tai khoan", error)
            return

        for item in students:
            if normalize_student_code(item["student_id"]) == self.username:
                item["student_id"] = values["student_id"]
                item["full_name"] = values["full_name"]
                item["class_name"] = values["class_name"]
                item["address"] = values["address"]
                item["phone"] = values["phone"]
                item["major"] = values["major"]
                break
        save_students(students)
        rename_gpa_trial_owner(self.username, values["student_id"])
        self.username = values["student_id"]
        self.reload_data()
        QMessageBox.information(self, "Da cap nhat", "Da cap nhat thong tin ca nhan.")

    def open_gpa_trial_dialog(self) -> None:
        dialog = GpaTrialDialog(self.username, self)
        dialog.exec_()


def main() -> None:
    ensure_default_admin()
    app = QApplication(sys.argv)
    app.setApplicationName("Student Manager Desktop")
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
