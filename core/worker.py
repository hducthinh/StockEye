import sys, os, time, json, queue, threading, math, random, ctypes
import cv2
import numpy as np
import chess
import keyboard
from PyQt5.QtCore import QThread, pyqtSignal, Qt

class ChessWorker(QThread):
    # Truyền danh sách tọa độ nước đi lên UI
    # Định dạng: [((sx, sy), (ex, ey), score), ...]
    moves_ready = pyqtSignal(list)
    suggest_ui_signal = pyqtSignal(bool)
    exit_app_signal = pyqtSignal()
    force_side_ui_signal = pyqtSignal(str)
    toggle_stealth_signal = pyqtSignal()

    def __init__(self, capture, engine):
        super().__init__()
        self.capture = capture
        self.engine = engine
        self.running = True
        self.manual_move_request = None
        self.midgame_sync_request = False
        self.is_paused = True
        self.is_stealth_active = False
        
        self.analysis_queue = queue.Queue()
        
        import json, os
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
            except:
                self.config_data = {}
        else:
            self.config_data = {}
            
        # Ép mặc định khi khởi động
        self.config_data["suggest_mode"] = False
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
        except:
            pass

        def kill_switch(_):
            if self.config_data.get("suggest_mode", False):
                self.toggle_suggest_mode()

        # Đăng ký phím tắt toàn cục (Global Hotkeys)
        import keyboard
        keyboard.on_press_key("esc", kill_switch)
        keyboard.on_press_key("2", lambda _: self.toggle_suggest_mode())
        keyboard.on_press_key("5", lambda _: self.force_side_ui_signal.emit("white"))
        keyboard.on_press_key("6", lambda _: self.force_side_ui_signal.emit("black"))
        keyboard.on_press_key("f4", lambda _: self.exit_app_signal.emit())

        # [F10] Boss Key / Stealth Mode (Ẩn toàn bộ tool, Taskbar, Task Manager)
        self.last_f10_time = 0
        def on_f10(_):
            now = time.time()
            if now - self.last_f10_time < 0.4:
                return
            self.last_f10_time = now
            self.toggle_stealth_signal.emit()

        keyboard.on_press_key("f10", on_f10)

    def toggle_suggest_mode(self):
        new_state = not self.config_data.get("suggest_mode", False)
        self.config_data["suggest_mode"] = new_state
        self.is_paused = not new_state
        self.suggest_ui_signal.emit(new_state)
        
        if new_state:
            print("\n[System] Đã BẬT Gợi ý!")
            self.request_midgame_sync(turn="auto_suggest")
        else:
            print("\n[System] Đã TẮT Gợi ý!")
            self.moves_ready.emit([]) # Xóa UI mũi tên

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
            
        # Tính tọa độ trung tâm ô cờ
        rel_x = (col_idx * self.capture.sq_width) + (self.capture.sq_width / 2)
        rel_y = (y_idx * self.capture.sq_height) + (self.capture.sq_height / 2)
        
        # Cộng thêm độ lệch tuyệt đối của BBox so với màn hình
        abs_x = self.capture.bbox["left"] + rel_x
        abs_y = self.capture.bbox["top"] + rel_y
        
        return (abs_x, abs_y)

    def run(self):
        print("\n[Worker] Bắt đầu theo dõi bàn cờ...")

        
        prev_img = self.capture.get_board_image()
        last_stable_img = prev_img
        pre_move_img = prev_img
        stable_counter = 0
        last_failed_squares = None
        
        # Bỏ qua nước đi mở màn vì tool đang tạm dừng
        # self.analysis_queue.put(True)

        import os
        import threading
        config_mtime = os.path.getmtime("config.json") if os.path.exists("config.json") else 0
        last_config_check = time.time()
        
        # Thread đọc input từ Terminal
        threading.Thread(target=self.terminal_listener, daemon=True).start()
        
        # Thread phân tích Stockfish độc lập
        threading.Thread(target=self.analysis_worker, daemon=True).start()
        
        while self.running:
            if self.midgame_sync_request:
                turn_to_move = self.midgame_sync_request
                self.midgame_sync_request = False
                
                curr_img = self.capture.get_board_image()
                
                # Tự động nhận diện màu quân cờ hiện tại
                try:
                    if self.config_data.get("force_side_enabled", False):
                        detected_color = self.config_data.get("force_side", "white")
                    else:
                        detected_color = self.capture.auto_detect_color(curr_img)
                        
                    self.capture.player_color = detected_color
                    
                    if turn_to_move in ["auto", "auto_suggest"]:
                        turn_to_move = 'w' if detected_color == 'white' else 'b'
                        print(f"\n[System] TỰ NHẬN DIỆN BẠN CẦM QUÂN: {'TRẮNG' if detected_color == 'white' else 'ĐEN'} (Gợi ý)")
                    
                    print(f"\n[System] ĐANG QUÉT ẢNH VÀ TÌM NƯỚC CHO {'TRẮNG' if turn_to_move == 'w' else 'ĐEN'}...")
                    
                    # Cập nhật màu quân theo yêu cầu gợi ý của user
                    # Đồng bộ màu phe để vẽ UI chính xác
                    self.config_data["player_color"] = "white" if turn_to_move == 'w' else "black"
                    self.capture.player_color = self.config_data["player_color"]
                except:
                    pass
                
                # 1. Gọi hàm nhận diện hình ảnh để lấy chuỗi FEN
                detected_fen = self.capture.image_to_fen(
                    curr_img, 
                    turn_to_move=turn_to_move, 
                    fallback_board=self.engine.board
                ) 
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
                        
                        # Reset biến theo dõi để tránh nhiễu ảnh
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
                    
            # Tự động phục hồi nếu bàn cờ không đổi (lỗi click bị miss do quá nhanh)
            recovery_time = 3.0
            if getattr(self, 'current_time_left', 60.0) < 15.0:
                recovery_time = 0.5
                
            if getattr(self, 'waiting_for_board_change', False) and time.time() - getattr(self, 'last_bot_click_time', 0) > recovery_time:
                print(f"[System] CẢNH BÁO: Đã quá {recovery_time}s kể từ khi Bot click mà bàn cờ không đổi. Tự động phục hồi (Auto-Recovery)!")
                self.waiting_for_board_change = False
                self.request_midgame_sync(turn="auto")
                
            # Xử lý lệnh terminal hoặc nước đi thủ công
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
            
            # Lọc nhiễu hoạt ảnh trượt (Anti-Animation)
            import cv2
            import numpy as np
            diff = cv2.absdiff(prev_img, curr_img)
            gray = np.max(diff, axis=2).astype(np.uint8)
            
            # [SỬA ĐỔI 3] Đồng bộ ngưỡng 40 với capture.py
            _, thresh = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)
            motion_pixels = cv2.countNonZero(thresh)
            
            # Ngưỡng 500 px để lọc nhiễu icon nhấp nháy
            if motion_pixels > 500: 
                stable_counter = 0
            else:
                stable_counter += 1
                
            # Dùng cấu hình số frame tĩnh để xác nhận kết thúc hoạt ảnh
            stable_frames = self.engine.config.get("stable_frames", 4)
            if stable_counter >= stable_frames:
                # Lúc này hoạt ảnh đã xong hoàn toàn. 
                # So sánh frame tĩnh hiện tại và trước khi di chuyển
                changed_squares_stable = self.capture.detect_move(last_stable_img, curr_img)
                
                if changed_squares_stable and len(changed_squares_stable) >= 2:
                    pushed_moves = self.engine.infer_and_push_move(changed_squares_stable)
                    
                    if pushed_moves:
                        self.analysis_queue.put(True)
                        self.waiting_for_board_change = False
                        # Lưu ảnh cũ để đối chiếu nhầm lẫn Hover Cancel
                        pre_move_img = last_stable_img
                        # Cập nhật mốc tĩnh mới vì đã áp dụng nước đi thành công!
                        last_stable_img = curr_img
                        # Đã áp dụng xong, ẩn cảnh báo cũ đi
                        last_failed_squares = None
                    else:
                        # Thay đổi diện rộng (>= 5 ô) thường do reset ván mới, popup hoặc cuộn trang
                        # Auto-sync để lấy lại FEN chuẩn
                        if len(changed_squares_stable) >= 5:
                            print(f"[Worker] ⚠️ Phát hiện thay đổi diện rộng ({len(changed_squares_stable)} ô). Tự động đồng bộ FEN (New Game)!")
                            self.request_midgame_sync(turn="auto_suggest")
                            stable_counter = 0
                            continue
                            
                        # Kiểm tra thao tác nhấc và thả quân về chỗ cũ (Hover Cancel)
                        is_potential_cancel = self.engine.is_potential_hover_cancel(changed_squares_stable)
                        
                        if is_potential_cancel:
                            # Xác nhận lại bằng hình ảnh: Nếu thực sự là Hover Cancel, 
                            # Xác nhận bằng ảnh: ảnh hiện tại phải giống ảnh trước khi đi
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
                                # Chỉ là dư âm hoạt ảnh, bỏ qua
                                # Bỏ qua rác hình ảnh
                                if changed_squares_stable != last_failed_squares:
                                    print(f"[Worker] Đã bỏ qua rác/hoạt ảnh lơ lửng sau nước đi: {changed_squares_stable}")
                                    last_failed_squares = changed_squares_stable
                                    # Không cập nhật mốc ảnh tĩnh để tránh bỏ sót nước đi
                        elif changed_squares_stable != last_failed_squares:
                            print(f"[Worker] Đã bỏ qua rác/hoạt ảnh lơ lửng: {changed_squares_stable}")
                            last_failed_squares = changed_squares_stable

                                
                        elif stable_counter > 40:
                            print(f"[Worker] ⚠️ Bàn cờ bị Desync. Đang lấy lại FEN để tiếp tục gợi ý...")
                            self.request_midgame_sync(turn="auto_suggest")
                            stable_counter = 0
                            
            prev_img = curr_img
                
    def process_and_emit_top_moves(self):
        """Hỏi Stockfish và đẩy kết quả lên UI"""
        import chess
        
        if self.is_paused:
            self.moves_ready.emit([]) # Xóa UI mũi tên
            return
            
        # Bỏ qua phân tích lượt đối thủ để tiết kiệm CPU
        with self.engine.lock:
            board_turn = self.engine.board.turn
            
        if self.capture.player_color == "white" and board_turn == chess.BLACK:
            self.moves_ready.emit([]) # Xóa UI mũi tên
            return
        if self.capture.player_color == "black" and board_turn == chess.WHITE:
            self.moves_ready.emit([]) # Xóa UI mũi tên
            return
            
        if not self.config_data.get("suggest_mode", True):
            self.moves_ready.emit([])
            return
            
        top_moves = self.engine.get_top_moves(limit=4)
        
        if not top_moves:
            return
            
        ui_data = []
        best_m = None
        best_score = None
        for item in top_moves:
            m = item["move"] # 'e2e4' hoặc ['e2e4', 'e7e5', 'g1f3']
            score = item["score"]
            
            if best_m is None:
                best_m = m[0] if isinstance(m, list) else m
                best_score = score
            
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
                
        # (Đã xóa logic giới hạn mũi tên khi tàn sát)
            
        # Phát tín hiệu an toàn qua thread ranh giới (cross-thread)
        self.moves_ready.emit(ui_data)

    def terminal_listener(self):
        while self.running:
            try:
                cmd = input().strip().lower()
                if len(cmd) >= 4 and self.running:
                    self.manual_move_request = cmd
            except (EOFError, KeyboardInterrupt):
                break
            except Exception:
                break
    def analysis_worker(self):
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

