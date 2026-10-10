from __future__ import annotations

import os
import subprocess
import sys

import chess
import chess.engine

from core.config import engine_path
from core.process_guard import register_engine_pid, unregister_engine_pid


class ChessEngine:
    """Single-thread-owned UCI adapter. It does not own application board state."""

    def __init__(self, path: str | os.PathLike | None = None, threads: int = 1):
        self.path = str(path or engine_path())
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Không tìm thấy Stockfish: {self.path}")
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            kwargs["startupinfo"] = startupinfo
        self.engine = chess.engine.SimpleEngine.popen_uci(self.path, **kwargs)
        self.pid = None
        try:
            process = self.engine.transport.get_extra_info("subprocess")
            self.pid = getattr(process, "pid", None)
            register_engine_pid(self.pid)
        except Exception:
            self.pid = None
        self.configure(threads)

    def configure(self, threads: int) -> None:
        self.engine.configure({"Threads": max(1, int(threads))})

    def analyse(self, fen: str, multipv: int = 3, time_ms: int = 20) -> list[dict]:
        try:
            board = chess.Board(fen)
        except Exception:
            return []
        if not board.is_valid() or board.is_game_over() or not any(board.legal_moves):
            return []
        try:
            info = self.engine.analyse(
                board,
                chess.engine.Limit(time=max(0.005, time_ms / 1000.0)),
                multipv=max(1, min(4, int(multipv))),
            )
        except (chess.engine.EngineTerminatedError, chess.engine.EngineError):
            raise
        except Exception:
            return []
        if isinstance(info, dict):
            info = [info]
        moves = []
        for entry in info:
            pv = entry.get("pv") or []
            if not pv:
                continue
            score_obj = entry["score"].white()
            if score_obj.is_mate():
                score = f"M{score_obj.mate()}"
            else:
                centipawns = score_obj.score(mate_score=100000)
                value = (centipawns or 0) / 100.0
                score = f"{value:+.2f}"
            pov = entry["score"].pov(board.turn).score(mate_score=100000) or 0
            moves.append({"move": pv[0].uci(), "score": score, "sort": pov})
        moves.sort(key=lambda item: item["sort"], reverse=True)
        for item in moves:
            item.pop("sort", None)
        return moves

    def close(self) -> None:
        if not getattr(self, "engine", None):
            return
        try:
            self.engine.quit()
        except Exception:
            try:
                self.engine.close()
            except Exception:
                pass
        unregister_engine_pid(self.pid)
        self.engine = None
