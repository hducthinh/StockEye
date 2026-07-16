import sys
import time
import signal
import cv2
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox, QFormLayout, QLabel
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt

from capture import BoardCapture
from engine_logic import ChessEngine
from overlay import OverlayUI
import queue

class ChessWorker(QThread):
    # Signal truyền List các nước đi đã chuyển đổi sang tọa độ Pixel lên UI
    # Định dạng: [((sx, sy), (ex, ey), score), ...]
    moves_ready = pyqtSignal(list)
    toggle_pause_signal = pyqtSignal()
    autoplay_ui_signal = pyqtSignal(bool)

    def __init__(self, capture, engine):
        super().__init__()
        self.capture = capture
        self.engine = engine
        self.running = True
        self.manual_move_request = None
        self.midgame_sync_request = False
        self.is_paused = True
        
        self.analysis_queue = queue.Queue()
        self.click_queue = queue.Queue()
        self.current_time_left = 60.0
        
        import json, os
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
            except:
                self.config_data = {}
        else:
            self.config_data = {}
            
        # Ép mặc định khi khởi động là tắt Autoplay
        self.config_data["autoplay"] = False
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
        except:
            pass

        def kill_switch(_):
            print("[Kill Switch] Hủy bỏ Autoplay và xóa hàng đợi click!")
            self.is_paused = True
            with self.click_queue.mutex:
                self.click_queue.queue.clear()
            self.toggle_pause_signal.emit()

        # Đăng ký phím tắt toàn cục (Global Hotkeys)
        import keyboard
        keyboard.on_press_key("1", lambda _: self.toggle_pause_signal.emit())
        keyboard.on_press_key("esc", kill_switch)
        keyboard.on_press_key("2", lambda _: self.request_midgame_sync(turn="auto_suggest"))
        keyboard.on_press_key("3", lambda _: self.request_midgame_sync(turn="auto"))

    def request_midgame_sync(self, turn):
        if self.is_paused:
            print("\n[!] Lệnh bị từ chối: Vui lòng BẬT (phím 1) tool trước khi sử dụng phím 2 hoặc 3!")
            return
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
        print(" - Nhấn phím 1: Bật / Tắt tạm dừng để vẽ chiến thuật")
        print(" - Nhấn phím 2: Tự động nhận diện Phe & Gợi ý nước cờ")
        print(" - Nhấn phím 3: Tự động nhận diện Phe & Bật Autoplay ngay lập tức")
        print(" - Nhấn phím ESC: Kill Switch (Tắt và xóa lệnh chuột ngay lập tức)")
        print(" - Cấu hình sức mạnh/thời gian tự động cập nhật khi bạn lưu file config.json")
        print(" - Nhấn Ctrl+C ở Terminal để thoát")
        print("\n💡 MẸO: Nếu bị lỡ nước đi, bạn có thể GÕ TRỰC TIẾP nước đi (vd: e2e4) vào Terminal này rồi nhấn Enter để đồng bộ lại!")
        print("="*40)
        
        prev_img = self.capture.get_board_image()
        last_stable_img = prev_img
        pre_move_img = prev_img
        stable_counter = 0
        last_failed_squares = None
        
        # Không lấy nước đi mở màn tự động nữa vì mặc định tool đang Tạm dừng
        # self.analysis_queue.put(True)

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
        
        # Thread OCR Đồng hồ độc lập (Clock Worker)
        def clock_worker():
            while self.running:
                try:
                    time_left = self.capture.get_remaining_time()
                    if time_left is not None:
                        self.current_time_left = time_left
                    time.sleep(0.1) # Quét đồng hồ mỗi 100ms
                except Exception:
                    time.sleep(0.5)
        threading.Thread(target=clock_worker, daemon=True).start()
        
        # Thread điều khiển chuột (Click Worker)
        def click_worker():
            import ctypes
            import random
            import math
            import time
            import chess
            
            def move_and_click(px_x, px_y, delay, travel_time):
                # Random offset 15-20%
                offset_limit = self.capture.sq_width * 0.15
                rx = px_x + random.uniform(-offset_limit, offset_limit)
                ry = px_y + random.uniform(-offset_limit, offset_limit)
                
                time.sleep(travel_time)
                ctypes.windll.user32.SetCursorPos(int(rx), int(ry))
                
                # Click (Down, sleep 20-50ms, Up)
                ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0) # LEFTDOWN
                time.sleep(random.uniform(0.02, 0.05))
                ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0) # LEFTUP
                
            while self.running:
                try:
                    task = self.click_queue.get(timeout=0.1)
                    start_sq = task["start_sq"]
                    end_sq = task["end_sq"]
                    start_px = task["start_px"]
                    end_px = task["end_px"]
                    decision_fen = task["decision_fen"]
                    is_scramble = task["is_scramble"]
                    ctx = task["context"]
                    
                    # Double check FEN
                    with self.engine.lock:
                        current_fen = self.engine.board.fen()
                    if current_fen != decision_fen:
                        print("[ClickWorker] FEN mismatch (Opponent moved?). Hủy click.")
                        continue
                        
                    bot_delay = self.config_data.get("bot_delay", 0.15)
                    
                    # Fitts Law approximation for travel time (luôn áp dụng)
                    dist = math.hypot(end_px[0] - start_px[0], end_px[1] - start_px[1])
                    dist_squares = dist / self.capture.sq_width
                    travel_time = 0.05 + (dist_squares * 0.015)
                    
                    action_log = "Normal"
                    
                    # Quy tắc Tối thượng: Time Scramble (Hard-Override)
                    if is_scramble:
                        reaction_time = max(0.01, random.gauss(0.05, 0.02)) + bot_delay * 0.2
                        travel_time = 0.02
                        action_log = "Scramble"
                    else:
                        # 4 Lớp Màng Lọc Ngữ Cảnh
                        # Bước 4: Hesitation (Trượt chuột)
                        if random.random() < 0.03:
                            reaction_time = random.uniform(1.5, 3.0)
                            action_log = "Hesitation"
                        # Bước 2: Forced/Evasion
                        elif ctx["opponent_captured"]:
                            reaction_time = random.uniform(0.1, 0.2)
                            action_log = "Recapture"
                        elif ctx["is_in_check"]:
                            if ctx["legal_moves_count"] <= 3:
                                reaction_time = random.uniform(0.1, 0.3)
                                action_log = "Instinct Evasion"
                            else:
                                reaction_time = random.uniform(0.5, 1.5)
                                action_log = "Calculated Evasion"
                        # Bước 3: Premove (15% ở Khai cuộc hoặc Tàn cuộc)
                        elif (ctx["fullmove_number"] <= 5 or ctx["fullmove_number"] > 35) and random.random() < 0.15:
                            reaction_time = random.uniform(0.01, 0.05)
                            action_log = "Premove"
                        # Bước 1: Game Phases (Bình thường)
                        else:
                            if ctx["fullmove_number"] <= 5:
                                reaction_time = max(0.01, random.gauss(bot_delay * 0.8, 0.05))
                            else:
                                reaction_time = max(0.01, random.gauss(bot_delay, 0.05))
                                # Tactical pause chance ở Trung/Tàn cuộc
                                if 6 <= ctx["fullmove_number"] <= 35 and random.random() < 0.15:
                                    reaction_time += random.uniform(0.5, 1.5)
                                    action_log = "Tactical Pause"

                    print(f"[ClickWorker] {action_log}! Executing {start_sq}{end_sq} (Reaction: {reaction_time:.2f}s, Travel: {travel_time:.2f}s, Scramble: {is_scramble})")
                    
                    time.sleep(reaction_time)
                    # Double check again just in case the long reaction time allowed opponent to move
                    with self.engine.lock:
                        current_fen = self.engine.board.fen()
                    if current_fen != decision_fen:
                        print("[ClickWorker] FEN mismatch sau reaction time. Hủy click.")
                        continue

                    # Execute clicks
                    move_and_click(start_px[0], start_px[1], 0, 0)
                    move_and_click(end_px[0], end_px[1], 0, travel_time)
                    
                    # Reset chuột về 1 góc để tránh hover tooltip che bàn cờ
                    time.sleep(0.05)
                    ctypes.windll.user32.SetCursorPos(10, 10)
                    
                except queue.Empty:
                    pass
                except Exception as e:
                    print(f"[ClickWorker Error] {e}")

        threading.Thread(target=click_worker, daemon=True).start()
        
        while self.running:
            if self.midgame_sync_request:
                turn_to_move = self.midgame_sync_request
                self.midgame_sync_request = False
                
                curr_img = self.capture.get_board_image()
                
                # Tự động nhận diện màu quân cờ hiện tại
                try:
                    detected_color = self.capture.auto_detect_color(curr_img)
                    self.capture.player_color = detected_color
                    
                    if turn_to_move in ["auto", "auto_suggest"]:
                        turn_to_move_resolved = 'w' if detected_color == 'white' else 'b'
                        
                        if turn_to_move == "auto":
                            # Bật Autoplay
                            self.is_paused = False
                            self.config_data["autoplay"] = True
                            self.autoplay_ui_signal.emit(True)
                            
                            import json
                            with open("config.json", "r", encoding="utf-8") as f:
                                cfg = json.load(f)
                            cfg["autoplay"] = True
                            with open("config.json", "w", encoding="utf-8") as f:
                                json.dump(cfg, f, indent=4)
                                
                            print(f"\n[System] ĐÃ BẬT AUTOPLAY! TỰ NHẬN DIỆN BẠN CẦM QUÂN: {'TRẮNG' if detected_color == 'white' else 'ĐEN'}")
                        else:
                            print(f"\n[System] TỰ NHẬN DIỆN BẠN CẦM QUÂN: {'TRẮNG' if detected_color == 'white' else 'ĐEN'} (Chỉ gợi ý)")
                            
                        turn_to_move = turn_to_move_resolved
                    
                    print(f"\n[System] ĐANG QUÉT ẢNH VÀ TÌM NƯỚC CHO {'TRẮNG' if turn_to_move == 'w' else 'ĐEN'}...")
                    
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
                        with self.engine.lock:
                            self.engine.board.set_fen(detected_fen)
                            is_valid = self.engine.board.is_valid()
                        
                        if not is_valid:
                            print(f"\n[!] Bàn cờ không hợp lệ (Có thể do lỗi ảnh hoặc sai lượt). Vui lòng quét lại!\n")
                            continue
                            
                        self.engine.white_moves = []
                        self.engine.black_moves = []
                        
                        # 3. Cập nhật lại các biến theo dõi ảnh để không bị lỗi nhiễu pixel
                        prev_img = curr_img
                        last_stable_img = curr_img
                        pre_move_img = curr_img
                        last_failed_squares = None
                        
                        # Phát âm báo hiệu (đã bị tắt)
                        # import winsound
                        # winsound.Beep(1200, 300)
                        
                        # Buộc cập nhật UI NGAY LẬP TỨC
                        self.process_and_emit_top_moves()
                    except ValueError as e:
                        print(f"\n\n[System] Lỗi khi đồng bộ FEN: Chuỗi FEN không hợp lệ! ({e})\n\n")
                    except Exception as e:
                        print(f"\n\n[System] Lỗi không xác định khi set_fen: {e}\n\n")
                else:
                    print("[!] Lỗi: Nhận diện hình ảnh thất bại.")
                
                continue
                
            if self.is_paused:
                time.sleep(0.1)
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
                        import json
                        with open("config.json", "r", encoding="utf-8") as f:
                            self.config_data = json.load(f)
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
                        with self.engine.lock:
                            is_legal = move in self.engine.board.legal_moves
                            board_turn = self.engine.board.turn
                        if is_legal:
                            if board_turn == chess.WHITE:
                                self.engine.white_moves.append(move)
                            else:
                                self.engine.black_moves.append(move)
                            with self.engine.lock:
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
                                    last_stable_img = curr_img
                        elif changed_squares_stable != last_failed_squares:
                            print(f"[Worker] Đã lọc rác/hoạt ảnh lơ lửng: {changed_squares_stable}")
                            last_failed_squares = changed_squares_stable
                            last_stable_img = curr_img
                            
            prev_img = curr_img
                
    def process_and_emit_top_moves(self):
        """Hỏi Stockfish và đẩy kết quả lên UI"""
        top_moves = self.engine.get_top_moves(limit=2)
        
        if not top_moves:
            return
            
        ui_data = []
        best_m = None
        for item in top_moves:
            m = item["move"] # 'e2e4' hoặc ['e2e4', 'e7e5', 'g1f3']
            score = item["score"]
            
            if best_m is None:
                best_m = m[0] if isinstance(m, list) else m
            
            try:
                if isinstance(m, list):
                    for move_str in m:
                        start_sq = move_str[:2]
                        end_sq = move_str[2:4]
                        start_px = self.square_to_pixel(start_sq)
                        end_px = self.square_to_pixel(end_sq)
                        ui_data.append((start_px, end_px, score))
                else:
                    start_sq = m[:2]
                    end_sq = m[2:4]
                    start_px = self.square_to_pixel(start_sq)
                    end_px = self.square_to_pixel(end_sq)
                    ui_data.append((start_px, end_px, score))
            except Exception as e:
                print(f"[Worker] Lỗi convert tọa độ: {e}")
                
        # Phát tín hiệu an toàn qua thread ranh giới (cross-thread)
        self.moves_ready.emit(ui_data)
        
        # Xử lý Autoplay
        import chess
        if self.config_data.get('autoplay', False) and not self.is_paused and best_m:
            is_our_turn = False
            with self.engine.lock:
                board_turn = self.engine.board.turn
            if board_turn == chess.WHITE and self.capture.player_color == "white":
                is_our_turn = True
            elif board_turn == chess.BLACK and self.capture.player_color == "black":
                is_our_turn = True
                
            if is_our_turn:
                start_sq = best_m[:2]
                end_sq = best_m[2:4]
                start_px = self.square_to_pixel(start_sq)
                end_px = self.square_to_pixel(end_sq)
                
                is_scramble = self.current_time_left < 15.0
                
                with self.click_queue.mutex:
                    self.click_queue.queue.clear()
                    
                with self.engine.lock:
                    context = {
                        "fullmove_number": self.engine.board.fullmove_number,
                        "is_in_check": self.engine.board.is_check(),
                        "opponent_captured": False,
                        "legal_moves_count": len(list(self.engine.board.legal_moves))
                    }
                    
                    # Check if opponent's last move was a capture
                    if len(self.engine.board.move_stack) > 0:
                        try:
                            last_move = self.engine.board.peek()
                            self.engine.board.pop()
                            context["opponent_captured"] = self.engine.board.is_capture(last_move)
                            self.engine.board.push(last_move)
                        except:
                            pass
                    decision_fen = self.engine.board.fen()
                
                click_task = {
                    "start_sq": start_sq,
                    "end_sq": end_sq,
                    "start_px": start_px,
                    "end_px": end_px,
                    "decision_fen": decision_fen,
                    "is_scramble": is_scramble,
                    "context": context
                }
                self.click_queue.put(click_task)

