from __future__ import annotations

import glob
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import mss
import numpy as np

from core.config import templates_dir


PIECE_TO_FEN = {
    "wk": "K", "wq": "Q", "wr": "R", "wb": "B", "wn": "N", "wp": "P",
    "bk": "k", "bq": "q", "br": "r", "bb": "b", "bn": "n", "bp": "p",
}


@dataclass(frozen=True)
class RecognitionResult:
    board_fen: str | None
    min_confidence: float
    unknown_squares: tuple[str, ...]
    error: str | None = None
    orientation: str | None = None


class BoardCapture:
    """Owns ROI geometry. Screen handles are opened by the capture thread."""

    def __init__(self, bbox: dict | None = None, orientation: str = "white"):
        self.bbox = bbox
        self.orientation = orientation
        self.sq_width = (bbox["width"] / 8.0) if bbox else 0.0
        self.sq_height = (bbox["height"] / 8.0) if bbox else 0.0
        self._sct = None
        self._lock = threading.Lock()

    def set_geometry(self, bbox: dict, orientation: str | None = None) -> None:
        self.bbox = dict(bbox)
        self.sq_width = self.bbox["width"] / 8.0
        self.sq_height = self.bbox["height"] / 8.0
        if orientation in {"white", "black"}:
            self.orientation = orientation

    def open(self) -> None:
        if self._sct is None:
            sct_class = getattr(mss, "MSS", mss.mss)
            self._sct = sct_class()

    def close(self) -> None:
        if self._sct is not None:
            try:
                self._sct.close()
            finally:
                self._sct = None

    def get_board_image(self) -> np.ndarray:
        if not self.bbox:
            raise ValueError("Chưa cấu hình vùng bàn cờ")
        self.open()
        with self._lock:
            raw = np.asarray(self._sct.grab(self.bbox))
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

    def square_name(self, row: int, col: int) -> str:
        if self.orientation == "black":
            return f"{chr(ord('h') - col)}{row + 1}"
        return f"{chr(ord('a') + col)}{8 - row}"

    def square_center(self, square: str) -> tuple[float, float]:
        if not self.bbox:
            raise ValueError("Chưa cấu hình vùng bàn cờ")
        if self.orientation == "black":
            col = ord("h") - ord(square[0])
            row = int(square[1]) - 1
        else:
            col = ord(square[0]) - ord("a")
            row = 8 - int(square[1])
        return (
            self.bbox["left"] + (col + 0.5) * self.sq_width,
            self.bbox["top"] + (row + 0.5) * self.sq_height,
        )

    def changed_squares(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        pixel_threshold: int = 35,
        score_threshold: float = 0.08,
    ) -> list[str]:
        if reference.shape != current.shape:
            return []
        changed: list[tuple[str, float]] = []
        for row in range(8):
            for col in range(8):
                x1 = round(col * self.sq_width)
                x2 = round((col + 1) * self.sq_width)
                y1 = round(row * self.sq_height)
                y2 = round((row + 1) * self.sq_height)
                mx = max(1, round((x2 - x1) * 0.16))
                my = max(1, round((y2 - y1) * 0.16))
                before = reference[y1 + my:y2 - my, x1 + mx:x2 - mx]
                after = current[y1 + my:y2 - my, x1 + mx:x2 - mx]
                if before.size == 0 or after.size == 0:
                    continue
                delta = np.max(cv2.absdiff(before, after), axis=2)
                pixel_ratio = float(np.count_nonzero(delta > pixel_threshold)) / delta.size
                edge_a = cv2.Canny(cv2.cvtColor(before, cv2.COLOR_BGR2GRAY), 50, 140)
                edge_b = cv2.Canny(cv2.cvtColor(after, cv2.COLOR_BGR2GRAY), 50, 140)
                edge_ratio = float(np.count_nonzero(cv2.bitwise_xor(edge_a, edge_b))) / edge_a.size
                score = 0.35 * pixel_ratio + 0.65 * edge_ratio
                if score >= score_threshold:
                    changed.append((self.square_name(row, col), score))
        changed.sort(key=lambda item: item[1], reverse=True)
        return [name for name, _ in changed]


