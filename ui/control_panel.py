from __future__ import annotations

import sys
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton,
    QShortcut, QSpinBox, QVBoxLayout, QWidget,
)

from core.config import save_config


class ControlPanelUI(QWidget):
    resync_requested = pyqtSignal()
    pause_changed = pyqtSignal(bool)
    settings_changed = pyqtSignal(dict)
    exit_requested = pyqtSignal()

    def __init__(self, config: dict):
        super().__init__()
        self.config = dict(config)
        self.paused = False
        self.setWindowTitle("StockEye Tracker")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        self.resize(340, 325)

        # Đặt cửa sổ ở góc trên bên phải màn hình khi khởi động
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            x = avail.x() + avail.width() - self.width() - 20
            y = avail.y() + 20
            self.move(x, y)
        else:
            self.move(1200, 20)

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Đang khởi tạo...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 8px; background: #37474f; color: white;")
        layout.addWidget(self.status_label)

        form = QFormLayout()
        self.board_preset = QComboBox()
        self.board_preset.addItem("[5] Bàn cờ thông thường", "standard")
        self.board_preset.addItem("[6] Puzzle Rush", "puzzle")
        active_preset = config.get("active_preset", "standard")
        self.board_preset.setCurrentIndex(0 if active_preset == "standard" else 1)
        form.addRow("Chế độ chơi:", self.board_preset)

        preset_btn_layout = QHBoxLayout()
        self.btn_preset_standard = QPushButton("[5] Bàn thường")
        self.btn_preset_puzzle = QPushButton("[6] Puzzle Rush")
        preset_btn_layout.addWidget(self.btn_preset_standard)
        preset_btn_layout.addWidget(self.btn_preset_puzzle)
        form.addRow("Phím nhanh:", preset_btn_layout)
        self._update_preset_button_styles(active_preset)

        self.orientation = QComboBox()
        self.orientation.addItem("Trắng ở dưới", "white")
        self.orientation.addItem("Đen ở dưới", "black")
        self.orientation.setCurrentIndex(0 if config["board_orientation"] == "white" else 1)
        form.addRow("Hướng bàn:", self.orientation)

        self.selected_side = QComboBox()
        self.selected_side.addItem("Lượt Trắng", "white")
        self.selected_side.addItem("Lượt Đen", "black")
        self.selected_side.setCurrentIndex(0 if config["selected_side"] == "white" else 1)
        form.addRow("Lượt khi Resync:", self.selected_side)

        self.time_ms = QSpinBox()
        self.time_ms.setRange(10, 50)
        self.time_ms.setValue(config["engine_time_ms"])
        self.time_ms.setSuffix(" ms")
        form.addRow("Stockfish:", self.time_ms)

        self.multipv = QSpinBox()
        self.multipv.setRange(1, 4)
        self.multipv.setValue(config["multipv"])
        form.addRow("Số gợi ý:", self.multipv)

        self.suggest_for = QComboBox()
        self.suggest_for.addItem("Chỉ bên tôi (quân ở dưới)", "mine")
        self.suggest_for.addItem("Cả hai bên", "both")
        self.suggest_for.addItem("Chỉ quân Trắng", "white")
        self.suggest_for.addItem("Chỉ quân Đen", "black")
        suggest_val = config.get("suggest_for", "mine")
        self.suggest_for.setCurrentIndex(max(0, self.suggest_for.findData(suggest_val)))
        form.addRow("Gợi ý cho:", self.suggest_for)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.resync_button = QPushButton("RESYNC [3]")
        self.resync_button.setStyleSheet("background:#2196f3;color:white;font-weight:bold;padding:9px;")
        self.pause_button = QPushButton("TẠM DỪNG [4]")
        self.pause_button.setStyleSheet("padding:9px;")
        buttons.addWidget(self.resync_button)
        buttons.addWidget(self.pause_button)
        layout.addLayout(buttons)

        self.hide_button = QPushButton("ẨN GIAO DIỆN [7] (GỢI Ý VẪN HOẠT ĐỘNG)")
        self.hide_button.setStyleSheet(
            "background:#37474f;color:#eceff1;font-weight:bold;padding:6px;font-size:11px;border-radius:3px;"
        )
        layout.addWidget(self.hide_button)

        self.resync_button.clicked.connect(self._resync)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.hide_button.clicked.connect(self.toggle_visibility)
        self.btn_preset_standard.clicked.connect(lambda: self.switch_preset("standard"))
        self.btn_preset_puzzle.clicked.connect(lambda: self.switch_preset("puzzle"))
        self.board_preset.currentIndexChanged.connect(self._on_preset_changed)
        self.orientation.currentIndexChanged.connect(self._save_and_emit)
        self.selected_side.currentIndexChanged.connect(self._save_and_emit)
        self.time_ms.valueChanged.connect(self._save_and_emit)
        self.multipv.valueChanged.connect(self._save_and_emit)
        self.suggest_for.currentIndexChanged.connect(self._save_and_emit)

        # Hotkeys khi Control Panel có focus
        self.shortcut_3 = QShortcut(QKeySequence("3"), self)
        self.shortcut_3.activated.connect(self._resync)

        self.shortcut_4 = QShortcut(QKeySequence("4"), self)
        self.shortcut_4.activated.connect(self._toggle_pause)

        self.shortcut_5 = QShortcut(QKeySequence("5"), self)
        self.shortcut_5.activated.connect(lambda: self.switch_preset("standard"))

        self.shortcut_6 = QShortcut(QKeySequence("6"), self)
        self.shortcut_6.activated.connect(lambda: self.switch_preset("puzzle"))

        self.shortcut_7 = QShortcut(QKeySequence("7"), self)
        self.shortcut_7.activated.connect(self.toggle_visibility)

    def toggle_visibility(self) -> None:
        """Ẩn/hiện toàn bộ giao diện tool và cửa sổ console, trong khi gợi ý nước đi vẫn tiếp tục hoạt động."""
        if self.isVisible():
            self.hide()
            self._set_console_visible(False)
        else:
            self.show()
            self.raise_()
            self.activateWindow()
            self._set_console_visible(True)

    @staticmethod
    def _set_console_visible(visible: bool) -> None:
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 5 if visible else 0)
            except Exception:
                pass

    def trigger_resync(self) -> None:
        self.set_status("Đang đồng bộ lại toàn bộ bàn cờ (Phím 3)...", True)
        self._resync()

    def toggle_pause(self) -> None:
        self._toggle_pause()

    def switch_preset(self, preset_key: str) -> None:
        if preset_key not in {"standard", "puzzle"}:
            return
        idx = 0 if preset_key == "standard" else 1
        if self.board_preset.currentIndex() != idx:
            self.board_preset.setCurrentIndex(idx)
        else:
            self._on_preset_changed()

    def _update_preset_button_styles(self, active_key: str) -> None:
        active_style = "padding: 6px; font-weight: bold; background: #1976d2; color: white; border-radius: 3px;"
        inactive_style = "padding: 6px; background: #455a64; color: #cfd8dc; border-radius: 3px;"
        if active_key == "standard":
            self.btn_preset_standard.setStyleSheet(active_style)
            self.btn_preset_puzzle.setStyleSheet(inactive_style)
        else:
            self.btn_preset_standard.setStyleSheet(inactive_style)
            self.btn_preset_puzzle.setStyleSheet(active_style)

    def _current_settings(self) -> dict:
        preset_key = self.board_preset.currentData()
        self.config["active_preset"] = preset_key
        presets = self.config.get("board_presets", {})
        if preset_key in presets and presets[preset_key].get("bbox"):
            self.config["bbox"] = presets[preset_key]["bbox"]
        self.config["board_orientation"] = self.orientation.currentData()
        self.config["selected_side"] = self.selected_side.currentData()
        self.config["engine_time_ms"] = self.time_ms.value()
        self.config["multipv"] = self.multipv.value()
        self.config["suggest_for"] = self.suggest_for.currentData()
        return self.config

    def _on_preset_changed(self) -> None:
        preset_key = self.board_preset.currentData()
        presets = self.config.get("board_presets", {})
        preset_bbox = presets.get(preset_key, {}).get("bbox")
        preset_name = "Puzzle Rush (Phím 6)" if preset_key == "puzzle" else "Bàn cờ thông thường (Phím 5)"
        self._update_preset_button_styles(preset_key)
        if preset_bbox is None:
            self.set_status(f"'{preset_name}' chưa có tọa độ! Hãy chạy: py .\\auto_setup.py", False)
        else:
            self.set_status(f"Đã chuyển sang: {preset_name} — đang đồng bộ...", True)
        self._save_and_emit()
        self.resync_requested.emit()

    def _save_and_emit(self) -> None:
        self.config = save_config(self._current_settings())
        self.settings_changed.emit(dict(self.config))

    def _resync(self) -> None:
        self._save_and_emit()
        self.resync_requested.emit()

    def apply_detected_side(self, side: str) -> None:
        """Reflect the orientation detected by the resync worker without causing another resync."""
        if side not in {"white", "black"}:
            return
        self.orientation.blockSignals(True)
        self.selected_side.blockSignals(True)
        try:
            self.orientation.setCurrentIndex(self.orientation.findData(side))
            self.selected_side.setCurrentIndex(self.selected_side.findData(side))
        finally:
            self.orientation.blockSignals(False)
            self.selected_side.blockSignals(False)
        self.config["board_orientation"] = side
        self.config["selected_side"] = side
        self.config = save_config(self.config)

    def _toggle_pause(self) -> None:
        self.paused = not self.paused
        self.pause_button.setText("TIẾP TỤC [4]" if self.paused else "TẠM DỪNG [4]")
        if self.paused:
            self.set_status("Đã tạm dừng tracking (Phím 4). Nhấn [4] để tiếp tục.", False)
        else:
            self.set_status("Đang tiếp tục tracking (Phím 4)...", True)
        self.pause_changed.emit(self.paused)

    def set_status(self, message: str, healthy: bool) -> None:
        color = "#2e7d32" if healthy else "#b71c1c"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"padding:8px;background:{color};color:white;")

    def closeEvent(self, event) -> None:
        self._set_console_visible(True)
        self.exit_requested.emit()
        event.accept()