class ControlPanelUI(QWidget):
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.setWindowTitle("StockEye Control")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        self.resize(250, 300)
        
        layout = QVBoxLayout()
        
        # Form config
        form_layout = QFormLayout()
        
        import json
        self.config_path = "config.json"
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)
        except:
            self.config_data = {}

        # Autoplay (BOT Mode)
        self.chk_autoplay = QCheckBox()
        self.chk_autoplay.setChecked(self.config_data.get("autoplay", False))
        self.worker.autoplay_ui_signal.connect(self.chk_autoplay.setChecked, Qt.QueuedConnection)
        form_layout.addRow("Autoplay (BOT):", self.chk_autoplay)
        
        # Limit Strength (Checkbox) - Ép mặc định luôn BẬT
        self.config_data["uci_limit_strength"] = True
        self.chk_limit_strength = QCheckBox()
        self.chk_limit_strength.setChecked(True)
        form_layout.addRow("Limit Strength:", self.chk_limit_strength)
        
        # ELO (SpinBox)
        self.spin_elo = QSpinBox()
        self.spin_elo.setRange(1320, 4000)
        self.spin_elo.setValue(self.config_data.get("uci_elo", 2000))
        form_layout.addRow("UCI Elo:", self.spin_elo)
        
        # Human Error Rate (DoubleSpinBox)
        self.spin_error = QDoubleSpinBox()
        self.spin_error.setRange(0.0, 1.0)
        self.spin_error.setSingleStep(0.1)
        self.spin_error.setValue(self.config_data.get("human_error_rate", 0.2))
        form_layout.addRow("Error Rate:", self.spin_error)
        
        # Time Limit (DoubleSpinBox)
        self.spin_time = QDoubleSpinBox()
        self.spin_time.setRange(0.01, 10.0)
        self.spin_time.setSingleStep(0.05)
        self.spin_time.setValue(self.config_data.get("time_limit", 0.1))
        form_layout.addRow("Time Limit (s):", self.spin_time)
        
        # BOT Delay (DoubleSpinBox)
        self.spin_bot_delay = QDoubleSpinBox()
        self.spin_bot_delay.setRange(0.0, 2.0)
        self.spin_bot_delay.setSingleStep(0.1)
        self.spin_bot_delay.setValue(self.config_data.get("bot_delay", 0.15))
        form_layout.addRow("BOT Delay (s):", self.spin_bot_delay)
        
        layout.addLayout(form_layout)
        
        # Kết nối tín hiệu Limit Strength để bật/tắt các ô bên dưới
        self.chk_limit_strength.stateChanged.connect(self.toggle_strength_inputs)
        
        # Nút Lưu Settings
        self.btn_save = QPushButton("LƯU SETTINGS")
        self.btn_save.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")
        self.btn_save.clicked.connect(self.save_config)
        layout.addWidget(self.btn_save)
        
        # Nút Bật/Tắt
        self.btn_toggle = QPushButton()
        if self.worker.is_paused:
            self.btn_toggle.setText("[1] BẬT / TẮT: ĐÃ DỪNG")
            self.btn_toggle.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
        else:
            self.btn_toggle.setText("[1] BẬT / TẮT: ĐANG CHẠY")
            self.btn_toggle.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
            
        self.btn_toggle.clicked.connect(self.toggle_tool)
        layout.addWidget(self.btn_toggle)
        
        # Nút Gợi Ý
        self.btn_suggest = QPushButton("[2] GỢI Ý (Tự nhận diện phe)")
        self.btn_suggest.setStyleSheet("background-color: white; color: black; font-weight: bold; padding: 10px;")
        self.btn_suggest.clicked.connect(lambda: self.worker.request_midgame_sync("auto_suggest"))
        layout.addWidget(self.btn_suggest)
        
        # Nút Autoplay (Tự nhận diện)
        self.btn_auto = QPushButton("[3] AUTOPLAY (Tự nhận diện phe)")
        self.btn_auto.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; padding: 10px;")
        self.btn_auto.clicked.connect(lambda: self.worker.request_midgame_sync("auto"))
        layout.addWidget(self.btn_auto)
        
        self.setLayout(layout)
        
        # Cập nhật UI ban đầu
        self.toggle_strength_inputs()

    def toggle_strength_inputs(self):
        is_checked = self.chk_limit_strength.isChecked()
        self.spin_elo.setEnabled(is_checked)
        self.spin_error.setEnabled(is_checked)
        self.spin_time.setEnabled(is_checked)

    def save_config(self):
        import json
        self.config_data["autoplay"] = self.chk_autoplay.isChecked()
        self.config_data["uci_limit_strength"] = self.chk_limit_strength.isChecked()
        self.config_data["uci_elo"] = self.spin_elo.value()
        self.config_data["human_error_rate"] = self.spin_error.value()
        self.config_data["time_limit"] = round(self.spin_time.value(), 2)
        self.config_data["bot_delay"] = round(self.spin_bot_delay.value(), 2)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            print(f"Lỗi khi lưu config: {e}")

    def toggle_tool(self):
        self.worker.is_paused = not self.worker.is_paused
        if self.worker.is_paused:
            self.btn_toggle.setText("[1] BẬT / TẮT: ĐÃ DỪNG")
            self.btn_toggle.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
            self.worker.moves_ready.emit([]) # Xóa mũi tên cũ trên màn hình
            with self.worker.click_queue.mutex:
                self.worker.click_queue.queue.clear()
        else:
            self.btn_toggle.setText("[1] BẬT / TẮT: ĐANG CHẠY")
            self.btn_toggle.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")

    def closeEvent(self, event):
        """Bắt sự kiện đóng cửa sổ (nhấn X) để tắt toàn bộ chương trình"""
        print("\n[UI] Bảng điều khiển đã bị đóng. Đang thoát chương trình...")
        QApplication.instance().quit()
        event.accept()

if __name__ == "__main__":
    # Cứu tinh cho Ctrl+C: Ép PyQt5 nhường quyền quản lý ngắt hệ thống (SIGINT) lại cho Python
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception as e:
        print(f"Không thể thiết lập DPI Aware: {e}")
        
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
    worker.moves_ready.connect(overlay.update_moves, Qt.QueuedConnection) # Nối Signal của Worker vào hàm vẽ của UI
    worker.start()
    
    # [Thêm đoạn này] Khởi tạo Bảng điều khiển
    control_panel = ControlPanelUI(worker)
    control_panel.show()
    
    # Kết nối phím tắt ` tới nút Bật/Tắt UI
    worker.toggle_pause_signal.connect(control_panel.toggle_tool)
    
    # 5. Chạy Event Loop của PyQt (Giữ cửa sổ UI sống)
    exit_code = app.exec_()
    
    # 6. Dọn dẹp tài nguyên khi user đóng app
    print("\n[Main] Đang dọn dẹp tài nguyên...")
    worker.running = False
    worker.wait()
    engine.close()
    sys.exit(exit_code)
