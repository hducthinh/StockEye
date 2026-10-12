from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

import chess
from PyQt5.QtCore import QThread, pyqtSignal

from core.capture import BoardCapture, TemplateRecognizer
from core.engine_logic import ChessEngine
from core.tracker import BoardState, LegalMoveResolver, square_crop


@dataclass(frozen=True)
class FramePacket:
    frame_id: int
    captured_at_ns: int
    image: object


@dataclass(frozen=True)
class AnalysisRequest:
    revision: int
    fen: str


def put_latest(target: queue.Queue, item) -> None:
    try:
        target.put_nowait(item)
    except queue.Full:
        try:
            target.get_nowait()
        except queue.Empty:
            pass
        target.put_nowait(item)


class CaptureWorker(QThread):
    capture_error = pyqtSignal(str)
    capture_latency = pyqtSignal(float)

    def __init__(self, capture: BoardCapture, output_queue: queue.Queue, fps: int = 60):
        super().__init__()
        self.capture = capture
        self.output_queue = output_queue
        self.fps = max(10, int(fps))
        self.running = True

    def run(self) -> None:
        frame_id = 0
        interval = 1.0 / self.fps
        try:
            self.capture.open()
            while self.running:
                started = time.perf_counter()
                image = self.capture.get_board_image()
                captured_at = time.perf_counter_ns()
                put_latest(self.output_queue, FramePacket(frame_id, captured_at, image))
                frame_id += 1
                elapsed = time.perf_counter() - started
                self.capture_latency.emit(elapsed * 1000.0)
                if elapsed < interval:
                    self.msleep(max(1, round((interval - elapsed) * 1000)))
        except Exception as exc:
            self.capture_error.emit(str(exc))
        finally:
            self.capture.close()

    def stop(self) -> None:
        self.running = False


class BoardTrackingWorker(QThread):
    board_updated = pyqtSignal(int, str)
    orientation_detected = pyqtSignal(str)
    status_changed = pyqtSignal(str, bool)
    tracking_latency = pyqtSignal(float)
    clear_overlay = pyqtSignal()

    def __init__(self, capture: BoardCapture, input_queue: queue.Queue, config: dict):
        super().__init__()
        self.capture = capture
        self.input_queue = input_queue
        self.config = dict(config)
        self.recognizer = TemplateRecognizer(
            threshold=float(config["recognition_threshold"]),
            ambiguity_margin=float(config["recognition_margin"]),
            preset=config.get("active_preset", "standard"),
        )
        self.state = BoardState(config["selected_side"])
        self.resolver = LegalMoveResolver()
        self.running = True
        self.paused = False
        self._resync_requested = threading.Event()
        self._resync_requested.set()
        self._state_lock = threading.RLock()
        self._reference_image = None
        self._last_auto_poll = 0.0
        self._auto_poll_interval = 0.5

    @property
    def revision(self) -> int:
        with self._state_lock:
            return self.state.revision

    def request_resync(self) -> None:
        self._resync_requested.set()
        self.status_changed.emit("Đang chờ frame để đồng bộ...", False)

    def set_paused(self, paused: bool) -> None:
        self.paused = bool(paused)
        if paused:
            self.clear_overlay.emit()
            self.status_changed.emit("Đã tạm dừng", False)
        else:
            self._resync_requested.set()
            self.status_changed.emit("Tiếp tục — đang đồng bộ lại", False)

    def update_preset(self, preset: str) -> None:
        with self._state_lock:
            self.recognizer.set_preset(preset)
            self._reference_image = None
            self._resync_requested.set()

    def update_side_and_orientation(self, selected_side: str, orientation: str) -> None:
        with self._state_lock:
            self.state.selected_side = selected_side
            self.capture.orientation = orientation
        self._reference_image = None
        self._resync_requested.set()

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        while self.running:
            try:
                packet: FramePacket = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if self.paused:
                continue
            started = time.perf_counter()
            if self._resync_requested.is_set():
                self._perform_resync(packet)
            elif self.state.synced and self._reference_image is not None:
                self._track_frame(packet)
            else:
                now = time.perf_counter()
                if now - self._last_auto_poll >= self._auto_poll_interval:
                    self._last_auto_poll = now
                    self._perform_resync(packet, is_auto_poll=True)
            self.tracking_latency.emit((time.perf_counter() - started) * 1000.0)

    def _perform_resync(self, packet: FramePacket, is_auto_poll: bool = False) -> None:
        self._resync_requested.clear()
        if not is_auto_poll:
            self.status_changed.emit("Đang nhận diện 64 ô...", False)
        try:
            recognition = self.recognizer.recognize_board_auto(packet.image)
            with self._state_lock:
                if recognition.orientation in {"white", "black"}:
                    self.capture.orientation = recognition.orientation
                    self.state.selected_side = recognition.orientation
                ok, message = self.state.resync(recognition)
                if ok:
                    self._reference_image = packet.image.copy()
                    revision = self.state.revision
                    fen = self.state.board.fen()
                else:
                    self.state.synced = False
                    revision = None
                    fen = None
        except Exception as exc:
            ok = False
            message = f"Lỗi nhận diện: {exc}"
            revision = None
            fen = None
            recognition = None

        if ok:
            self.orientation_detected.emit(recognition.orientation)
            self.status_changed.emit(message, True)
            self.board_updated.emit(revision, fen)
        else:
            if recognition and recognition.orientation in {"white", "black"}:
                self.orientation_detected.emit(recognition.orientation)
            self.clear_overlay.emit()
            if is_auto_poll:
                self.status_changed.emit("Đang chờ ván mới...", False)
            else:
                self.status_changed.emit("Resync thất bại: " + message, False)

    def _track_frame(self, packet: FramePacket) -> None:
        try:
            changed = self.capture.changed_squares(
                self._reference_image,
                packet.image,
                int(self.config["pixel_diff_threshold"]),
                float(self.config["square_change_threshold"]),
            )
            if not changed:
                return
            if len(changed) == 1:
                return
            if len(changed) > 4:
                self._schedule_auto_resync(len(changed))
                return

            destination = None
            with self._state_lock:
                board = self.state.board.copy(stack=True)
            promotion_targets = {
                move.to_square for move in board.legal_moves
                if move.promotion and {
                    chess.square_name(move.from_square), chess.square_name(move.to_square)
                }.issubset(set(changed))
            }
            if len(promotion_targets) == 1:
                target_name = chess.square_name(next(iter(promotion_targets)))
                destination = square_crop(packet.image, target_name, self.capture.orientation)

            resolution = self.resolver.resolve(board, changed, destination, self.recognizer)
            if resolution.move is None:
                self._mark_desynced(resolution.reason or "Không xác định được nước đi")
                return
            with self._state_lock:
                revision = self.state.push(resolution.move)
                fen = self.state.board.fen()
                self._reference_image = packet.image.copy()
            self.status_changed.emit(f"Đã nhận nước {resolution.move.uci()}", True)
            self.board_updated.emit(revision, fen)
        except Exception as exc:
            self._mark_desynced(f"Lỗi tracking: {exc}")

    def _mark_desynced(self, reason: str) -> None:
        with self._state_lock:
            self.state.synced = False
        self.clear_overlay.emit()
        self.status_changed.emit(reason + " — đang tự động đồng bộ lại...", False)

    def _schedule_auto_resync(self, changed_count: int) -> None:
        with self._state_lock:
            self.state.synced = False
        self.clear_overlay.emit()
        self.status_changed.emit(
            f"Phát hiện {changed_count} ô thay đổi — tự động Resync...", False
        )
        # Resync ở frame kế tiếp để không dùng lại frame đã kích hoạt thay đổi.
        self._resync_requested.set()
