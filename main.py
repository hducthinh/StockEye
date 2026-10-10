import os
import queue
import signal
import sys


def enable_per_monitor_dpi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


enable_per_monitor_dpi()

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

import chess
from PyQt5.QtCore import QObject, Qt, pyqtSlot
from PyQt5.QtWidgets import QApplication, QMessageBox

from core.capture import BoardCapture
from core.config import load_config, save_config
from core.process_guard import init_process_guard
from core.worker import BoardTrackingWorker, CaptureWorker, EngineWorker
from ui.control_panel import ControlPanelUI
from ui.overlay import OverlayUI


class AppCoordinator(QObject):
    def __init__(self, capture, tracker, engine, overlay, panel):
        super().__init__()
        self.capture = capture
        self.tracker = tracker
        self.engine = engine
        self.overlay = overlay
        self.panel = panel
        self.current_revision = -1
        self.current_fen = None
        self.orientation = capture.orientation
        self.selected_side = tracker.state.selected_side

    @pyqtSlot(int, str)
    def on_board_updated(self, revision: int, fen: str) -> None:
        self.current_revision = revision
        self.current_fen = fen
        self.overlay.clear_moves()

        try:
            board = chess.Board(fen)
        except Exception:
            return

        if not board.is_valid():
            return

        suggest_for = self.panel.config.get("suggest_for", "mine")
        is_my_turn = (
            suggest_for == "both"
            or (suggest_for == "mine" and board.turn == (chess.WHITE if self.orientation == "white" else chess.BLACK))
            or (suggest_for == "white" and board.turn == chess.WHITE)
            or (suggest_for == "black" and board.turn == chess.BLACK)
        )

        if not is_my_turn:
            self.panel.set_status("Đang đợi đối thủ đi...", True)
            return

        self.panel.set_status("Đến lượt bạn — đang tính gợi ý...", True)
        self.engine.submit(revision, fen)

    @pyqtSlot(int, list)
    def on_analysis_ready(self, revision: int, moves: list) -> None:
        if revision != self.current_revision:
            return
        drawing = []
        for item in moves:
            move = item.get("move", "")
            if len(move) < 4:
                continue
            drawing.append((
                self.capture.square_center(move[:2]),
                self.capture.square_center(move[2:4]),
                item.get("score", ""),
            ))
        self.overlay.update_moves(drawing)

    @pyqtSlot(dict)
    def on_settings_changed(self, config: dict) -> None:
        geometry_changed = (
            config["board_orientation"] != self.orientation
            or config["selected_side"] != self.selected_side
        )
        if geometry_changed:
            self.orientation = config["board_orientation"]
            self.selected_side = config["selected_side"]
            self.tracker.update_side_and_orientation(self.selected_side, self.orientation)
        self.engine.update_settings(
            config["threads"], config["multipv"], config["engine_time_ms"]
        )
        if geometry_changed:
            self.overlay.clear_moves()
        elif self.current_fen and self.current_revision != -1:
            self.on_board_updated(self.current_revision, self.current_fen)

    @pyqtSlot(str)
    def on_orientation_detected(self, side: str) -> None:
        self.orientation = side
        self.selected_side = side
        self.panel.apply_detected_side(side)


def main() -> int:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    init_process_guard()
    config = save_config(load_config())
    app = QApplication(sys.argv)
    app.setApplicationName("StockEye")

    if not config.get("bbox"):
        QMessageBox.critical(
            None, "StockEye",
            "Chưa có vùng bàn cờ. Hãy chạy auto_setup.py trước.",
        )
        return 1

    capture = BoardCapture(config["bbox"], config["board_orientation"])
    frame_queue = queue.Queue(maxsize=1)
    capture_worker = CaptureWorker(capture, frame_queue, config["capture_fps"])
    tracker = BoardTrackingWorker(capture, frame_queue, config)
    engine = EngineWorker(config)

    overlay = OverlayUI()
    overlay.show()
    if not overlay.enable_capture_exclusion():
        QMessageBox.critical(
            None, "StockEye",
            "Windows không cho phép loại overlay khỏi ảnh chụp. Tracking đã dừng để tránh tự nhận diện mũi tên.",
        )
        overlay.close()
        return 2

    panel = ControlPanelUI(config)
    panel.show()
    coordinator = AppCoordinator(capture, tracker, engine, overlay, panel)

    tracker.board_updated.connect(coordinator.on_board_updated, Qt.QueuedConnection)
    tracker.orientation_detected.connect(coordinator.on_orientation_detected, Qt.QueuedConnection)
    tracker.status_changed.connect(panel.set_status, Qt.QueuedConnection)
    tracker.clear_overlay.connect(overlay.clear_moves, Qt.QueuedConnection)
    engine.analysis_ready.connect(coordinator.on_analysis_ready, Qt.QueuedConnection)
    engine.engine_error.connect(lambda message: panel.set_status("Lỗi Stockfish: " + message, False))
    engine.engine_error.connect(overlay.clear_moves)
    capture_worker.capture_error.connect(lambda message: panel.set_status("Lỗi capture: " + message, False))
    capture_worker.capture_error.connect(overlay.clear_moves)

    panel.resync_requested.connect(tracker.request_resync)
    panel.pause_changed.connect(tracker.set_paused)
    panel.settings_changed.connect(coordinator.on_settings_changed)
    panel.exit_requested.connect(app.quit)

    engine.start()
    tracker.start()
    capture_worker.start()
    exit_code = app.exec_()

    capture_worker.stop()
    tracker.stop()
    engine.stop()
    capture_worker.wait(1500)
    tracker.wait(1500)
    engine.wait(3000)
    overlay.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
