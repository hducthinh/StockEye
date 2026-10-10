from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
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
        self.resize(340, 260)

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Đang khởi tạo...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 8px; background: #37474f; color: white;")
        layout.addWidget(self.status_label)

        form = QFormLayout()
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
        self.resync_button = QPushButton("RESYNC")
        self.resync_button.setStyleSheet("background:#2196f3;color:white;font-weight:bold;padding:9px;")
        self.pause_button = QPushButton("TẠM DỪNG")
        self.pause_button.setStyleSheet("padding:9px;")
        buttons.addWidget(self.resync_button)
        buttons.addWidget(self.pause_button)
        layout.addLayout(buttons)

        self.resync_button.clicked.connect(self._resync)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.orientation.currentIndexChanged.connect(self._save_and_emit)
        self.selected_side.currentIndexChanged.connect(self._save_and_emit)
        self.time_ms.valueChanged.connect(self._save_and_emit)
        self.multipv.valueChanged.connect(self._save_and_emit)
        self.suggest_for.currentIndexChanged.connect(self._save_and_emit)

    def _current_settings(self) -> dict:
        self.config["board_orientation"] = self.orientation.currentData()
        self.config["selected_side"] = self.selected_side.currentData()
        self.config["engine_time_ms"] = self.time_ms.value()
        self.config["multipv"] = self.multipv.value()
        self.config["suggest_for"] = self.suggest_for.currentData()
        return self.config

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
        self.pause_button.setText("TIẾP TỤC" if self.paused else "TẠM DỪNG")
        self.pause_changed.emit(self.paused)

    def set_status(self, message: str, healthy: bool) -> None:
        color = "#2e7d32" if healthy else "#b71c1c"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"padding:8px;background:{color};color:white;")

    def closeEvent(self, event) -> None:
        self.exit_requested.emit()
        event.accept()