class EngineWorker(QThread):
    analysis_ready = pyqtSignal(int, list)
    engine_error = pyqtSignal(str)
    engine_latency = pyqtSignal(float)

    def __init__(self, config: dict, engine_factory=ChessEngine):
        super().__init__()
        self.engine_factory = engine_factory
        self.requests: queue.Queue = queue.Queue(maxsize=1)
        self.running = True
        self._lock = threading.Lock()
        self._latest_revision = -1
        self._threads = int(config["threads"])
        self._multipv = int(config["multipv"])
        self._time_ms = int(config["engine_time_ms"])

    def submit(self, revision: int, fen: str) -> None:
        with self._lock:
            self._latest_revision = max(self._latest_revision, revision)
        put_latest(self.requests, AnalysisRequest(revision, fen))

    def update_settings(self, threads: int, multipv: int, time_ms: int) -> None:
        with self._lock:
            self._threads = max(1, int(threads))
            self._multipv = max(1, min(4, int(multipv)))
            self._time_ms = max(10, min(50, int(time_ms)))

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        engine = None
        configured_threads = None
        try:
            while self.running:
                try:
                    request: AnalysisRequest = self.requests.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    with self._lock:
                        threads, multipv, time_ms = self._threads, self._multipv, self._time_ms
                    if engine is None:
                        engine = self.engine_factory(threads=threads)
                        configured_threads = threads
                    elif configured_threads != threads:
                        engine.configure(threads)
                        configured_threads = threads
                    started = time.perf_counter()
                    moves = engine.analyse(request.fen, multipv=multipv, time_ms=time_ms)
                    elapsed = (time.perf_counter() - started) * 1000.0
                    self.engine_latency.emit(elapsed)
                    with self._lock:
                        is_current = request.revision == self._latest_revision
                    if is_current:
                        self.analysis_ready.emit(request.revision, moves)
                except Exception as exc:
                    if engine:
                        try:
                            engine.close()
                        except Exception:
                            pass
                        engine = None
                    self.engine_error.emit(str(exc))
                    time.sleep(0.3)
        finally:
            if engine:
                engine.close()
