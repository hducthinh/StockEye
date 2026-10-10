from __future__ import annotations

from dataclasses import dataclass

import chess
import numpy as np

from core.capture import PIECE_TO_FEN, RecognitionResult, TemplateRecognizer


@dataclass(frozen=True)
class MoveResolution:
    move: chess.Move | None
    candidates: tuple[chess.Move, ...]
    reason: str | None = None


def changed_squares_for_move(board: chess.Board, move: chess.Move) -> frozenset[str]:
    after = board.copy(stack=False)
    after.push(move)
    changed = {
        chess.square_name(square)
        for square in chess.SQUARES
        if board.piece_at(square) != after.piece_at(square)
    }
    return frozenset(changed)


class LegalMoveResolver:
    def resolve(
        self,
        board: chess.Board,
        changed_squares: list[str] | set[str],
        destination_image: np.ndarray | None = None,
        recognizer: TemplateRecognizer | None = None,
    ) -> MoveResolution:
        observed = frozenset(changed_squares)
        candidates = tuple(
            move for move in board.legal_moves
            if changed_squares_for_move(board, move) == observed
        )
        if not candidates:
            return MoveResolution(None, (), "Không có nước hợp lệ khớp các ô thay đổi")
        if len(candidates) == 1:
            return MoveResolution(candidates[0], candidates)

        if all(move.promotion for move in candidates):
            selected = self._resolve_promotion(candidates, destination_image, recognizer)
            return MoveResolution(selected, candidates, None if selected else "Không xác định được quân phong cấp")
        return MoveResolution(None, candidates, "Có nhiều nước hợp lệ cùng khớp")

    @staticmethod
    def _resolve_promotion(
        candidates: tuple[chess.Move, ...],
        destination_image: np.ndarray | None,
        recognizer: TemplateRecognizer | None,
    ) -> chess.Move | None:
        if destination_image is not None and recognizer is not None:
            piece_type, _, ambiguous = recognizer.classify_square(destination_image)
            if piece_type and not ambiguous:
                fen_symbol = PIECE_TO_FEN[piece_type].lower()
                promotion_type = {
                    "q": chess.QUEEN, "r": chess.ROOK,
                    "b": chess.BISHOP, "n": chess.KNIGHT,
                }.get(fen_symbol)
                if promotion_type:
                    for move in candidates:
                        if move.promotion == promotion_type:
                            return move
        for move in candidates:
            if move.promotion == chess.QUEEN:
                return move
        return None


def reconcile_from_starting_board(target_board_fen: str, max_depth: int = 4) -> chess.Board | None:
    start = chess.Board()
    if target_board_fen == start.board_fen():
        return start

    try:
        target_board = chess.Board(f"{target_board_fen} w - - 0 1")
    except ValueError:
        return None

    diff = {sq for sq in chess.SQUARES if start.piece_at(sq) != target_board.piece_at(sq)}
    if len(diff) > max_depth * 2:
        return None

    def search(b: chess.Board, depth: int) -> chess.Board | None:
        if depth == 0:
            return b if b.board_fen() == target_board_fen else None
        for m in b.legal_moves:
            if m.from_square in diff or m.to_square in diff:
                next_b = b.copy(stack=True)
                next_b.push(m)
                if next_b.board_fen() == target_board_fen:
                    return next_b
                found = search(next_b, depth - 1)
                if found is not None:
                    return found
        return None

    for d in range(1, max_depth + 1):
        found = search(start, d)
        if found is not None:
            return found
    return None


