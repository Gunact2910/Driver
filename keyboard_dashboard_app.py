#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROC_FILE = "/proc/kb_driver"
STATUS_SCRIPT = os.path.join(BASE_DIR, "keyboard_status.sh")
BIND_SCRIPT = os.path.join(BASE_DIR, "bind_kb_driver.sh")
UNBIND_SCRIPT = os.path.join(BASE_DIR, "unbind_kb_driver.sh")


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
            if key == "logging_enabled":
                result[key] = value == "1"
            elif key in {"active_devices", "total_press_events", "total_release_events", "history_entries"}:
                result[key] = int(value)
        elif section == "devices":
            parts = (line.split("|") + ["", "", ""])[:3]
            if parts[0]:
                result["devices"].append(
                    {
                        "interface": parts[0],
                        "vendor_id": parts[1],
                        "product_id": parts[2],
                    }
                )
        elif section == "history":
            parts = (line.split("|") + ["", "", "", "", "", ""])[:6]
            if parts[0]:
                result["history"].append(
                    {
                        "seq": int(parts[0]),
                        "timestamp": int(parts[1]),
                        "interface": parts[2],
                        "action": parts[3],
                        "key": parts[4],
                        "usage": parts[5],
                    }
                )
        elif section == "key_stats":
            parts = (line.split("|") + ["", "", "0", "0"])[:4]
            if parts[0]:
                result["key_stats"].append(
                    {
                        "usage": parts[0],
                        "name": parts[1],
                        "pressed": int(parts[2]),
                        "released": int(parts[3]),
                    }
                )

    result["key_stats"].sort(key=lambda item: (-item["pressed"], item["usage"]))
    return result


