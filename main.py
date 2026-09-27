import sys
import os
import signal

# Bảo vệ an toàn khi chạy chế độ không có terminal (--noconsole / GUI app)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure') and stream is not None:
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

# Ẩn hoàn toàn cửa sổ terminal nếu chạy từ file exe đóng gói
if getattr(sys, 'frozen', False):
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt

from core.capture import BoardCapture
from core.engine_logic import ChessEngine
from core.worker import ChessWorker
from core.process_guard import init_process_guard
from ui.overlay import OverlayUI
from ui.control_panel import ControlPanelUI

def main():
    # Khởi tạo bảo vệ tiến trình (Job Object + Dọn dẹp engine cũ sót lại)
    init_process_guard()

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
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Lỗi khởi tạo bàn cờ:\n{e}\n\nVui lòng chạy file auto_setup.exe để cài đặt bàn cờ trước!", "StockEye - Lỗi Khởi Tạo", 0x10)
        except Exception:
            pass
        sys.exit(1)
        
    # Khởi tạo Engine Stockfish
    try:
        engine = ChessEngine()
    except Exception as e:
        print(f"Lỗi khởi tạo Engine: {e}")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Lỗi khởi tạo Engine:\n{e}", "StockEye - Lỗi Engine", 0x10)
        except Exception:
            pass
        sys.exit(1)
        
    # Khởi tạo luồng xử lý chính (ChessWorker)
    worker = ChessWorker(capture, engine)
    worker.start()
    
    # Khởi tạo giao diện người dùng
    overlay = OverlayUI()
    overlay.show()
    
    from ui.share_board import ShareableBoardUI
    share_board = ShareableBoardUI(capture)
    if worker.config_data.get("show_share_board", True):
        share_board.show()
    
    control_panel = ControlPanelUI(worker, share_board=share_board, overlay=overlay)
    control_panel.show()
    
    # Kết nối các tín hiệu (signals) giữa Worker và UI
    worker.moves_ready.connect(overlay.update_moves, Qt.QueuedConnection)
    worker.moves_ready.connect(share_board.update_moves, Qt.QueuedConnection)
    worker.exit_app_signal.connect(control_panel.close, Qt.QueuedConnection)
    
    # Khởi tạo bộ điều khiển Stealth Mode (F10 Boss Key)
    from core.stealth import StealthController
    stealth_controller = StealthController(worker, control_panel, overlay, share_board=share_board)
    worker.toggle_stealth_signal.connect(stealth_controller.toggle_stealth, Qt.QueuedConnection)
    
    print("\n[System] Phần mềm đã sẵn sàng. Hãy bấm [2] để BẬT / TẮT GỢI Ý hoặc dùng Control Panel.")
    print("[System] Phím tắt [F10]: ẨN / HIỆN TOÀN BỘ TOOL (Stealth Mode: Ẩn màn hình, Taskbar & Task Manager - Ngụy trang chrome.exe).")
    
    exit_code = app.exec_()
    
    print("\n[Main] Đang dọn dẹp tài nguyên...")
    worker.running = False
    worker.wait(300)
    try:
        engine.close()
    except Exception as e:
        print(f"[Main] Lỗi đóng engine: {e}")
    import os
    os._exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
