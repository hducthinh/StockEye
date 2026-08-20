import sys
import cv2
import numpy as np
import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QImage, QPainter, QPen, QColor, QPolygon

class SmallBoardUI(QWidget):
    def __init__(self, capture):
        super().__init__()
        self.capture = capture
        self.setWindowTitle("StockEye - Shared Board")
        
        # Luôn nổi lên trên, nhưng là cửa sổ bình thường để có thể chia sẻ
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.resize(400, 400)
        
        self.moves_to_draw = []
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_board)
        
        self.board_image = None
        
        # Mặc định chưa chạy timer
        self.is_active = False

    def toggle_active(self, state):
        """Bật/tắt luồng cập nhật bàn cờ phụ"""
        self.is_active = state
        if self.is_active:
            self.timer.start(100) # 10 FPS
            self.show()
        else:
            self.timer.stop()
            self.hide()

    def update_moves(self, moves):
        if not self.is_active:
            return
        self.moves_to_draw = moves
        self.update_board()

    def update_board(self):
        if not self.capture.bbox or not self.is_active:
            return
            
        try:
            # Capture the current board from the screen
            img = self.capture.get_board_image() # BGR numpy array
            
            # Convert to RGB for PyQt
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            bytes_per_line = ch * w
            q_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.board_image = q_img
            
            self.update() # Trigger paintEvent
        except Exception as e:
            pass

    def paintEvent(self, event):
        if not self.board_image or not self.is_active:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Vẽ ảnh nền bàn cờ (scale theo kích thước cửa sổ phụ)
        rect = self.rect()
        painter.drawImage(rect, self.board_image)
        
        if not self.moves_to_draw:
            return
            
        # Tính tỷ lệ scale
        if not self.capture.bbox:
            return
            
        orig_w = self.capture.bbox["width"]
        orig_h = self.capture.bbox["height"]
        
        scale_x = rect.width() / orig_w
        scale_y = rect.height() / orig_h
        
        for i, move in enumerate(self.moves_to_draw):
            start_pt, end_pt, score = move
            
            # Chuyển tọa độ màn hình tuyệt đối sang tọa độ tương đối của bounding box
            rel_start_x = (start_pt[0] - self.capture.bbox["left"]) * scale_x
            rel_start_y = (start_pt[1] - self.capture.bbox["top"]) * scale_y
            
            rel_end_x = (end_pt[0] - self.capture.bbox["left"]) * scale_x
            rel_end_y = (end_pt[1] - self.capture.bbox["top"]) * scale_y
            
            # Màu sắc theo thứ hạng
            if i == 0:
                color = QColor(0, 255, 0, 200) # Green, Best Move
            elif i == 1:
                color = QColor(0, 191, 255, 200) # DeepSkyBlue
            elif i == 2:
                color = QColor(255, 215, 0, 180) # Gold/Yellow
            else:
                color = QColor(255, 0, 0, 180) # Red
                
            pen = QPen(color, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            
            p1 = QPoint(int(rel_start_x), int(rel_start_y))
            p2 = QPoint(int(rel_end_x), int(rel_end_y))
            
            # 1. Vẽ thân mũi tên
            painter.drawLine(p1, p2)
            
            # 2. Vẽ đầu mũi tên
            self._draw_arrow_head(painter, p1, p2, color)
            
            # 3. Vẽ văn bản điểm số
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.drawText(p2.x() + 10, p2.y() + 10, str(score))

    def _draw_arrow_head(self, painter, p1, p2, color):
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        angle = math.atan2(dy, dx)
        
        arrow_size = 15
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
