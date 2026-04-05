#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import os
import sys
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.dat")
STUDENTS_FILE = os.path.join(BASE_DIR, "students.dat")

USERNAME_LEN = 32
PASSWORD_HASH_LEN = 65
MAX_STUDENTS = 256
ADMIN_USERNAME = "admin"


def collapse_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_student_code(value: str) -> str:
    return "".join(collapse_spaces(value).split()).upper()


def normalize_full_name(value: str) -> str:
    collapsed = collapse_spaces(value)
    if not collapsed:
        return ""
    return " ".join(part[:1].upper() + part[1:].lower() for part in collapsed.split(" "))


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
                "username": student["student_id"],
                "password_hash": account["password_hash"] if account else "",
            }
        )
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


class EditStudentDialog(QDialog):
    def __init__(self, student: dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.student = student
        self.setWindowTitle("Sua thong tin sinh vien")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.student_id_input = QLineEdit(student["student_id"])
        self.full_name_input = QLineEdit(student["full_name"])
        self.class_name_input = QLineEdit(student["class_name"])
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("De trong neu giu nguyen mat khau")

        form.addRow("Ma SV", self.student_id_input)
        form.addRow("Ho va ten", self.full_name_input)
        form.addRow("Lop", self.class_name_input)
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
            "password": self.password_input.text(),
        }


