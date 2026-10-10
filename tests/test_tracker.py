import chess

from core.capture import RecognitionResult
from core.tracker import BoardState, LegalMoveResolver, changed_squares_for_move


def resolve(fen, squares):
    board = chess.Board(fen)
    return LegalMoveResolver().resolve(board, squares).move


def test_normal_move_changes_two_squares():
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")
    assert changed_squares_for_move(board, move) == {"e2", "e4"}
    assert resolve(board.fen(), {"e2", "e4"}) == move


def test_capture_changes_two_squares():
    board = chess.Board("7k/8/8/3p4/4P3/8/8/7K w - - 0 1")
    move = chess.Move.from_uci("e4d5")
    assert changed_squares_for_move(board, move) == {"e4", "d5"}
    assert resolve(board.fen(), {"e4", "d5"}) == move


def test_en_passant_changes_three_squares():
    board = chess.Board("7k/8/8/3pP3/8/8/8/7K w - d6 0 1")
    move = chess.Move.from_uci("e5d6")
    assert changed_squares_for_move(board, move) == {"e5", "d5", "d6"}
    assert resolve(board.fen(), {"e5", "d5", "d6"}) == move


def test_castling_changes_four_squares():
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    move = chess.Move.from_uci("e1g1")
    assert changed_squares_for_move(board, move) == {"e1", "f1", "g1", "h1"}
    assert resolve(board.fen(), {"e1", "f1", "g1", "h1"}) == move


def test_promotion_defaults_to_queen_when_image_is_unavailable():
    board = chess.Board("7k/P7/8/8/8/8/8/7K w - - 0 1")
    result = LegalMoveResolver().resolve(board, {"a7", "a8"})
    assert result.move == chess.Move.from_uci("a7a8q")
    assert len(result.candidates) == 4


def test_unmatched_change_is_rejected():
    result = LegalMoveResolver().resolve(chess.Board(), {"e2", "e5"})
    assert result.move is None


def test_resync_is_transactional_for_invalid_board():
    state = BoardState("white")
    old_fen = state.board.fen()
    ok, _ = state.resync(RecognitionResult("8/8/8/8/8/8/8/8", 0.9, ()))
    assert not ok
    assert state.board.fen() == old_fen


def test_resync_replays_one_move_and_preserves_metadata():
    state = BoardState("white")
    after = chess.Board()
    after.push_uci("e2e4")
    ok, _ = state.resync(RecognitionResult(after.board_fen(), 0.9, ()))
    assert ok
    assert state.board.peek() == chess.Move.from_uci("e2e4")
    assert state.board.turn == chess.BLACK
    assert state.board.has_kingside_castling_rights(chess.WHITE)


def test_resync_starting_position_creates_fresh_game():
    state = BoardState("black")
    # Simulate an endgame from previous game
    state.board = chess.Board("7k/8/8/8/8/8/8/7K b - - 0 50")
    ok, msg = state.resync(RecognitionResult(chess.STARTING_BOARD_FEN, 0.95, ()))
    assert ok
    assert "Ván mới: xuất phát" in msg
    assert state.board.turn == chess.WHITE
    assert state.board.has_kingside_castling_rights(chess.WHITE)
    assert state.board.has_queenside_castling_rights(chess.WHITE)
    assert state.board.has_kingside_castling_rights(chess.BLACK)
    assert state.board.has_queenside_castling_rights(chess.BLACK)
    assert len(state.board.move_stack) == 0


def test_resync_opening_moves_reconstructs_history_and_castling():
    state = BoardState("white")
    # Simulate an endgame from previous game
    state.board = chess.Board("7k/8/8/8/8/8/8/7K b - - 0 50")

    # Opponent already played 1. e4 before resync
    board_after_e4 = chess.Board()
    board_after_e4.push_uci("e2e4")

    ok, msg = state.resync(RecognitionResult(board_after_e4.board_fen(), 0.95, ()))
    assert ok
    assert "Ván mới: đã đi 1 nước" in msg
    assert state.board.turn == chess.BLACK
    assert state.board.peek() == chess.Move.from_uci("e2e4")
    assert state.board.has_kingside_castling_rights(chess.WHITE)
    assert state.board.has_kingside_castling_rights(chess.BLACK)


def test_resync_opening_multi_moves_reconstructs_turn_and_castling():
    state = BoardState("white")
    # 4 plies: 1. e4 e5 2. Nf3 Nc6
    board_4_plies = chess.Board()
    for uci in ["e2e4", "e7e5", "g1f3", "b8c6"]:
        board_4_plies.push_uci(uci)

    ok, msg = state.resync(RecognitionResult(board_4_plies.board_fen(), 0.95, ()))
    assert ok
    assert "Ván mới: đã đi 4 nước" in msg
    assert state.board.turn == chess.WHITE
    assert state.board.has_kingside_castling_rights(chess.WHITE)
    assert state.board.has_kingside_castling_rights(chess.BLACK)

