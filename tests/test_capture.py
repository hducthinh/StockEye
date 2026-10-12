from pathlib import Path
import cv2
import numpy as np

from core.capture import BoardCapture, TemplateRecognizer


def paint_piece(image, row, col, color=(240, 240, 240)):
    size = image.shape[0] // 8
    center = (col * size + size // 2, row * size + size // 2)
    cv2.circle(image, center, size // 4, color, -1)
    cv2.circle(image, center, size // 4, (20, 20, 20), 3)


def test_detects_two_changed_squares_white_orientation():
    capture = BoardCapture({"left": 0, "top": 0, "width": 800, "height": 800}, "white")
    before = np.full((800, 800, 3), 100, dtype=np.uint8)
    after = before.copy()
    paint_piece(before, 6, 4)
    paint_piece(after, 4, 4)
    assert set(capture.changed_squares(before, after)) == {"e2", "e4"}


def test_square_center_black_orientation():
    capture = BoardCapture({"left": -800, "top": 100, "width": 800, "height": 800}, "black")
    assert capture.square_center("h1") == (-750.0, 150.0)
    assert capture.square_center("a8") == (-50.0, 850.0)


def test_orientation_is_inferred_from_piece_centroids():
    white_at_bottom = [
        (7, 4, "K"), (6, 0, "P"), (6, 7, "P"),
        (0, 4, "k"), (1, 0, "p"), (1, 7, "p"),
    ]
    black_at_bottom = [
        (0, 4, "K"), (1, 0, "P"), (1, 7, "P"),
        (7, 4, "k"), (6, 0, "p"), (6, 7, "p"),
    ]
    assert TemplateRecognizer._infer_orientation(white_at_bottom) == "white"
    assert TemplateRecognizer._infer_orientation(black_at_bottom) == "black"


def test_template_recognizer_starting_board_recognition():
    import glob
    rec = TemplateRecognizer(threshold=0.65, ambiguity_margin=0.01)
    assert rec.ready

    # Verify each piece template self-classifies correctly
    for f in rec.directory.glob("*.png"):
        if "empty" in f.name:
            continue
        img = cv2.imread(str(f))
        piece_type, score, amb = rec.classify_square(img)
        expected = Path(f).name.lower()[:2]
        assert piece_type == expected
        assert score >= 0.90
        assert amb is False


def test_template_recognizer_preset_switch():
    rec = TemplateRecognizer(preset="standard")
    assert rec.preset == "standard"
    assert rec.ready
    assert "standard" in str(rec.directory).lower()

    rec.set_preset("puzzle")
    assert rec.preset == "puzzle"
    assert rec.ready
    assert "puzzle" in str(rec.directory).lower()