def parse_status_output(raw_output: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for raw_line in raw_output.splitlines():
        line = raw_line.strip()
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
    return devices


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

    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if not output:
        output = f"exit code {completed.returncode}"
    return completed.returncode == 0, output


def write_proc_command(command: str) -> tuple[bool, str]:
    try:
        with open(PROC_FILE, "w", encoding="utf-8") as handle:
            handle.write(command)
    except OSError as exc:
        return False, str(exc)
    return True, f"Sent '{command}' to {PROC_FILE}"


class StatCard(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("statTitle")
        self.value_label = QLabel("-")
        self.value_label.setObjectName("statValue")

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class KeyboardDashboardWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bang Dieu Khien Driver Ban Phim USB")
        self.resize(1180, 820)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(10)

        title = QLabel("Bang Dieu Khien Driver Ban Phim USB")
        title.setObjectName("heroTitle")
        subtitle = QLabel("Ung dung desktop cho bai 2: doc /proc/kb_driver, hien thi su kien phim va dieu khien bind/unbind.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("heroSubtitle")

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.bind_button = QPushButton("Gan Tat Ca")
        self.unbind_button = QPushButton("Go Gan Tat Ca")
        self.logging_on_button = QPushButton("Bat Ghi Log")
        self.logging_off_button = QPushButton("Tat Ghi Log")
        self.clear_button = QPushButton("Xoa Lich Su")
        self.reset_button = QPushButton("Dat Lai Thong Ke")
        self.refresh_button = QPushButton("Lam Moi")

        for button in (
            self.bind_button,
            self.unbind_button,
            self.logging_on_button,
            self.logging_off_button,
            self.clear_button,
            self.reset_button,
            self.refresh_button,
        ):
            toolbar.addWidget(button)

        self.message_label = QLabel("Dang cho lan cap nhat dau tien...")
        self.message_label.setObjectName("messageBar")

        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(toolbar)
        hero_layout.addWidget(self.message_label)
        outer.addWidget(hero)

        stats_layout = QGridLayout()
        stats_layout.setHorizontalSpacing(12)
        stats_layout.setVerticalSpacing(12)
        self.module_card = StatCard("Trang Thai Module")
        self.device_card = StatCard("Thiet Bi Dang Hoat Dong")
        self.press_card = StatCard("So Lan Nhan Phim")
        self.release_card = StatCard("So Lan Nha Phim")
        stats_layout.addWidget(self.module_card, 0, 0)
        stats_layout.addWidget(self.device_card, 0, 1)
        stats_layout.addWidget(self.press_card, 0, 2)
        stats_layout.addWidget(self.release_card, 0, 3)
        outer.addLayout(stats_layout)

        panels = QGridLayout()
        panels.setHorizontalSpacing(14)
        panels.setVerticalSpacing(14)

        state_box = QGroupBox("Trang Thai Driver")
        state_layout = QVBoxLayout(state_box)
        self.state_logging = QLabel("-")
        self.state_history = QLabel("0")
        self.state_proc = QLabel(PROC_FILE)
        for label in (self.state_logging, self.state_history, self.state_proc):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        state_layout.addWidget(QLabel("Ghi log"))
        state_layout.addWidget(self.state_logging)
        state_layout.addWidget(QLabel("So muc lich su"))
        state_layout.addWidget(self.state_history)
        state_layout.addWidget(QLabel("Tep proc"))
        state_layout.addWidget(self.state_proc)
        state_layout.addStretch(1)

        devices_box = QGroupBox("Giao Dien Ban Phim USB")
        devices_layout = QVBoxLayout(devices_box)
        self.devices_table = QTableWidget(0, 4)
        self.devices_table.setHorizontalHeaderLabels(["Giao Dien", "Thiet Bi", "VID:PID", "Driver"])
        self.devices_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.devices_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.devices_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.devices_table.setSelectionMode(QTableWidget.SingleSelection)
        devices_layout.addWidget(self.devices_table)

        history_box = QGroupBox("Su Kien Gan Day")
        history_layout = QVBoxLayout(history_box)
        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels(["STT", "Thoi Gian", "Giao Dien", "Hanh Dong", "Phim", "Ma Usage"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SingleSelection)
        history_layout.addWidget(self.history_table)

        stats_box = QGroupBox("Thong Ke Phim")
        key_stats_layout = QVBoxLayout(stats_box)
        self.key_stats_table = QTableWidget(0, 4)
        self.key_stats_table.setHorizontalHeaderLabels(["Ma Usage", "Ten Phim", "So Lan Nhan", "So Lan Nha"])
        self.key_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.key_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.key_stats_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.key_stats_table.setSelectionMode(QTableWidget.SingleSelection)
        key_stats_layout.addWidget(self.key_stats_table)

        panels.addWidget(state_box, 0, 0)
        panels.addWidget(devices_box, 0, 1)
        panels.addWidget(history_box, 1, 0, 1, 2)
        panels.addWidget(stats_box, 2, 0, 1, 2)
        outer.addLayout(panels)

        self.bind_button.clicked.connect(lambda: self.run_action("bind_all"))
        self.unbind_button.clicked.connect(lambda: self.run_action("unbind_all"))
        self.logging_on_button.clicked.connect(lambda: self.run_action("logging_on"))
        self.logging_off_button.clicked.connect(lambda: self.run_action("logging_off"))
        self.clear_button.clicked.connect(lambda: self.run_action("clear_history"))
        self.reset_button.clicked.connect(lambda: self.run_action("reset_stats"))
        self.refresh_button.clicked.connect(self.refresh_dashboard)

        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.refresh_dashboard)
        self.timer.start()

        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4efe5;
                color: #1e1e1e;
                font-family: "DejaVu Sans";
                font-size: 14px;
            }
            QFrame#hero, QFrame#statCard, QGroupBox {
                background: #fffaf3;
                border: 1px solid #e2d5c3;
                border-radius: 16px;
            }
            QLabel#heroTitle {
                font-size: 28px;
                font-weight: 700;
                color: #173828;
            }
            QLabel#heroSubtitle {
                color: #6a6a6a;
            }
            QLabel#messageBar {
                background: #dceee3;
                border: 1px solid #c5dfd0;
                border-radius: 12px;
                padding: 10px 12px;
                color: #164a37;
                font-weight: 600;
            }
            QLabel#statTitle {
                color: #6c6c6c;
            }
            QLabel#statValue {
                font-size: 24px;
                font-weight: 700;
                color: #173828;
            }
            QPushButton {
                background: #1d6b3a;
                color: white;
                border: 0;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #14532d;
            }
            QPushButton:pressed {
                background: #103f22;
            }
            QGroupBox {
                margin-top: 8px;
                padding-top: 14px;
                font-weight: 700;
            }
            QTableWidget {
                background: white;
                border: 1px solid #e6d9c8;
                border-radius: 10px;
                gridline-color: #efe6db;
            }
            QHeaderView::section {
                background: #efe5d8;
                border: 0;
                padding: 8px;
                font-weight: 700;
            }
            """
        )

        self.refresh_dashboard()

    def set_message(self, text: str, is_error: bool = False) -> None:
        self.message_label.setText(text)
        if is_error:
            self.message_label.setStyleSheet(
                "background: #f8e1d8; border: 1px solid #efc7b9; border-radius: 12px; padding: 10px 12px; color: #7a2415; font-weight: 600;"
            )
        else:
            self.message_label.setStyleSheet(
                "background: #dceee3; border: 1px solid #c5dfd0; border-radius: 12px; padding: 10px 12px; color: #164a37; font-weight: 600;"
            )

    def format_timestamp(self, value: int) -> str:
        try:
            return datetime.fromtimestamp(value / 1000.0).strftime("%H:%M:%S.%f")[:-3]
        except (OverflowError, OSError, ValueError):
            return str(value)

    def populate_table(self, table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                table.setItem(row_index, column_index, item)

    def collect_status_devices(self) -> tuple[list[dict[str, str]], str]:
        ok, output = run_command([STATUS_SCRIPT])
        if not ok:
            return [], output
        return parse_status_output(output), "Dashboard da duoc cap nhat"

    def translate_action(self, action: str) -> str:
        if action == "pressed":
            return "Nhan"
        if action == "released":
            return "Nha"
        return action

    def refresh_dashboard(self) -> None:
        proc_state = read_proc_state()
        devices, status_message = self.collect_status_devices()
        module_loaded = os.path.isdir("/sys/bus/usb/drivers/kb_driver")

        self.module_card.set_value("Da nap" if module_loaded else "Chua nap")
        self.device_card.set_value(str(proc_state["active_devices"]))
        self.press_card.set_value(str(proc_state["total_press_events"]))
        self.release_card.set_value(str(proc_state["total_release_events"]))

        self.state_logging.setText("Bat" if proc_state["logging_enabled"] else "Tat")
        self.state_history.setText(str(proc_state["history_entries"]))

        device_rows = [
            [
                device.get("interface", ""),
                device.get("device", ""),
                device.get("vendor_product", ""),
                device.get("driver", ""),
            ]
            for device in devices
        ]
        self.populate_table(self.devices_table, device_rows)

        history_rows = [
            [
                str(event["seq"]),
                self.format_timestamp(event["timestamp"]),
                event["interface"],
                self.translate_action(event["action"]),
                event["key"],
                event["usage"],
            ]
            for event in reversed(proc_state["history"])
        ]
        self.populate_table(self.history_table, history_rows)

        key_stat_rows = [
            [
                stat["usage"],
                stat["name"],
                str(stat["pressed"]),
                str(stat["released"]),
            ]
            for stat in proc_state["key_stats"]
        ]
        self.populate_table(self.key_stats_table, key_stat_rows)

        if module_loaded:
            self.set_message(status_message, False)
        else:
            self.set_message("kb_driver chua duoc nap hoac chua bind vao thiet bi.", True)

    def run_action(self, action: str) -> None:
        actions = {
            "bind_all": lambda: run_command([BIND_SCRIPT]),
            "unbind_all": lambda: run_command([UNBIND_SCRIPT]),
            "logging_on": lambda: write_proc_command("logging=1"),
            "logging_off": lambda: write_proc_command("logging=0"),
            "clear_history": lambda: write_proc_command("clear_history"),
            "reset_stats": lambda: write_proc_command("reset_stats"),
        }

        ok, message = actions[action]()
        self.refresh_dashboard()
        if ok:
            self.set_message(message, False)
        else:
            self.set_message(message, True)
            QMessageBox.warning(self, "Thao tac that bai", message)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Bang Dieu Khien Driver Ban Phim USB")
    window = KeyboardDashboardWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