class EditOwnProfileDialog(QDialog):
    def __init__(self, student: dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cap nhat thong tin ca nhan")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.student_id_input = QLineEdit(student["student_id"])
        self.full_name_input = QLineEdit(student["full_name"])
        self.class_name_input = QLineEdit(student["class_name"])

        form.addRow("Ma SV", self.student_id_input)
        form.addRow("Ho va ten", self.full_name_input)
        form.addRow("Lop", self.class_name_input)

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
        }


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
        form.setSpacing(12)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("admin hoac ma sinh vien")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Nhap mat khau")
        self.password_input.setEchoMode(QLineEdit.Password)
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
                padding: 10px 12px;
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
                border-radius: 22px;
            }
            QFrame#panel {
                background: #fffaf3;
                border: 1px solid #e7dccc;
                border-radius: 18px;
            }
            QLabel#statValue {
                font-size: 24px;
                font-weight: 700;
                color: #1d6b3a;
            }
            QLabel#statLabel {
                color: #7a6e5d;
            }
            QLineEdit {
                background: white;
                border: 1px solid #d9cbb7;
                border-radius: 10px;
                padding: 9px 11px;
            }
            QLineEdit:focus {
                border: 1px solid #1d6b3a;
            }
            QPushButton {
                background: #1d6b3a;
                color: white;
                border: 0;
                border-radius: 12px;
                padding: 11px 14px;
                font-weight: 700;
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

    def make_stat_card(self, label_text: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
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
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 20, 22, 20)
        title = QLabel("Bang dieu khien admin")
        title.setFont(QFont("DejaVu Sans", 18, QFont.Bold))
        title.setStyleSheet("color: #f9f5ee;")
        subtitle = QLabel("Them, sua, xoa sinh vien va tai khoan sinh vien ngay trong giao dien desktop.")
        subtitle.setStyleSheet("color: rgba(249,245,238,0.85);")
        logout_button = QPushButton("Logout")
        logout_button.setObjectName("secondary")
        logout_button.clicked.connect(self.open_login_window)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(logout_button, alignment=Qt.AlignRight)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.total_card = self.make_stat_card("Tong sinh vien")
        self.class_card = self.make_stat_card("So lop")
        self.account_card = self.make_stat_card("Tai khoan SV")
        stats_row.addWidget(self.total_card[0])
        stats_row.addWidget(self.class_card[0])
        stats_row.addWidget(self.account_card[0])

        body = QHBoxLayout()
        body.setSpacing(16)

        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)

        left_title = QLabel("Danh sach sinh vien va tai khoan")
        left_title.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Loc theo ma, ten, lop, hash...")
        self.search_input.textChanged.connect(self.refresh_table)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["#", "Ma SV", "Ho va ten", "Lop", "Username", "Password hash"])
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
        left_layout.addWidget(self.search_input)
        left_layout.addWidget(self.table)
        left_layout.addLayout(action_row)

        right_panel = QFrame()
        right_panel.setObjectName("panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(14)

        right_title = QLabel("Them sinh vien moi")
        right_title.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
        right_note = QLabel("Khi them sinh vien, he thong se tao luon username = ma sinh vien va bam mat khau bang SHA-256.")
        right_note.setWordWrap(True)
        right_note.setStyleSheet("color: #6b6b6b;")

        form = QFormLayout()
        self.student_id_input = QLineEdit()
        self.full_name_input = QLineEdit()
        self.class_name_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        form.addRow("Ma SV", self.student_id_input)
        form.addRow("Ho va ten", self.full_name_input)
        form.addRow("Lop", self.class_name_input)
        form.addRow("Mat khau SV", self.password_input)

        add_button = QPushButton("Them sinh vien + tai khoan")
        add_button.clicked.connect(self.add_student)

        detail_title = QLabel("Thong tin tai khoan dang chon")
        detail_title.setFont(QFont("DejaVu Sans", 13, QFont.Bold))
        self.detail_labels: dict[str, QLabel] = {}
        detail_grid = QGridLayout()
        detail_grid.setHorizontalSpacing(10)
        detail_grid.setVerticalSpacing(8)

        for row_index, key in enumerate(["student_id", "full_name", "class_name", "username", "password_hash"]):
            key_label = QLabel(
                {
                    "student_id": "Ma SV",
                    "full_name": "Ho va ten",
                    "class_name": "Lop",
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

        right_layout.addWidget(right_title)
        right_layout.addWidget(right_note)
        right_layout.addLayout(form)
        right_layout.addWidget(add_button)
        right_layout.addSpacing(10)
        right_layout.addWidget(detail_title)
        right_layout.addLayout(detail_grid)
        right_layout.addStretch(1)

        body.addWidget(left_panel, 4)
        body.addWidget(right_panel, 3)

        root.addWidget(header)
        root.addLayout(stats_row)
        root.addLayout(body)

    def filtered_rows(self) -> list[dict[str, str]]:
        query = self.search_input.text().strip().lower()
        if not query:
            return self.rows

        result = []
        for row in self.rows:
            haystack = " ".join(row.values()).lower()
            if query in haystack:
                result.append(row)
        return result

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
        password = self.password_input.text()

        if not student_id or not full_name or not class_name or not password:
            QMessageBox.warning(self, "Thieu du lieu", "Can nhap ma SV, ho ten, lop va mat khau sinh vien.")
            return

        students = load_students()
        if any(normalize_student_code(student["student_id"]) == student_id for student in students):
            QMessageBox.warning(self, "Trung ma", "Ma sinh vien da ton tai.")
            return

        ok, error = create_student_account(student_id, password)
        if not ok:
            QMessageBox.warning(self, "Khong tao duoc tai khoan", error)
            return

        students.append(
            {
                "student_id": student_id,
                "full_name": full_name,
                "class_name": class_name,
            }
        )
        save_students(students)

        self.student_id_input.clear()
        self.full_name_input.clear()
        self.class_name_input.clear()
        self.password_input.clear()
        self.reload_data()
        QMessageBox.information(self, "Da them", f"Da them sinh vien {student_id} va tao tai khoan SHA-256.")

    def edit_selected_student(self) -> None:
        student = self.selected_student()
        if student is None:
            QMessageBox.information(self, "Chua chon", "Hay chon mot sinh vien trong bang.")
            return

        dialog = EditStudentDialog(student, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.values()
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
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 20, 22, 20)
        title = QLabel("Khong gian sinh vien")
        title.setFont(QFont("DejaVu Sans", 18, QFont.Bold))
        title.setStyleSheet("color: #f9f5ee;")
        subtitle = QLabel("Sinh vien xem duoc danh sach cong khai va chi sua thong tin cua chinh minh.")
        subtitle.setStyleSheet("color: rgba(249,245,238,0.85);")
        logout_button = QPushButton("Logout")
        logout_button.setObjectName("secondary")
        logout_button.clicked.connect(self.open_login_window)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(logout_button, alignment=Qt.AlignRight)

        body = QHBoxLayout()
        body.setSpacing(16)

        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)

        left_title = QLabel("Danh sach sinh vien")
        left_title.setFont(QFont("DejaVu Sans", 14, QFont.Bold))
        left_note = QLabel("Chi hien thi thong tin cong khai: ma SV, ho ten, lop.")
        left_note.setStyleSheet("color: #6b6b6b;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Loc theo ma, ten, lop...")
        self.search_input.textChanged.connect(self.refresh_public_table)

        self.public_table = QTableWidget(0, 4)
        self.public_table.setHorizontalHeaderLabels(["#", "Ma SV", "Ho va ten", "Lop"])
        self.public_table.horizontalHeader().setStretchLastSection(True)
        self.public_table.verticalHeader().setVisible(False)
        self.public_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.public_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.public_table.setAlternatingRowColors(True)

        left_layout.addWidget(left_title)
        left_layout.addWidget(left_note)
        left_layout.addWidget(self.search_input)
        left_layout.addWidget(self.public_table)

        right_panel = QFrame()
        right_panel.setObjectName("panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

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
            ("username", "Username"),
        ]:
            block = QVBoxLayout()
            label_title = QLabel(title_text)
            value_label = QLabel("-")
            value_label.setStyleSheet("font-weight: 700;")
            block.addWidget(label_title)
            block.addWidget(value_label)
            right_layout.addLayout(block)
            self.profile_labels[key] = value_label

        self.edit_profile_button = QPushButton("Sua thong tin ca nhan")
        self.edit_profile_button.clicked.connect(self.edit_own_profile)
        right_layout.addWidget(right_title)
        right_layout.addWidget(right_note)
        right_layout.addWidget(self.edit_profile_button)
        right_layout.addStretch(1)

        body.addWidget(left_panel, 3)
        body.addWidget(right_panel, 2)

        root.addWidget(header)
        root.addLayout(body)

    def filtered_public_rows(self) -> list[dict[str, str]]:
        query = self.search_input.text().strip().lower()
        if not query:
            return self.public_rows

        result = []
        for row in self.public_rows:
            haystack = f"{row['student_id']} {row['full_name']} {row['class_name']}".lower()
            if query in haystack:
                result.append(row)
        return result

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
                break
        save_students(students)
        self.username = values["student_id"]
        self.reload_data()
        QMessageBox.information(self, "Da cap nhat", "Da cap nhat thong tin ca nhan.")


def main() -> None:
    ensure_default_admin()
    app = QApplication(sys.argv)
    app.setApplicationName("Student Manager Desktop")
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