class TemplateRecognizer:
    """Fixed-theme recognizer with templates cached and normalized in memory."""

    def __init__(
        self,
        directory: Path | None = None,
        threshold: float = 0.62,
        ambiguity_margin: float = 0.01,
        canonical_size: int = 64,
        preset: str = "standard",
    ):
        self.preset = preset
        self.directory = Path(directory or templates_dir(preset))
        self.threshold = threshold
        self.ambiguity_margin = ambiguity_margin
        self.canonical_size = canonical_size
        self.templates: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {}
        self.reload()

    def set_preset(self, preset: str) -> None:
        self.preset = preset
        self.directory = Path(templates_dir(preset))
        self.reload()

    def reload(self) -> None:
        self.templates.clear()
        target_dir = self.directory
        if not any(target_dir.glob("*.png")):
            target_dir = templates_dir("standard")
        for path_str in glob.glob(str(target_dir / "*.png")):
            piece_type = Path(path_str).name.lower()[:2]
            if piece_type not in PIECE_TO_FEN:
                continue
            image = cv2.imread(path_str, cv2.IMREAD_COLOR)
            if image is None or image.size == 0:
                continue
            image = self._normalized_square(image)
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            corners = np.concatenate((lab[:6, :6].reshape(-1, 3), lab[:6, -6:].reshape(-1, 3)))
            background = np.median(corners, axis=0)
            distance = np.linalg.norm(lab.astype(np.float32) - background.astype(np.float32), axis=2)
            mask = (distance > 16).astype(np.uint8) * 255
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
            if cv2.countNonZero(mask) < self.canonical_size * self.canonical_size * 0.05:
                mask[:] = 255
            self.templates.setdefault(piece_type, []).append((image, mask))

    @property
    def ready(self) -> bool:
        return all(piece in self.templates for piece in PIECE_TO_FEN)

    def _normalized_square(self, square: np.ndarray) -> np.ndarray:
        height, width = square.shape[:2]
        pad_x = round(width * 0.15)
        pad_y = round(height * 0.15)
        crop = square[pad_y:height - pad_y, pad_x:width - pad_x]
        return cv2.resize(crop, (self.canonical_size, self.canonical_size), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _masked_similarity(candidate: np.ndarray, template: np.ndarray, mask: np.ndarray) -> float:
        active = mask > 0
        if not np.any(active):
            return 0.0
        cand_act = candidate.astype(np.float32)[active]
        tpl_act = template.astype(np.float32)[active]
        color_distance = np.abs(cand_act - tpl_act)
        color_score = 1.0 - float(np.mean(color_distance)) / 255.0

        lum_diff = abs(float(np.mean(cand_act)) - float(np.mean(tpl_act)))
        if lum_diff > 45.0:
            color_score = max(0.0, color_score - (lum_diff - 45.0) / 100.0)

        candidate_edges = cv2.Canny(cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY), 50, 140)
        template_edges = cv2.Canny(cv2.cvtColor(template, cv2.COLOR_BGR2GRAY), 50, 140)

        k = np.ones((3, 3), np.uint8)
        c_dil = cv2.dilate(candidate_edges, k)
        t_dil = cv2.dilate(template_edges, k)

        c_cnt = np.count_nonzero(candidate_edges)
        t_cnt = np.count_nonzero(template_edges)
        if c_cnt > 0 and t_cnt > 0:
            c_in_t = np.count_nonzero((candidate_edges > 0) & (t_dil > 0)) / c_cnt
            t_in_c = np.count_nonzero((template_edges > 0) & (c_dil > 0)) / t_cnt
            edge_score = 0.5 * (c_in_t + t_in_c)
        else:
            edge_score = 0.0

        return 0.6 * color_score + 0.4 * edge_score

    def classify_square(self, square: np.ndarray) -> tuple[str | None, float, bool]:
        candidate = self._normalized_square(square)
        edges = cv2.Canny(cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY), 50, 140)
        edge_ratio = float(cv2.countNonZero(edges)) / edges.size
        # The calibrated Neo theme has flat empty squares; every piece template is
        # comfortably above 7% edge coverage, so this separates occupancy first.
        if edge_ratio < 0.035:
            return None, 1.0, False

        scores: list[tuple[str, float]] = []
        for piece_type, variants in self.templates.items():
            best = max(self._masked_similarity(candidate, tpl, mask) for tpl, mask in variants)
            scores.append((piece_type, best))
        scores.sort(key=lambda item: item[1], reverse=True)
        if not scores or scores[0][1] < self.threshold:
            return None, float(scores[0][1]) if scores else 0.0, False
        ambiguous = bool(len(scores) > 1 and scores[0][1] - scores[1][1] < self.ambiguity_margin)
        return scores[0][0], float(scores[0][1]), ambiguous

    def _scan_screen(self, image: np.ndarray) -> tuple[list[tuple[int, int, str]], list[float], list[tuple[int, int]]]:
        if not self.ready:
            return [], [], []
        height, width = image.shape[:2]
        pieces: list[tuple[int, int, str]] = []
        confidences: list[float] = []
        unknown_cells: list[tuple[int, int]] = []
        for row in range(8):
            for col in range(8):
                x1, x2 = round(col * width / 8), round((col + 1) * width / 8)
                y1, y2 = round(row * height / 8), round((row + 1) * height / 8)
                piece_type, confidence, ambiguous = self.classify_square(image[y1:y2, x1:x2])
                if piece_type:
                    pieces.append((row, col, PIECE_TO_FEN[piece_type]))
                    confidences.append(confidence)
                if ambiguous:
                    unknown_cells.append((row, col))
        return pieces, confidences, unknown_cells

    @staticmethod
    def _infer_orientation(pieces: list[tuple[int, int, str]]) -> str | None:
        white_rows = [row for row, _, piece in pieces if piece.isupper()]
        black_rows = [row for row, _, piece in pieces if piece.islower()]
        if not white_rows or not black_rows:
            return None

        # Pieces belonging to the player at the bottom have the larger screen-row
        # centroid. Kings get extra weight because they almost always remain in their
        # own half and make sparse endgames less ambiguous.
        white_score = float(np.mean(white_rows))
        black_score = float(np.mean(black_rows))
        white_king = [row for row, _, piece in pieces if piece == "K"]
        black_king = [row for row, _, piece in pieces if piece == "k"]
        if white_king and black_king:
            white_score = 0.65 * white_score + 0.35 * white_king[0]
            black_score = 0.65 * black_score + 0.35 * black_king[0]
        if abs(white_score - black_score) < 0.20:
            return None
        return "white" if white_score > black_score else "black"

    @staticmethod
    def _encode_scan(
        pieces: list[tuple[int, int, str]],
        unknown_cells: list[tuple[int, int]],
        orientation: str,
    ) -> tuple[str, tuple[str, ...]]:
        board = [["" for _ in range(8)] for _ in range(8)]
        unknown = []
        for row, col, piece in pieces:
            actual_row = 7 - row if orientation == "black" else row
            actual_col = 7 - col if orientation == "black" else col
            board[actual_row][actual_col] = piece
        for row, col in unknown_cells:
            actual_row = 7 - row if orientation == "black" else row
            actual_col = 7 - col if orientation == "black" else col
            unknown.append(chr(ord("a") + actual_col) + str(8 - actual_row))
        rows = []
        for row in board:
            encoded, empty = "", 0
            for piece in row:
                if not piece:
                    empty += 1
                else:
                    if empty:
                        encoded += str(empty)
                        empty = 0
                    encoded += piece
            if empty:
                encoded += str(empty)
            rows.append(encoded)
        return "/".join(rows), tuple(unknown)

    def recognize_board(self, image: np.ndarray, orientation: str) -> RecognitionResult:
        if not self.ready:
            return RecognitionResult(None, 0.0, (), "Thiếu template quân cờ", orientation)
        pieces, confidences, unknown_cells = self._scan_screen(image)
        board_fen, unknown = self._encode_scan(pieces, unknown_cells, orientation)
        return RecognitionResult(
            board_fen, min(confidences) if confidences else 0.0,
            unknown, None, orientation,
        )

    def recognize_board_auto(self, image: np.ndarray) -> RecognitionResult:
        if not self.ready:
            return RecognitionResult(None, 0.0, (), "Thiếu template quân cờ", None)
        pieces, confidences, unknown_cells = self._scan_screen(image)
        orientation = self._infer_orientation(pieces)
        if orientation is None:
            return RecognitionResult(
                None, min(confidences) if confidences else 0.0, (),
                "Không xác định chắc chắn được màu quân ở phía dưới", None,
            )
        board_fen, unknown = self._encode_scan(pieces, unknown_cells, orientation)
        return RecognitionResult(
            board_fen, min(confidences) if confidences else 0.0,
            unknown, None, orientation,
        )
