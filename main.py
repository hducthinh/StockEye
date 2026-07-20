import sys
import signal
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt

from core.capture import BoardCapture
from core.engine_logic import ChessEngine
from core.mouse import MouseController
from core.worker import ChessWorker
from ui.overlay import OverlayUI
from ui.control_panel import ControlPanelUI

def main():
    # Cho phép thoát bằng Ctrl+C trên terminal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception as e:
        print(f"Không thể thiết lập DPI Aware: {e}")
        
    app = QApplication(sys.argv)
    
    # Đồng bộ tín hiệu ngắt với vòng lặp PyQt5
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)
    
    # Khởi tạo hệ thống xử lý ảnh và xác định vùng bàn cờ
    capture = BoardCapture()
    try:
        capture.select_roi()
    except Exception as e:
        print(f"Lỗi khởi tạo Capture: {e}")
        sys.exit(1)
        
    # Khởi tạo Engine Stockfish
    try:
        engine = ChessEngine()
    except Exception as e:
        print(f"Lỗi khởi tạo Engine: {e}")
        sys.exit(1)
        
    # Khởi tạo bộ điều khiển chuột và luồng xử lý chính
    mouse_controller = MouseController(capture)
    worker = ChessWorker(capture, engine, mouse_controller)
    mouse_controller.worker = worker
    worker.start()
    
    # Khởi tạo giao diện người dùng
    overlay = OverlayUI()
    overlay.show()
    
    control_panel = ControlPanelUI(worker)
    control_panel.show()
    
    # Kết nối các tín hiệu (signals) giữa Worker và UI
    worker.moves_ready.connect(overlay.update_moves, Qt.QueuedConnection)
    worker.exit_app_signal.connect(control_panel.close, Qt.QueuedConnection)
    worker.toggle_pause_signal.connect(control_panel.toggle_tool, Qt.QueuedConnection)
    
    print("\n[System] Phần mềm đã sẵn sàng. Hãy bấm [1] BẬT / TẮT hoặc dùng Control Panel để bắt đầu.")
    
    exit_code = app.exec_()
    
    print("\n[Main] Đang dọn dẹp tài nguyên...")
    worker.running = False
    worker.wait()
    try:
        engine.close()
    except:
        pass
    import os
    os._exit(exit_code)

if __name__ == "__main__":
    main()
