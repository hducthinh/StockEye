import sys
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QPolygon
import math
import ctypes
import json
import os

class OverlayUI(QWidget):
    def __init__(self):
        super().__init__()
        
        # Lấy thông số cấu hình phe
        self.player_color = "white"
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    self.player_color = json.load(f).get("player_color", "white").lower()
            except:
                pass
                
        # Cấu hình cửa sổ Overlay
        self.setWindowFlags(
            Qt.FramelessWindowHint |      # Không viền
            Qt.WindowStaysOnTopHint |     # Luôn nổi trên cùng
            Qt.WindowTransparentForInput |# Xuyên chuột (Click-through)
            Qt.Tool                       # Ẩn khỏi Taskbar
        )
        # Nền trong suốt
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # --- MA THUẬT: ẨN OVERLAY KHỎI MSS ---
        # 0x00000011 (WDA_EXCLUDEFROMCAPTURE) giúp cửa sổ này trở nên "tàng hình"
        # đối với các phần mềm quay/chụp màn hình. Do đó mss sẽ chỉ chụp được bàn cờ bên dưới!
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        except Exception as e:
            print("[UI] Không thể set DisplayAffinity:", e)
        
        # Đặt kích thước bằng với toàn bộ màn hình
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        
        # Biến lưu trữ các nước đi cần vẽ
        # Format: [((start_x, start_y), (end_x, end_y), score), ...]
        self.moves_to_draw = []

    def update_moves(self, moves):
        """Hàm này được gọi từ Signal của Worker Thread để cập nhật data và vẽ lại"""
        self.moves_to_draw = moves
        self.update() # Kích hoạt hàm paintEvent()

    def paintEvent(self, event):
        """Hàm vẽ của PyQt, được gọi mỗi khi cần cập nhật màn hình"""
        if not self.moves_to_draw:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) # Chống răng cưa
        
        for i, move in enumerate(self.moves_to_draw):
            start_pt, end_pt, score = move
            
            # Màu sắc: Top 1 (Xanh lá đậm), Top 2 & 3 (Cam nhạt hơn)
            if i == 0:
                color = QColor(0, 255, 0, 200) # Green, alpha=200
            else:
                color = QColor(255, 165, 0, 150) # Orange, alpha=150
                
            pen = QPen(color, 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            
            p1 = QPoint(int(start_pt[0]), int(start_pt[1]))
            p2 = QPoint(int(end_pt[0]), int(end_pt[1]))
            
            # 1. Vẽ thân mũi tên (đoạn thẳng)
            painter.drawLine(p1, p2)
            
            # 2. Vẽ đầu mũi tên
            self._draw_arrow_head(painter, p1, p2, color)
            
            # 3. Vẽ văn bản điểm số (Score)
            painter.setPen(QPen(QColor(255, 255, 255), 2)) # Chữ trắng
            # Đặt text lệch ra một chút để không đè lên mũi tên
            painter.drawText(p2.x() + 15, p2.y() + 15, str(score))

    def _draw_arrow_head(self, painter, p1, p2, color):
        """Tính toán toán học để vẽ tam giác đầu mũi tên"""
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        angle = math.atan2(dy, dx)
        
        arrow_size = 20
        # Tính toán 2 điểm đáy của tam giác cân
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
