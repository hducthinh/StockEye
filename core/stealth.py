import ctypes
import os
import time
from PyQt5.QtCore import QObject, pyqtSlot

class StealthController(QObject):
    def __init__(self, worker, control_panel, overlay, share_board=None):
        super().__init__()
        self.worker = worker
        self.control_panel = control_panel
        self.overlay = overlay
        self.share_board = share_board
        
        self.is_stealth = False
        self.was_control_panel_visible = True
        self.was_share_board_visible = False
        self.was_overlay_visible = True
        self.was_worker_paused = False
        self.saved_console_hwnds = []
        
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

    def get_console_hwnds(self):
        """
        Lấy danh sách HWND của Console Window.
        Hỗ trợ cả CMD, PowerShell truyền thống và Windows Terminal (wt.exe).
        """
        hwnds = set()
        try:
            hwnd = self.kernel32.GetConsoleWindow()
            if hwnd and self.user32.IsWindow(hwnd):
                hwnds.add(hwnd)
                # Lấy cả cửa sổ root ancestor phòng trường hợp nhúng trong Windows Terminal
                GA_ROOT = 2
                root = self.user32.GetAncestor(hwnd, GA_ROOT)
                if root and self.user32.IsWindow(root):
                    hwnds.add(root)
        except Exception as e:
            pass
        return list(hwnds)

    @pyqtSlot()
    def toggle_stealth(self):
        """Chuyển đổi trạng thái Ẩn / Hiện khi bấm F10"""
        if self.is_stealth:
            self.show_all()
        else:
            self.hide_all()

    def hide_all(self):
        """
        ẨN TOÀN BỘ TOOL:
        - Ẩn màn hình (Control Panel, Overlay, Share Board, Console Window).
        - Ẩn khỏi Taskbar.
        - Ẩn khỏi mục 'Apps' của Task Manager.
        - Đưa CPU về 0.0% để chìm xuống đáy danh sách Task Manager.
        """
        if self.is_stealth:
            return
        self.is_stealth = True
        
        # 1. Ghi nhớ trạng thái các thành phần trước khi ẩn
        self.was_control_panel_visible = self.control_panel.isVisible() if self.control_panel else False
        self.was_share_board_visible = self.share_board.isVisible() if self.share_board else False
        self.was_overlay_visible = self.overlay.isVisible() if self.overlay else False
        self.was_worker_paused = self.worker.is_paused
        
        # 2. Ẩn Console Window (CMD / Terminal)
        self.saved_console_hwnds = []
        hwnds = self.get_console_hwnds()
        for hwnd in hwnds:
            if self.user32.IsWindowVisible(hwnd):
                self.saved_console_hwnds.append(hwnd)
                # SW_HIDE = 0: Ẩn khỏi màn hình & xóa khỏi Taskbar & xóa khỏi Task Manager Apps
                self.user32.ShowWindow(hwnd, 0)
                
        # 3. Ẩn cửa sổ Control Panel và Bàn cờ phụ (Share Board)
        # Không ẩn Overlay vì Overlay là cửa sổ tàng hình (Qt.Tool), không hiện ở Taskbar/Task Manager
        # Nhờ vậy khi bấm 1 (Bật) và 2 (Gợi ý), mũi tên vẫn vẽ lên bàn cờ để người dùng nhìn thấy
        if self.share_board:
            self.share_board.hide()
            
        if self.control_panel:
            self.control_panel.hide()
            
        # 4. Giữ Worker hoạt động ngầm bình thường (Không pause, không đóng băng click queue)
        self.worker.is_stealth_active = True
        
        if hasattr(self.control_panel, "update_stealth_btn_style"):
            self.control_panel.update_stealth_btn_style(True)

    def show_all(self):
        """
        HIỆN LẠI TOÀN BỘ TOOL:
        - Khôi phục cửa sổ Console, Control Panel, Overlay, Share Board.
        - Phục hồi lại trạng thái hoạt động trước đó của Worker.
        """
        if not self.is_stealth:
            return
        self.is_stealth = False
        
        # 1. Hiện lại Console Window
        for hwnd in self.saved_console_hwnds:
            if self.user32.IsWindow(hwnd):
                self.user32.ShowWindow(hwnd, 5) # SW_SHOW
                self.user32.ShowWindow(hwnd, 9) # SW_RESTORE
                self.user32.SetForegroundWindow(hwnd)
                
        # 2. Hiện lại các cửa sổ PyQt
        if self.control_panel and self.was_control_panel_visible:
            self.control_panel.show()
            self.control_panel.raise_()
            self.control_panel.activateWindow()
            
        if self.share_board and self.was_share_board_visible:
            self.share_board.show()
            
        if self.overlay and self.was_overlay_visible:
            self.overlay.show()
            
        # 3. Phục hồi trạng thái hiển thị
        self.worker.is_stealth_active = False
            
        if self.control_panel:
            if hasattr(self.control_panel, "update_toggle_btn_style"):
                self.control_panel.update_toggle_btn_style()
            if hasattr(self.control_panel, "update_suggest_btn_style"):
                self.control_panel.update_suggest_btn_style(self.worker.config_data.get("suggest_mode", True))
            if hasattr(self.control_panel, "update_autoplay_btn_style"):
                self.control_panel.update_autoplay_btn_style(self.worker.config_data.get("autoplay", False))
            if hasattr(self.control_panel, "update_stealth_btn_style"):
                self.control_panel.update_stealth_btn_style(False)
