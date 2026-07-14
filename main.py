import sys
import time
import signal
import cv2
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

from capture import BoardCapture
from engine_logic import ChessEngine
from overlay import OverlayUI
import queue

class ChessWorker(QThread):
    # Signal truyền List các nước đi đã chuyển đổi sang tọa độ Pixel lên UI
    # Định dạng: [((sx, sy), (ex, ey), score), ...]
    moves_ready = pyqtSignal(list)

    def __init__(self, capture, engine):
        super().__init__()
        self.capture = capture
        self.engine = engine
        self.running = True
        self.reset_request = None
        self.manual_move_request = None
        self.midgame_sync_request = False
        
        self.analysis_queue = queue.Queue()
        
        # Đăng ký phím tắt toàn cục (Global Hotkeys)
        import keyboard
        keyboard.on_press_key("f2", lambda _: self.request_reset())
        keyboard.on_press_key("1", lambda _: self.request_midgame_sync(turn="w"))
        keyboard.on_press_key("2", lambda _: self.request_midgame_sync(turn="b"))

    def request_reset(self):
        self.reset_request = True

    def request_midgame_sync(self, turn):
        self.midgame_sync_request = turn

    def square_to_pixel(self, sq):
        """
        Hàm ngược của pixel_to_square: 
        Chuyển ô cờ (vd 'e2') sang tọa độ Pixel tuyệt đối trên màn hình
        """
        if self.capture.player_color == "black":
            # Phe Đen: Góc trái trên là h1, góc phải dưới là a8
            col_idx = ord('h') - ord(sq[0])
            y_idx = int(sq[1]) - 1
        else:
            # Phe Trắng: Góc trái trên là a8, góc phải dưới là h1
            col_idx = ord(sq[0]) - ord('a')
            y_idx = 8 - int(sq[1])
            
        # Tính toán tọa độ trung tâm của ô cờ (Tương đối so với BBox)
        rel_x = (col_idx * self.capture.sq_width) + (self.capture.sq_width / 2)
        rel_y = (y_idx * self.capture.sq_height) + (self.capture.sq_height / 2)
        
        # Cộng thêm độ lệch tuyệt đối của BBox so với màn hình
        abs_x = self.capture.bbox["left"] + rel_x
        abs_y = self.capture.bbox["top"] + rel_y
        
        return (abs_x, abs_y)

    def run(self):
        print("\n[Worker] Bắt đầu theo dõi bàn cờ...")
        print("="*40)
        print("🔥 [HOTKEY CỜ CHỚP] 🔥")
        print(" - Nhấn phím F2: Bắt đầu ván MỚI (Phe sẽ được lấy từ file config.json)")
        print(" - Nhấn phím 1: Quét ảnh & Gợi ý nước cờ cho TRẮNG")
        print(" - Nhấn phím 2: Quét ảnh & Gợi ý nước cờ cho ĐEN")
        print(" - Cấu hình sức mạnh/thời gian tự động cập nhật khi bạn lưu file config.json")
        print(" - Nhấn Ctrl+C ở Terminal để thoát")
        print("\n💡 MẸO: Nếu bị lỡ nước đi, bạn có thể GÕ TRỰC TIẾP nước đi (vd: e2e4) vào Terminal này rồi nhấn Enter để đồng bộ lại!")
        print("="*40)
        
        prev_img = self.capture.get_board_image()
        last_stable_img = prev_img
        pre_move_img = prev_img
        stable_counter = 0
        last_failed_squares = None
        
        # Khi bắt đầu (thế cờ chuẩn), lấy nước đi gợi ý mở màn luôn
        self.analysis_queue.put(True)

        import os
        import threading
        config_mtime = os.path.getmtime("config.json") if os.path.exists("config.json") else 0
        last_config_check = time.time()
        
        # Thread đọc input từ Terminal
        def terminal_listener():
            while self.running:
                try:
                    cmd = input().strip().lower()
                    if len(cmd) >= 4 and self.running:
                        self.manual_move_request = cmd
                except:
                    pass
        
        threading.Thread(target=terminal_listener, daemon=True).start()
        
        # Thread phân tích Stockfish độc lập
        def analysis_worker():
            while self.running:
                try:
                    self.analysis_queue.get(timeout=0.1)
                    # Xả toàn bộ hàng đợi để chỉ xử lý trạng thái mới nhất
                    while not self.analysis_queue.empty():
                        self.analysis_queue.get_nowait()
                    self.process_and_emit_top_moves()
                except queue.Empty:
                    pass
                except Exception as e:
                    print(f"[Worker Error] {e}")

        threading.Thread(target=analysis_worker, daemon=True).start()
        
        while self.running:
            if self.reset_request:
                self.reset_request = False
                
                # Chụp ảnh bàn cờ hiện tại
                curr_img = self.capture.get_board_image()
                
                # Tự động nhận diện màu quân
                detected_color = self.capture.auto_detect_color(curr_img)
                self.capture.player_color = detected_color
                
                # Cập nhật màu vào config để đồng bộ
                try:
                    import json
                    with open("config.json", "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    cfg["player_color"] = detected_color
                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=4)
                except:
                    pass
                    
                self.engine.reset_board()
                self.engine.white_moves = []
                self.engine.black_moves = []
                self.manual_move_request = None
                
                # Phát âm báo hiệu
                import winsound
                freq = 1000 if self.capture.player_color == "white" else 800
                winsound.Beep(freq, 200)
                print(f"\n[System] ĐÃ RESET VÁN MỚI! TỰ ĐỘNG NHẬN DIỆN BẠN CẦM QUÂN: {self.capture.player_color.upper()}")
                
                # Cập nhật lại màn hình tĩnh
                last_stable_img = curr_img
                pre_move_img = curr_img
                last_failed_squares = None
                
                # [SỬA LỖI] Bắt buộc phải cập nhật prev_img, nếu không OpenCV sẽ 
                # trừ ảnh ván mới cho ảnh ván cũ và gây ra rác toàn bàn cờ!
                prev_img = curr_img
                
                self.analysis_queue.put(True)
                continue
                
            if self.midgame_sync_request:
                turn_to_move = self.midgame_sync_request
                self.midgame_sync_request = False
                
                print(f"\n[System] ĐANG QUÉT ẢNH VÀ TÌM NƯỚC CHO {'TRẮNG' if turn_to_move == 'w' else 'ĐEN'}...")
                curr_img = self.capture.get_board_image()
                
                # Tự động nhận diện màu quân cờ hiện tại
                try:
                    detected_color = self.capture.auto_detect_color(curr_img)
                    self.capture.player_color = detected_color
                    
                    import json
                    with open("config.json", "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    
                    # Chúng ta ép player_color thành phe mà người dùng muốn lấy gợi ý
                    # Để UI mũi tên có thể vẽ đúng màu phe đó
                    cfg["player_color"] = "white" if turn_to_move == 'w' else "black"
                    self.capture.player_color = cfg["player_color"]
                    
                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=4)
                except:
                    pass
                
                # 1. Gọi hàm nhận diện hình ảnh để lấy chuỗi FEN
                detected_fen = self.capture.image_to_fen(curr_img, turn_to_move=turn_to_move) 
                print(f"[Debug] image_to_fen returned: {detected_fen}")
                
                if detected_fen:
                    try:
                        # 2. Xóa lịch sử cũ, ép Stockfish nhận thế cờ mới
                        self.engine.board.set_fen(detected_fen)
                        
                        if not self.engine.board.is_valid():
                            print(f"\n[!] Bàn cờ không hợp lệ (Có thể do lỗi ảnh hoặc sai lượt). Vui lòng quét lại!\n")
                            continue
                            
                        self.engine.white_moves = []
                        self.engine.black_moves = []
                        
                        # 3. Cập nhật lại các biến theo dõi ảnh để không bị lỗi nhiễu pixel
                        prev_img = curr_img
                        last_stable_img = curr_img
                        pre_move_img = curr_img
                        last_failed_squares = None
                        
                        # Phát âm báo hiệu
                        import winsound
                        winsound.Beep(1200, 300)
                        
                        # Buộc cập nhật UI NGAY LẬP TỨC
                        self.process_and_emit_top_moves()
                    except ValueError as e:
                        print(f"\n\n[System] Lỗi khi đồng bộ FEN: Chuỗi FEN không hợp lệ! ({e})\n\n")
                    except Exception as e:
                        print(f"\n\n[System] Lỗi không xác định khi set_fen: {e}\n\n")
                else:
                    print("[!] Lỗi: Nhận diện hình ảnh thất bại.")
                
                continue
                
            time.sleep(0.016) # ~60 fps
            
            # Kiểm tra config.json thay đổi mỗi giây
            if time.time() - last_config_check > 1.0:
                last_config_check = time.time()
                try:
                    current_mtime = os.path.getmtime("config.json")
                    if current_mtime > config_mtime:
                        config_mtime = current_mtime
                        self.engine.reload_config()
                        import winsound
                        winsound.Beep(1500, 100)
                except:
                    pass
                    
            # Kiểm tra xem người dùng có nhập lệnh hoặc nước đi thủ công không
            if self.manual_move_request:
                cmd_str = self.manual_move_request
                self.manual_move_request = None
                
                if cmd_str in ["white", "black"]:
                    self.capture.player_color = cmd_str
                    self.engine.reset_board()
                    self.engine.white_moves = []
                    self.engine.black_moves = []
                    
                    # Cập nhật cả vào file config để lưu lại
                    try:
                        import json
                        with open("config.json", "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                        cfg["player_color"] = cmd_str
                        with open("config.json", "w", encoding="utf-8") as f:
                            json.dump(cfg, f, indent=4)
                    except:
                        pass
                        
                    print(f"\n[System] ĐÃ ĐỔI PHE VÀ RESET VÁN MỚI! BẠN ĐANG CẦM QUÂN: {cmd_str.upper()}")
                    
                    curr_img = self.capture.get_board_image()
                    last_stable_img = curr_img
                    last_failed_squares = None
                    self.analysis_queue.put(True)
                else:
                    try:
                        import chess
                        move = chess.Move.from_uci(cmd_str)
                        if move in self.engine.board.legal_moves:
                            if self.engine.board.turn == chess.WHITE:
                                self.engine.white_moves.append(move)
                            else:
                                self.engine.black_moves.append(move)
                            self.engine.board.push(move)
                            print(f"\n[System] Đã nạp tay nước đi: {cmd_str}")
                            
                            curr_img = self.capture.get_board_image()
                            last_stable_img = curr_img
                            pre_move_img = curr_img
                            last_failed_squares = None
                            
                            self.analysis_queue.put(True)
                        else:
                            print(f"\n[!] Lỗi: Nước đi '{cmd_str}' KHÔNG hợp lệ với bàn cờ hiện tại.")
                    except Exception as e:
                        print(f"\n[!] Cú pháp không hợp lệ. Vui lòng gõ 'white', 'black' hoặc chuẩn UCI (vd: e2e4).")
            
            curr_img = self.capture.get_board_image()
            
            # --- THUẬT TOÁN CHỐNG ẢO GIÁC HOẠT ẢNH TRƯỢT (ANTI-DRAG & ANTI-ANIMATION) ---
            import cv2
            import numpy as np
            diff = cv2.absdiff(prev_img, curr_img)
            gray = np.max(diff, axis=2).astype(np.uint8)
            
            # [SỬA ĐỔI 3] Đồng bộ ngưỡng 40 với capture.py
            _, thresh = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)
            motion_pixels = cv2.countNonZero(thresh)
            
            # [SỬA ĐỔI 4] Nâng ngưỡng motion_pixels lên 50 để tránh nhiễu li ti
            if motion_pixels > 50: 
                stable_counter = 0
            else:
                stable_counter += 1
                
            # [SỬA ĐỔI 5] Cấu hình ép xung: Sử dụng stable_frames từ config (mặc định 4 frames)
            stable_frames = self.engine.config.get("stable_frames", 4)
            if stable_counter >= stable_frames:
                # Lúc này hoạt ảnh đã xong hoàn toàn. 
                # So sánh frame tĩnh hiện tại với frame tĩnh TRƯỚC KHI quân cờ bắt đầu di chuyển
                changed_squares_stable = self.capture.detect_move(last_stable_img, curr_img)
                
                if changed_squares_stable and len(changed_squares_stable) >= 2:
                    pushed_moves = self.engine.infer_and_push_move(changed_squares_stable)
                    
                    if pushed_moves:
                        self.analysis_queue.put(True)
                        # Lưu lại ảnh TRƯỚC KHI cập nhật mốc mới để đối chiếu nếu bị Hover Cancel
                        pre_move_img = last_stable_img
                        # Cập nhật mốc tĩnh mới vì đã áp dụng nước đi thành công!
                        last_stable_img = curr_img
                        # Đã áp dụng xong, ẩn cảnh báo cũ đi
                        last_failed_squares = None
                    else:
                        # Kiểm tra xem đây có phải là Hover Cancel (Thả quân về chỗ cũ) không
                        is_potential_cancel = self.engine.is_potential_hover_cancel(changed_squares_stable)
                        
                        if is_potential_cancel:
                            # Xác nhận lại bằng hình ảnh: Nếu thực sự là Hover Cancel, 
                            # thì curr_img hiện tại phải giống hệt với pre_move_img (lúc chưa đi)!
                            import cv2
                            import numpy as np
                            diff_with_pre = cv2.absdiff(pre_move_img, curr_img)
                            gray_pre = np.max(diff_with_pre, axis=2).astype(np.uint8)
                            _, thresh_pre = cv2.threshold(gray_pre, 30, 255, cv2.THRESH_BINARY)
                            diff_pixels = cv2.countNonZero(thresh_pre)
                            
                            if diff_pixels < 500: # Rất giống ảnh trước khi đi -> Đúng là đã Undo
                                self.engine.undo_last_move()
                                last_stable_img = curr_img
                                last_failed_squares = None
                            else:
                                # Ảnh không giống lúc trước khi đi -> Đây chỉ là dư âm của hoạt ảnh!
                                # Đừng undo, chỉ lọc rác
                                if changed_squares_stable != last_failed_squares:
                                    print(f"[Worker] Đã lọc rác/hoạt ảnh lơ lửng sau nước đi: {changed_squares_stable}")
                                    last_failed_squares = changed_squares_stable
                        elif changed_squares_stable != last_failed_squares:
                            print(f"[Worker] Đã lọc rác/hoạt ảnh lơ lửng: {changed_squares_stable}")
                            last_failed_squares = changed_squares_stable
                            
            prev_img = curr_img
                
    def process_and_emit_top_moves(self):
        """Hỏi Stockfish và đẩy kết quả lên UI"""
        top_moves = self.engine.get_top_moves(limit=3)
        
        if not top_moves:
            return
            
        ui_data = []
        for item in top_moves:
            m = item["move"] # 'e2e4'
            score = item["score"]
            
            start_sq = m[:2]
            end_sq = m[2:4]
            
            try:
                start_px = self.square_to_pixel(start_sq)
                end_px = self.square_to_pixel(end_sq)
                ui_data.append((start_px, end_px, score))
            except Exception as e:
                print(f"[Worker] Lỗi convert tọa độ: {e}")
                
        # Phát tín hiệu an toàn qua thread ranh giới (cross-thread)
        self.moves_ready.emit(ui_data)