class BoardState:
    """Transactional owner of python-chess state and revision."""

    def __init__(self, selected_side: str = "white"):
        self.board = chess.Board()
        self.revision = 0
        self.selected_side = selected_side
        self.synced = False

    def push(self, move: chess.Move) -> int:
        if move not in self.board.legal_moves:
            raise ValueError(f"Nước đi không hợp lệ: {move.uci()}")
        self.board.push(move)
        self.revision += 1
        self.synced = True
        return self.revision

    def resync(self, recognition: RecognitionResult) -> tuple[bool, str]:
        if recognition.error:
            return False, recognition.error
        if not recognition.board_fen:
            return False, "Không nhận diện được bố cục quân"
        msg_detail = ""
        candidate = self._reconcile_with_history(recognition.board_fen)
        if candidate is None:
            from_start = reconcile_from_starting_board(recognition.board_fen, max_depth=4)
            if from_start is not None:
                candidate = from_start
                if len(candidate.move_stack) == 0:
                    msg_detail = " (Ván mới: xuất phát)"
                else:
                    msg_detail = f" (Ván mới: đã đi {len(candidate.move_stack)} nước)"

        if candidate is None:
            turn = "w" if self.selected_side == "white" else "b"
            for test_turn in ("w", "b"):
                try:
                    tb = chess.Board(f"{recognition.board_fen} {test_turn} - - 0 1")
                    if tb.is_valid() and tb.is_check():
                        turn = test_turn
                        break
                except ValueError:
                    pass

            castling = ""
            try:
                tb = chess.Board(f"{recognition.board_fen} w - - 0 1")
                if tb.piece_at(chess.E1) == chess.Piece(chess.KING, chess.WHITE):
                    if tb.piece_at(chess.H1) == chess.Piece(chess.ROOK, chess.WHITE):
                        castling += "K"
                    if tb.piece_at(chess.A1) == chess.Piece(chess.ROOK, chess.WHITE):
                        castling += "Q"
                if tb.piece_at(chess.E8) == chess.Piece(chess.KING, chess.BLACK):
                    if tb.piece_at(chess.H8) == chess.Piece(chess.ROOK, chess.BLACK):
                        castling += "k"
                    if tb.piece_at(chess.A8) == chess.Piece(chess.ROOK, chess.BLACK):
                        castling += "q"
            except Exception:
                pass
            if not castling:
                castling = "-"

            try:
                candidate = chess.Board(f"{recognition.board_fen} {turn} {castling} - 0 1")
            except ValueError as exc:
                if recognition.unknown_squares:
                    return False, "Ô chưa chắc chắn: " + ", ".join(recognition.unknown_squares)
                return False, f"FEN không hợp lệ: {exc}"

            if not candidate.is_valid():
                alt_turn = "b" if turn == "w" else "w"
                try:
                    alt_candidate = chess.Board(f"{recognition.board_fen} {alt_turn} {castling} - 0 1")
                    if alt_candidate.is_valid():
                        candidate = alt_candidate
                except ValueError:
                    pass

        if not candidate.is_valid():
            if recognition.unknown_squares:
                return False, "Ô chưa chắc chắn: " + ", ".join(recognition.unknown_squares)
            return False, f"Bàn cờ không hợp lệ (status={candidate.status()})"

        self.board = candidate
        self.revision += 1
        self.synced = True
        return True, "Đồng bộ thành công" + msg_detail

    def _reconcile_with_history(self, board_fen: str) -> chess.Board | None:
        if self.board.board_fen() == board_fen:
            return self.board.copy(stack=True)
        matches: list[chess.Board] = []
        for move in self.board.legal_moves:
            candidate = self.board.copy(stack=True)
            candidate.push(move)
            if candidate.board_fen() == board_fen:
                matches.append(candidate)
        return matches[0] if len(matches) == 1 else None


def square_crop(image: np.ndarray, square: str, orientation: str) -> np.ndarray:
    file_index = ord(square[0]) - ord("a")
    rank = int(square[1])
    if orientation == "black":
        col = 7 - file_index
        row = rank - 1
    else:
        col = file_index
        row = 8 - rank
    height, width = image.shape[:2]
    x1, x2 = round(col * width / 8), round((col + 1) * width / 8)
    y1, y2 = round(row * height / 8), round((row + 1) * height / 8)
    return image[y1:y2, x1:x2]
