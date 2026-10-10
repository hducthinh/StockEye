import time
import queue

from PyQt5.QtCore import QCoreApplication

from core.capture import BoardCapture
from core.worker import BoardTrackingWorker, EngineWorker


class FakeEngine:
    def __init__(self, threads=1):
        self.threads = threads

    def configure(self, threads):
        self.threads = threads

    def analyse(self, fen, multipv=3, time_ms=20):
        time.sleep(0.04)
        return [{"move": "e2e4", "score": "+0.10", "fen": fen}]

    def close(self):
        pass


def test_stale_engine_result_is_discarded():
    app = QCoreApplication.instance() or QCoreApplication([])
    config = {"threads": 1, "multipv": 3, "engine_time_ms": 20}
    worker = EngineWorker(config, engine_factory=FakeEngine)
    results = []
    worker.analysis_ready.connect(lambda revision, moves: results.append(revision))
    worker.start()
    worker.submit(1, "first")
    time.sleep(0.01)
    worker.submit(2, "second")
    deadline = time.time() + 1.0
    while time.time() < deadline and not results:
        app.processEvents()
        time.sleep(0.01)
    worker.stop()
    worker.wait(1000)
    app.processEvents()
    assert results == [2]


def test_more_than_four_changes_schedule_automatic_resync():
    config = {
        "selected_side": "white",
        "recognition_threshold": 0.62,
        "recognition_margin": 0.01,
        "pixel_diff_threshold": 35,
        "square_change_threshold": 0.08,
    }
    capture = BoardCapture({"left": 0, "top": 0, "width": 800, "height": 800}, "white")
    worker = BoardTrackingWorker(capture, queue.Queue(maxsize=1), config)
    worker._resync_requested.clear()
    worker.state.synced = True
    worker._schedule_auto_resync(5)
    assert worker._resync_requested.is_set()
    assert not worker.state.synced


def test_auto_poll_resync_recovers_state():
    from core.worker import FramePacket
    from core.capture import RecognitionResult
    import numpy as np

    config = {
        "selected_side": "white",
        "recognition_threshold": 0.62,
        "recognition_margin": 0.01,
        "pixel_diff_threshold": 35,
        "square_change_threshold": 0.08,
    }
    capture = BoardCapture({"left": 0, "top": 0, "width": 800, "height": 800}, "white")
    worker = BoardTrackingWorker(capture, queue.Queue(maxsize=1), config)
    worker._resync_requested.clear()
    worker.state.synced = False

    # Mock recognizer returning starting board
    dummy_img = np.zeros((800, 800, 3), dtype=np.uint8)
    worker.recognizer.recognize_board_auto = lambda img: RecognitionResult(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR", 0.95, (), None, "white"
    )

    packet = FramePacket(1, 1000, dummy_img)
    worker._perform_resync(packet, is_auto_poll=True)

    assert worker.state.synced is True
    assert worker.state.board.turn == 1  # chess.WHITE
    assert worker.state.revision > 0


def test_chess_engine_rejects_invalid_fens_safely():
    from core.engine_logic import ChessEngine

    class MockSimpleEngine:
        def configure(self, *args, **kwargs):
            pass

        def analyse(self, *args, **kwargs):
            raise AssertionError("Stockfish should not be called with invalid board!")

        def quit(self):
            pass

    engine = ChessEngine.__new__(ChessEngine)
    engine.engine = MockSimpleEngine()
    engine.pid = 99999

    # Pawns on 8th rank
    assert engine.analyse("k3P3/8/8/8/8/8/8/K7 w - - 0 1") == []
    # Missing king
    assert engine.analyse("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQ1BNR w - - 0 1") == []
    # Opposite check
    assert engine.analyse("rnb1kbnr/ppppQppp/8/8/8/8/PPPP1PPP/RNB1KBNR w - - 0 1") == []
    # Checkmate / game over
    assert engine.analyse("k1R5/8/K7/8/8/8/8/8 b - - 0 1") == []


def test_engine_worker_does_not_loop_on_fatal_error():
    app = QCoreApplication.instance() or QCoreApplication([])

    class CrashingEngine:
        def __init__(self, threads=1):
            pass

        def configure(self, threads):
            pass

        def analyse(self, fen, multipv=3, time_ms=20):
            raise RuntimeError("Engine died unexpectedly")

        def close(self):
            pass

    config = {"threads": 1, "multipv": 3, "engine_time_ms": 20}
    worker = EngineWorker(config, engine_factory=CrashingEngine)
    errors = []
    worker.engine_error.connect(lambda err: errors.append(err))
    worker.start()

    worker.submit(1, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

    deadline = time.time() + 1.0
    while time.time() < deadline and not errors:
        app.processEvents()
        time.sleep(0.02)

    worker.stop()
    worker.wait(1000)
    app.processEvents()

    assert len(errors) == 1
    assert "Engine died unexpectedly" in errors[0]
    assert worker.requests.empty()

