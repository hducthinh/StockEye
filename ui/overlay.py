import ctypes
import math

from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygon
from PyQt5.QtWidgets import QApplication, QWidget


class OverlayUI(QWidget):
    def __init__(self):
        super().__init__()
        self.moves_to_draw = []
        self.capture_excluded = False
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._fit_virtual_desktop()

    def _fit_virtual_desktop(self) -> None:
        screens = QApplication.screens()
        if not screens:
            return
        geometry = QRect(screens[0].geometry())
        for screen in screens[1:]:
            geometry = geometry.united(screen.geometry())
        self.setGeometry(geometry)

    def enable_capture_exclusion(self) -> bool:
        if not hasattr(ctypes, "windll"):
            return False
        hwnd = int(self.winId())
        result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        self.capture_excluded = bool(result)
        return self.capture_excluded

    def update_moves(self, moves: list) -> None:
        self.moves_to_draw = list(moves)
        self.update()

    def clear_moves(self) -> None:
        if self.moves_to_draw:
            self.moves_to_draw = []
            self.update()

    def paintEvent(self, event) -> None:
        if not self.moves_to_draw:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        origin = self.geometry().topLeft()
        for index, (start, end, score) in enumerate(self.moves_to_draw):
            colors = (
                QColor(0, 255, 127, 220), QColor(0, 190, 255, 210),
                QColor(255, 215, 0, 200), QColor(255, 82, 82, 190),
            )
            color = colors[min(index, len(colors) - 1)]
            p1 = QPoint(round(start[0] - origin.x()), round(start[1] - origin.y()))
            p2 = QPoint(round(end[0] - origin.x()), round(end[1] - origin.y()))
            painter.setPen(QPen(color, 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(p1, p2)
            self._draw_arrow_head(painter, p1, p2, color)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawText(p2.x() + 10, p2.y() + 18, str(score))

    @staticmethod
    def _draw_arrow_head(painter: QPainter, start: QPoint, end: QPoint, color: QColor) -> None:
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        size = 20
        left = QPoint(
            round(end.x() - size * math.cos(angle - math.pi / 6)),
            round(end.y() - size * math.sin(angle - math.pi / 6)),
        )
        right = QPoint(
            round(end.x() - size * math.cos(angle + math.pi / 6)),
            round(end.y() - size * math.sin(angle + math.pi / 6)),
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QPolygon([end, left, right]))
