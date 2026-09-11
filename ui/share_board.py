import sys
import numpy as np
import cv2
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QPolygon, QImage, QPixmap, QFont, QBrush, QLinearGradient
import math

class ShareableBoardUI(QWidget):
    visibility_changed = pyqtSignal(bool)

    def __init__(self, capture):
        super().__init__()
        self.capture = capture
        
        self.setWindowTitle("StockEye - Bàn Cờ Phụ")
        # Luôn nổi trên cùng, cửa sổ độc lập, không viền hệ thống (custom border)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Kích thước ban đầu: 360 x (360 + 36px header)
        self.header_height = 36
        self.board_size = 360
        self.setMinimumSize(260, 260 + self.header_height)
        self.resize(self.board_size, self.board_size + self.header_height)
        
        # Mặc định ở góc trên bên trái màn hình (người dùng vẫn tự do kéo di chuyển)
        try:
            desktop_geom = QApplication.desktop().availableGeometry()
            self.move(desktop_geom.left() + 20, desktop_geom.top() + 20)
        except Exception:
            self.move(20, 20)
        
        self.moves_to_draw = []
        self.current_pixmap = None
        self.is_resizing = False
        self.drag_position = None
        self.resize_margin = 16
        
        # Timer cập nhật hình ảnh bàn cờ từ capture (~30 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_board)
        self.timer.start(33)

    def update_board(self):
        if not self.isVisible():
            return
            
        try:
            if not self.capture.bbox:
                return
                
            # Lấy ảnh vùng bàn cờ từ capture (đã có thread lock)
            img_bgr = self.capture.get_board_image()
            if img_bgr is None or img_bgr.size == 0:
                return
                
            # Chuyển BGR sang RGB cho QImage
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            self.current_pixmap = QPixmap.fromImage(qimg)
            self.update() # Kích hoạt vẽ lại
        except Exception:
            pass

    def update_moves(self, moves):
        """Được gọi từ Signal của Worker Thread để cập nhật danh sách nước đi gợi ý"""
        self.moves_to_draw = moves
        self.update()

    def get_board_rect(self):
        """Trả về QRect của khu vực vẽ bàn cờ (bên dưới header)"""
        w = self.width()
        h = self.height() - self.header_height
        size = min(w, h)
        # Căn giữa bàn cờ trong khung còn lại
        offset_x = (w - size) // 2
        offset_y = self.header_height + (h - size) // 2
        return QRect(offset_x, offset_y, size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        total_w = self.width()
        total_h = self.height()
        
        # 1. Vẽ nền tổng thể khung cửa sổ (Dark Glassmorphism)
        bg_rect = QRect(0, 0, total_w, total_h)
        painter.setPen(QPen(QColor(46, 204, 113, 200), 1.5)) # Viền xanh tinh tế
        painter.setBrush(QBrush(QColor(18, 22, 28, 245)))
        painter.drawRoundedRect(bg_rect, 10, 10)
        
        # 2. Vẽ Header Bar
        header_rect = QRect(0, 0, total_w, self.header_height)
        grad = QLinearGradient(0, 0, 0, self.header_height)
        grad.setColorAt(0.0, QColor(32, 40, 52, 255))
        grad.setColorAt(1.0, QColor(22, 28, 36, 255))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(QRect(1, 1, total_w - 2, self.header_height), 10, 10)
        # Đè góc dưới header để vuông vức tiếp giáp bàn cờ
        painter.drawRect(QRect(1, self.header_height - 6, total_w - 2, 6))
        
        # Tiêu đề Header
        painter.setPen(QColor(236, 240, 241))
        title_font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(title_font)
        painter.drawText(12, int(self.header_height * 0.65), "♟ Bàn Cờ Phụ")
        
        # Badge Phe & Điểm Eval
        eval_text = ""
        if self.moves_to_draw and len(self.moves_to_draw) > 0:
            first_move = self.moves_to_draw[0]
            score_val = str(first_move[2])
            eval_text = f"Eval: {score_val}"
            
        color_text = "⚪ Trắng" if getattr(self.capture, "player_color", "white") == "white" else "⚫ Đen"
        badge_text = f"{color_text}  {eval_text}".strip()
        
        painter.setPen(QColor(46, 204, 113))
        badge_font = QFont("Segoe UI", 9, QFont.DemiBold)
        painter.setFont(badge_font)
        painter.drawText(QRect(110, 0, total_w - 145, self.header_height), Qt.AlignRight | Qt.AlignVCenter, badge_text)
        
        # Nút đóng [X]
        close_rect = QRect(total_w - 28, 6, 22, 22)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(231, 76, 60, 180))
        painter.drawRoundedRect(close_rect, 4, 4)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(close_rect, Qt.AlignCenter, "✕")

        # 3. Vẽ Bàn Cờ
        board_rect = self.get_board_rect()
        if self.current_pixmap and not self.current_pixmap.isNull():
            painter.drawPixmap(board_rect, self.current_pixmap)
        else:
            # Vẽ bàn cờ ô vuông tạm thời nếu chưa có ảnh
            sq_w = board_rect.width() / 8.0
            sq_h = board_rect.height() / 8.0
            for r in range(8):
                for c in range(8):
                    sq_rect = QRect(int(board_rect.left() + c * sq_w), int(board_rect.top() + r * sq_h), int(sq_w) + 1, int(sq_h) + 1)
                    color = QColor(240, 217, 181) if (r + c) % 2 == 0 else QColor(181, 136, 99)
                    painter.fillRect(sq_rect, color)
            painter.setPen(QColor(120, 120, 120))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(board_rect, Qt.AlignCenter, "Đang chờ ảnh bàn cờ...")

        # 4. Vẽ Mũi Tên Gợi Ý (Arrows)
        if self.moves_to_draw and self.capture.bbox:
            orig_w = self.capture.bbox.get("width", 1)
            orig_h = self.capture.bbox.get("height", 1)
            scale_x = board_rect.width() / float(orig_w)
            scale_y = board_rect.height() / float(orig_h)

            for i, move in enumerate(self.moves_to_draw):
                start_pt_abs, end_pt_abs, score = move
                
                # Tọa độ tương đối so với bbox gốc
                rel_start_x = start_pt_abs[0] - self.capture.bbox["left"]
                rel_start_y = start_pt_abs[1] - self.capture.bbox["top"]
                rel_end_x = end_pt_abs[0] - self.capture.bbox["left"]
                rel_end_y = end_pt_abs[1] - self.capture.bbox["top"]
                
                # Chiếu vào board_rect trên bàn cờ phụ
                final_start_x = board_rect.left() + (rel_start_x * scale_x)
                final_start_y = board_rect.top() + (rel_start_y * scale_y)
                final_end_x = board_rect.left() + (rel_end_x * scale_x)
                final_end_y = board_rect.top() + (rel_end_y * scale_y)
                
                # Màu sắc theo độ ưu tiên nước đi
                if i == 0:
                    color = QColor(0, 255, 127, 230)   # Best: Xanh lá neon rực rỡ
                elif i == 1:
                    color = QColor(0, 229, 255, 230)   # Strong: Cyan / Xanh biển
                elif i == 2:
                    color = QColor(255, 215, 0, 210)   # Alternative: Vàng hoàng kim
                else:
                    color = QColor(255, 82, 82, 210)   # Risky: Đỏ san hô
                    
                line_width = max(3.0, 5.5 * scale_x)
                pen = QPen(color, line_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                
                p1 = QPoint(int(final_start_x), int(final_start_y))
                p2 = QPoint(int(final_end_x), int(final_end_y))
                
                # Thân mũi tên
                painter.drawLine(p1, p2)
                
                # Đầu mũi tên
                self._draw_arrow_head(painter, p1, p2, color, scale_x)
                
                # Badge hiển thị điểm số (Score Pill)
                score_str = str(score)
                font_size = max(8, int(10 * scale_x))
                badge_font = QFont("Segoe UI", font_size, QFont.Bold)
                painter.setFont(badge_font)
                
                text_w = int(len(score_str) * font_size * 0.75 + 10)
                text_h = int(font_size * 1.6)
                badge_x = int(p2.x() + 8 * scale_x)
                badge_y = int(p2.y() - text_h // 2)
                
                # Đảm bảo badge nằm gọn trong bàn cờ
                badge_x = min(badge_x, board_rect.right() - text_w - 2)
                badge_x = max(badge_x, board_rect.left() + 2)
                badge_y = min(badge_y, board_rect.bottom() - text_h - 2)
                badge_y = max(badge_y, board_rect.top() + 2)
                
                badge_rect = QRect(badge_x, badge_y, text_w, text_h)
                painter.setPen(QPen(color, 1.2))
                painter.setBrush(QColor(15, 20, 28, 220))
                painter.drawRoundedRect(badge_rect, 4, 4)
                
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(badge_rect, Qt.AlignCenter, score_str)

        # 5. Icon góc kéo dãn kích thước (Resize Grip)
        grip_color = QColor(100, 110, 125, 180)
        painter.setPen(grip_color)
        for d in [4, 8, 12]:
            painter.drawLine(total_w - d, total_h - 2, total_w - 2, total_h - d)

    def _draw_arrow_head(self, painter, p1, p2, color, scale):
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        angle = math.atan2(dy, dx)
        
        arrow_size = max(10.0, 18.0 * scale)
        p_left = QPoint(
            int(p2.x() - arrow_size * math.cos(angle - math.pi / 6)),
            int(p2.y() - arrow_size * math.sin(angle - math.pi / 6))
        )
        p_right = QPoint(
            int(p2.x() - arrow_size * math.cos(angle + math.pi / 6)),
            int(p2.y() - arrow_size * math.sin(angle + math.pi / 6))
        )
        
        polygon = QPolygon([p2, p_left, p_right])
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(polygon)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Kiểm tra bấm nút đóng [X]
            close_rect = QRect(self.width() - 28, 6, 22, 22)
            if close_rect.contains(event.pos()):
                self.hide()
                return
                
            # Kiểm tra kéo dãn kích thước ở góc dưới phải
            corner_rect = QRect(self.width() - self.resize_margin, self.height() - self.resize_margin, self.resize_margin, self.resize_margin)
            if corner_rect.contains(event.pos()):
                self.is_resizing = True
                self.drag_position = event.globalPos()
            else:
                self.is_resizing = False
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            if self.is_resizing:
                delta = event.globalPos() - self.drag_position
                new_w = max(self.minimumWidth(), self.width() + delta.x())
                # Giữ tỷ lệ bàn cờ xấp xỉ vuông
                new_board = new_w
                new_h = new_board + self.header_height
                self.resize(new_w, new_h)
                self.drag_position = event.globalPos()
            else:
                self.move(event.globalPos() - self.drag_position)
        else:
            # Đổi con trỏ chuột khi lướt qua góc resize
            corner_rect = QRect(self.width() - self.resize_margin, self.height() - self.resize_margin, self.resize_margin, self.resize_margin)
            if corner_rect.contains(event.pos()):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_resizing = False
            self.drag_position = None
            self.setCursor(Qt.ArrowCursor)

    def showEvent(self, event):
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.visibility_changed.emit(False)