if __name__ == "__main__":
    # Cứu tinh cho Ctrl+C: Ép PyQt5 nhường quyền quản lý ngắt hệ thống (SIGINT) lại cho Python
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    
    # Đảm bảo Ctrl+C hoạt động ngay cả khi vòng lặp PyQt đang chạy
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)
    
    # 1. Khởi tạo Capture và yêu cầu user quét chọn vùng bàn cờ
    capture = BoardCapture()
    try:
        capture.select_roi()
    except Exception as e:
        print(f"Lỗi khởi tạo Capture: {e}")
        sys.exit(1)
        
    # 2. Khởi tạo Bộ não Stockfish
    engine = ChessEngine()
    if not engine.engine:
        print("Vui lòng tải file stockfish-windows-x86-64-avx2.exe và bỏ vào thư mục engine/ nhé!")
        sys.exit(1)
        
    # 3. Khởi tạo Giao diện Overlay
    overlay = OverlayUI()
    overlay.show()
    overlay.raise_()
    overlay.activateWindow()
    
    # 4. Tạo và chạy Luồng phụ (Worker) để xử lý CV & Engine ngầm
    worker = ChessWorker(capture, engine)
    worker.moves_ready.connect(overlay.update_moves) # Nối Signal của Worker vào hàm vẽ của UI
    worker.start()
    
    # 5. Chạy Event Loop của PyQt (Giữ cửa sổ UI sống)
    exit_code = app.exec_()
    
    # 6. Dọn dẹp tài nguyên khi user đóng app
    print("\n[Main] Đang dọn dẹp tài nguyên...")
    worker.running = False
    worker.wait()
    engine.close()
    sys.exit(exit_code)
