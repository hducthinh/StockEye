import sys
import numpy as np
import cv2
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QPolygon, QImage, QPixmap
import math

class ShareableBoardUI(QWidget):
    def __init__(self, capture):
        super().__init__()
        self.capture = capture
        
        self.setWindowTitle("StockEye - Bàn cờ phụ (Share Screen)")
        # Normal window flags so it's capturable by OBS/Discord. 
        # WindowStaysOnTopHint is optional but good so the user can see it
        # FramelessWindowHint to remove the title bar as requested
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window | Qt.FramelessWindowHint)
        
        # Kích thước cố định 333x333
        self.setFixedSize(333, 333)
        self.moves_to_draw = []
        
        # Timer to capture screen at 30 FPS
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_board)
        self.timer.start(33) # ~30 FPS
        
        self.current_pixmap = None

    def update_board(self):
        if not self.isVisible():
            return
            
        try:
            if not self.capture.bbox:
                return
                
            # Get raw image from mss
            img_bgr = self.capture.get_board_image()
            
            # Convert OpenCV BGR image to QImage
            # Convert BGR to RGB
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            self.current_pixmap = QPixmap.fromImage(qimg)
            self.update() # Trigger paintEvent
        except Exception as e:
            pass

    def update_moves(self, moves):
        """Called from Worker Thread signal to update arrows"""
        self.moves_to_draw = moves
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. Draw the board background
        if self.current_pixmap:
            # Scale pixmap to fit window size, keeping aspect ratio or just stretch?
            # It's better to stretch to match the window if user resizes, 
            # but for simplicity we draw it and scale arrows accordingly.
            rect = self.rect()
            painter.drawPixmap(rect, self.current_pixmap)
            
            scale_x = rect.width() / self.capture.bbox["width"] if self.capture.bbox else 1.0
            scale_y = rect.height() / self.capture.bbox["height"] if self.capture.bbox else 1.0
        else:
            scale_x = 1.0
            scale_y = 1.0

        # 2. Draw arrows
        if not self.moves_to_draw or not self.capture.bbox:
            return
            
        for i, move in enumerate(self.moves_to_draw):
            start_pt_abs, end_pt_abs, score = move
            
            # Convert absolute screen coordinates to relative coordinates inside the bbox
            rel_start_x = start_pt_abs[0] - self.capture.bbox["left"]
            rel_start_y = start_pt_abs[1] - self.capture.bbox["top"]
            
            rel_end_x = end_pt_abs[0] - self.capture.bbox["left"]
            rel_end_y = end_pt_abs[1] - self.capture.bbox["top"]
            
            # Apply scaling in case the user resizes the window
            final_start_x = rel_start_x * scale_x
            final_start_y = rel_start_y * scale_y
            final_end_x = rel_end_x * scale_x
            final_end_y = rel_end_y * scale_y
            
            if i == 0:
                color = QColor(0, 255, 0, 200) # Best
            elif i == 1:
                color = QColor(0, 191, 255, 200) # Strong
            elif i == 2:
                color = QColor(255, 215, 0, 180) # Interesting
            else:
                color = QColor(255, 0, 0, 180) # Bad
                
            pen = QPen(color, 6 * scale_x, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            
            p1 = QPoint(int(final_start_x), int(final_start_y))
            p2 = QPoint(int(final_end_x), int(final_end_y))
            
            # Draw line
            painter.drawLine(p1, p2)
            
            # Draw head
            self._draw_arrow_head(painter, p1, p2, color, scale_x)
            
            # Draw text
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            font = painter.font()
            font.setPointSize(int(12 * scale_x))
            painter.setFont(font)
            painter.drawText(p2.x() + int(15 * scale_x), p2.y() + int(15 * scale_y), str(score))

    def _draw_arrow_head(self, painter, p1, p2, color, scale):
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        angle = math.atan2(dy, dx)
        
        arrow_size = 20 * scale
        arrow_p1 = QPoint(
            int(p2.x() - arrow_size * math.cos(angle - math.pi / 6)),
            int(p2.y() - arrow_size * math.sin(angle - math.pi / 6))
        )
        arrow_p2 = QPoint(
            int(p2.x() - arrow_size * math.cos(angle + math.pi / 6)),
            int(p2.y() - arrow_size * math.sin(angle + math.pi / 6))
        )
        
        polygon = QPolygon([p2, arrow_p1, arrow_p2])
        painter.setBrush(color)
        painter.drawPolygon(polygon)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'oldPos') and self.oldPos is not None:
            delta = QPoint(event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = None
