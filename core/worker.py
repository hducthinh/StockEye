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
    toggle_pause_signal = pyqtSignal()
    autoplay_ui_signal = pyqtSignal(bool)
    autofarm_ui_signal = pyqtSignal(bool)
    suggest_ui_signal = pyqtSignal(bool)
    exit_app_signal = pyqtSignal()

    def __init__(self, capture, engine, mouse_controller):
        super().__init__()
        self.capture = capture
        self.engine = engine
        self.mouse_controller = mouse_controller
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
            
        # Ép mặc định khi khởi động là TẮT tất cả các chức năng
        self.config_data["autoplay"] = False
        self.config_data["suggest_mode"] = False
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
        keyboard.on_press_key("2", lambda _: self.toggle_suggest_mode())
        keyboard.on_press_key("3", lambda _: self.toggle_autoplay())
        
        self.auto_farm = False
        keyboard.on_press_key("4", lambda _: self.toggle_autofarm())
        keyboard.on_press_key("f4", lambda _: self.exit_app_signal.emit())

    def toggle_autofarm(self):
        new_state = not getattr(self, 'auto_farm', False)
        if new_state and self.is_paused:
            print("\n[System] Không thể Bật Autofarm (4)! Vui lòng Bật Tool (bấm phím 1) trước.")
            self.autofarm_ui_signal.emit(False)
            return
        self.auto_farm = new_state
        state = "BẬT" if self.auto_farm else "TẮT"
        print(f"\n[Autofarm] Chức năng tự động tìm trận đã được {state} (Bấm 4 để chuyển đổi)!")
        self.autofarm_ui_signal.emit(self.auto_farm)

    def toggle_suggest_mode(self):
        new_state = not self.config_data.get("suggest_mode", True)
        
        if new_state and self.is_paused:
            print("\n[System] Không thể Bật Gợi ý (2)! Vui lòng Bật Tool (bấm phím 1) trước.")
            # Emit False again in case UI triggered this and expects it to be on
            self.suggest_ui_signal.emit(False)
            return

        self.config_data["suggest_mode"] = new_state
        self.suggest_ui_signal.emit(new_state)
        
        if new_state:
            print("\n[System] Đã BẬT Gợi ý!")
            self.request_midgame_sync(turn="auto_suggest")
        else:
            print("\n[System] Đã TẮT Gợi ý!")
            self.moves_ready.emit([]) # Xóa UI mũi tên
            
            # Khi 2 tắt thì 3 cũng phải tắt
            if self.config_data.get("autoplay", False):
                self.config_data["autoplay"] = False
                self.autoplay_ui_signal.emit(False)
                print("\n[System] Đã tự động TẮT Autoplay vì Gợi ý đã bị tắt!")

    def toggle_autoplay(self):
        new_state = not self.config_data.get("autoplay", False)
        
        if new_state:
            if self.is_paused:
                print("\n[System] Không thể Bật Autoplay (3)! Vui lòng Bật Tool (bấm phím 1) trước.")
                self.autoplay_ui_signal.emit(False)
                return
            if not self.config_data.get("suggest_mode", True):
                print("\n[System] Không thể Bật Autoplay (3)! Vui lòng Bật Gợi ý (bấm phím 2) trước.")
                self.autoplay_ui_signal.emit(False)
                return

        if new_state:
            self.config_data["human_mouse"] = True
            self.request_midgame_sync(turn="auto")
        else:
            self.config_data["autoplay"] = False
            self.autoplay_ui_signal.emit(False)
            print("\n[System] Đã TẮT Autoplay!")

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
        
        # Thread OCR Đồng hồ độc lập (Clock Worker)
        threading.Thread(target=self.clock_worker, daemon=True).start()
        
        # Thread Autofarm (Tự động bấm New Game)
        self.is_waiting_for_match = False
        self.match_search_start_time = 0
        
        threading.Thread(target=self.autofarm_worker, daemon=True).start()
        
        # Thread điều khiển chuột (Click Worker)
        threading.Thread(target=self.click_worker, daemon=True).start()
        
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
                            print(f"\n[System] ĐÃ BẬT AUTOPLAY! TỰ NHẬN DIỆN BẠN CẦM QUÂN: {'TRẮNG' if detected_color == 'white' else 'ĐEN'}")
                        else:
                            # Đảm bảo tắt Autoplay khi dùng chế độ Gợi ý
                            self.config_data["autoplay"] = False
                            self.autoplay_ui_signal.emit(False)
                            print(f"\n[System] ĐÃ TẮT AUTOPLAY! TỰ NHẬN DIỆN BẠN CẦM QUÂN: {'TRẮNG' if detected_color == 'white' else 'ĐEN'} (Chỉ gợi ý)")
                            
                        turn_to_move = turn_to_move_resolved
                    
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
                
            if self.is_paused or getattr(self, 'is_waiting_for_match', False):
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
                            
                            # Thay đổi diện rộng (>= 5 ô) thường do popup hoặc cuộn trang
                            # Auto-sync để lấy lại FEN chuẩn
                            if len(changed_squares_stable) >= 5:
                                print(f"[Worker] ⚠️ Phát hiện thay đổi diện rộng ({len(changed_squares_stable)} ô). Tự động đồng bộ FEN!")
                                mode = "auto" if self.config_data.get("autoplay", False) else "auto_suggest"
                                self.request_midgame_sync(turn=mode)
                                stable_counter = 0
                                
                        elif stable_counter > (10 if getattr(self, 'current_time_left', 60) < 15.0 else 45):
                            if not self.config_data.get('autoplay', False):
                                print(f"[Worker] ⚠️ Bàn cờ bị Desync (Chế độ tự chơi). Đang lấy lại FEN để tiếp tục gợi ý...")
                                self.request_midgame_sync(turn="auto_suggest")
                            else:
                                print(f"[Worker] ⚠️ Phát hiện bàn cờ bị Desync! Bỏ qua tự động phục hồi để tránh nhận diện nhầm lượt.")
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
            
        top_moves = self.engine.get_top_moves(limit=2, time_left=getattr(self, 'current_time_left', 60.0))
        
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
                
        # Tắt Overlay khi < 5s để dồn CPU cho Engine
        if self.current_time_left < 5.0:
            ui_data = []
            
        # Phát tín hiệu an toàn qua thread ranh giới (cross-thread)
        self.moves_ready.emit(ui_data)
        
        # Xử lý Autoplay
        import chess
        if self.config_data.get('autoplay', False) and not self.is_paused and best_m:
            if getattr(self, 'waiting_for_board_change', False):
                return  # Chờ OpenCV xử lý click trước đó để chống spam
                
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
                
                bot_delay = self.config_data.get("bot_delay", 0.15)
                scramble_threshold = max(5.0, bot_delay * 10.0)
                is_scramble = self.current_time_left < scramble_threshold
                
                with self.click_queue.mutex:
                    self.click_queue.queue.clear()
                    
                with self.engine.lock:
                    context = {
                        "fullmove_number": self.engine.board.fullmove_number,
                        "is_in_check": self.engine.board.is_check(),
                        "opponent_captured": False,
                        "legal_moves_count": len(list(self.engine.board.legal_moves)),
                        "score": best_score,
                        "is_promotion": len(best_m) == 5
                    }
                    
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
                    "context": context,
                    "is_premove_hover": False
                }
                self.click_queue.put(click_task)
            
            # [TỐI ƯU] Predictive Premove
            elif not is_our_turn and len(top_moves) > 0 and "forced_premove" in top_moves[0]:
                premove_data = top_moves[0]["forced_premove"]
                our_premove = premove_data["our_premove"]
                
                start_sq = our_premove[:2]
                end_sq = our_premove[2:4]
                start_px = self.square_to_pixel(start_sq)
                end_px = self.square_to_pixel(end_sq)
                
                with self.click_queue.mutex:
                    self.click_queue.queue.clear()
                
                premove_task = {
                    "start_sq": start_sq,
                    "end_sq": end_sq,
                    "start_px": start_px,
                    "end_px": end_px,
                    "decision_fen": None,
                    "is_scramble": self.current_time_left < max(5.0, self.config_data.get("bot_delay", 0.15) * 10.0),
                    "context": {"is_premove_hover": True, "expected_opp_move": premove_data["expected_opp_move"]},
                    "is_premove_hover": True
                }
                self.click_queue.put(premove_task)


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
    def clock_worker(self):
        while self.running:
            try:
                time_left = self.capture.get_remaining_time()
                if time_left is not None:
                    self.current_time_left = time_left
                time.sleep(0.1) # Quét đồng hồ mỗi 100ms
            except Exception:
                time.sleep(0.5)
    def autofarm_worker(self):
        import ctypes
        import time
        while self.running:
            if getattr(self, 'auto_farm', False) and not self.is_paused:
                try:
                    curr_img = self.capture.get_board_image()
                    
                    if not self.is_waiting_for_match:
                        btn_pos = self.capture.find_new_game_button(curr_img)
                        if btn_pos:
                            print(f"[Autofarm] Phát hiện nút New Game/Rematch tại {btn_pos}! Tiến hành click...")
                            self.is_waiting_for_match = True
                            self.match_search_start_time = time.time()
                            
                            # Click
                            rx, ry = btn_pos
                            ctypes.windll.user32.SetCursorPos(int(rx), int(ry))
                            time.sleep(0.1)
                            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0) # LEFTDOWN
                            time.sleep(0.05)
                            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0) # LEFTUP
                            time.sleep(0.05)
                            ctypes.windll.user32.SetCursorPos(10, 10)
                            
                            # Reset board
                            self.engine.reset_board()
                            self.engine.white_moves = []
                            self.engine.black_moves = []
                            
                            # Né hoạt ảnh Modal fade-out
                            time.sleep(0.5)
                    else:
                        # Đang đợi trận mới (Polling)
                        if time.time() - self.match_search_start_time > 60:
                            print("[Autofarm] Timeout! Quá 60s không vào trận mới. Hủy trạng thái chờ.")
                            self.is_waiting_for_match = False
                        else:
                            if self.capture.is_start_position_fast(curr_img):
                                print("[Autofarm] Bàn cờ mới đã load xong! Chuẩn bị chiến đấu...")
                                time.sleep(0.2) # Chờ giao diện ổn định hẳn
                                self.is_waiting_for_match = False
                                self.request_midgame_sync(turn="auto")
                except Exception as e:
                    pass
            
            time.sleep(1.0 if not self.is_waiting_for_match else 0.5)
    def click_worker(self):
        import ctypes
        import random
        import math
        import time
        import chess
        
    
            
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
                
                is_premove_hover = task.get("is_premove_hover", False)
                if is_premove_hover:
                    expected_opp_move = ctx.get("expected_opp_move")
                    print(f"[ClickWorker] PREDICTIVE PREMOVE! Đưa chuột tới {start_sq} và chờ đối thủ đi {expected_opp_move}...")
                    
                    # 1. Rê chuột tới start_px
                    self.mouse_controller.move_and_click(start_px[0], start_px[1], 0, 0.05, ctx, move=True, click=False)
                    # 2. Nhấn giữ chuột trái (mô phỏng nhặt quân cờ)
                    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
                    # 3. Rê chuột tới end_px
                    self.mouse_controller.move_and_click(end_px[0], end_px[1], 0, 0.05, ctx, move=True, click=False)
                    
                    # 4. Chờ tín hiệu đối thủ đã đi đúng nước dự đoán
                    start_wait = time.time()
                    released = False
                    while time.time() - start_wait < 15.0 and self.running:
                        with self.engine.lock:
                            if len(self.engine.board.move_stack) > 0:
                                last_move = self.engine.board.move_stack[-1].uci()
                                if last_move == expected_opp_move:
                                    # ĐÚNG NƯỚC! NHẢ CHUỘT NGAY LẬP TỨC (0.001s)
                                    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
                                    released = True
                                    print("[ClickWorker] ĐỐI THỦ ĐÃ ĐI! NHẢ PREMOVE NGAY LẬP TỨC! 0.001s")
                                    break
                                # Xử lý khi đến lượt người chơi
                                elif self.engine.board.turn == (chess.WHITE if self.capture.player_color == "white" else chess.BLACK):
                                    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
                                    released = True
                                    break
                        time.sleep(0.005)
                    
                    if not released:
                        ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
                        
                    self.last_bot_click_time = time.time()
                    self.waiting_for_board_change = True
                    continue

                # Double check FEN
                with self.engine.lock:
                    current_fen = self.engine.board.fen()
                if current_fen != decision_fen:
                    print("[ClickWorker] FEN mismatch (Opponent moved?). Hủy click.")
                    continue
                    
                bot_delay = self.config_data.get("bot_delay", 0.15)
                scramble_threshold = max(5.0, bot_delay * 10.0)
                scramble_time = self.config_data.get("scramble_time", 5.0)
                if self.current_time_left < scramble_time:
                    bot_delay = 0.02
                
                # Fitts Law approximation for travel time (luôn áp dụng)
                dist = math.hypot(end_px[0] - start_px[0], end_px[1] - start_px[1])
                dist_squares = dist / self.capture.sq_width
                travel_time = 0.05 + (dist_squares * 0.015)
                
                action_log = "Normal"
                
                # Check Mate Premove
                is_mate_premove = False
                if "score" in ctx and isinstance(ctx["score"], str):
                    s = ctx["score"]
                    try:
                        if self.capture.player_color == "white" and s.startswith("M") and not s.startswith("M-"):
                            mate_val = int(s[1:])
                            if 1 <= mate_val <= 3: is_mate_premove = True
                        elif self.capture.player_color == "black" and s.startswith("M-"):
                            mate_val = int(s[2:])
                            if 1 <= mate_val <= 3: is_mate_premove = True
                    except:
                        pass
                
                # Quy tắc Tối thượng: Mate Premove (Hard-Override)
                if is_mate_premove:
                    reaction_time = 0.01
                    travel_time = 0.02
                    action_log = "Mate Premove"
                # Quy tắc: Phong Hậu Cờ Tàn (Premove)
                elif ctx.get("is_promotion", False):
                    reaction_time = 0.01
                    travel_time = 0.02
                    action_log = "Promotion Premove"
                # Quy tắc Tối thượng: Time Scramble (Hard-Override)
                elif self.current_time_left <= scramble_time:
                    reaction_time = 0.01
                    travel_time = 0.01
                    is_scramble = True
                    action_log = "Scramble"
                else:
                    # 4 Lớp Màng Lọc Ngữ Cảnh
                    # Bước 4: Hesitation (Trượt chuột) - Chỉ áp dụng khi còn RẤT NHIỀU thời gian
                    if random.random() < 0.03 and self.current_time_left > scramble_threshold * 2.0:
                        reaction_time = random.uniform(bot_delay * 4.0, bot_delay * 7.0)
                        action_log = "Hesitation / Deep Think"
                    # Bước 2: Forced/Evasion
                    elif ctx["opponent_captured"]:
                        reaction_time = max(0.05, bot_delay * 0.8 + random.gauss(0.05, 0.02))
                        action_log = "Recapture"
                    elif ctx["is_in_check"]:
                        if self.current_time_left < scramble_threshold:
                            reaction_time = random.uniform(0.01, 0.05)
                            action_log = "Scramble Evasion"
                        elif ctx["legal_moves_count"] <= 3:
                            hesitation_delay = max(0.0, random.gauss(bot_delay * 0.5, 0.05))
                            reaction_time = (bot_delay * 0.8) + hesitation_delay
                            action_log = "Instinct Evasion"
                        else:
                            evasion_multiplier = random.uniform(1.5, 3.0) 
                            hesitation_delay = max(0.0, random.gauss(bot_delay, 0.2))
                            reaction_time = (bot_delay * evasion_multiplier) + hesitation_delay
                            action_log = "Calculated Evasion"
                    # Bước 3: Premove (Khai cuộc <= 4)
                    elif ctx["fullmove_number"] <= 4:
                        reaction_time = max(0.01, bot_delay * 0.3 + random.uniform(0.01, 0.05))
                        action_log = "Opening Premove"
                    # Bước 1: Game Phases (Bình thường)
                    else:
                        # Phân bổ thời gian dựa trên bot_delay do người dùng cài đặt
                        if self.current_time_left > scramble_threshold:
                            variance = random.uniform(0.8, 1.5)
                            reaction_time = max(0.01, (bot_delay * variance) + random.gauss(0.05, 0.02))
                        else:
                            # Scramble: Ép tốc độ xuống siêu nhanh
                            reaction_time = max(0.01, (bot_delay * 0.2) + random.uniform(0.01, 0.03))
                        action_log = "Tactical Move"
                        
                    # Safeguard: Không bao giờ dùng quá 20% tổng thời gian còn lại cho 1 nước đi (trừ khi thời gian quá thấp)
                    max_allowed_time = max(0.02, self.current_time_left * 0.2)
                    if reaction_time > max_allowed_time:
                        reaction_time = max_allowed_time
                        action_log += " (Capped)"

                print(f"[ClickWorker] {action_log}! Executing {start_sq}{end_sq} (Reaction: {reaction_time:.2f}s, Travel: {travel_time:.2f}s, Scramble: {is_scramble})")
                
                enable_human = self.config_data.get("human_mouse", True)
                
                ctx["is_scramble"] = is_scramble
                
                if enable_human:
                    # Pre-hovering: Rê chuột sẵn trong lúc đợi Engine
                    move_start_time = min(reaction_time, 0.15)
                    sleep_time = reaction_time - move_start_time
                    
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
                    # Kiểm tra lại trạng thái Autoplay sau reaction time
                    if not self.config_data.get("autoplay", False):
                        print("[ClickWorker] Autoplay đã bị tắt giữa chừng. Hủy di chuyển chuột.")
                        continue
                    
                    # Rê chuột tới start_px nhưng chưa click
                    self.mouse_controller.move_and_click(start_px[0], start_px[1], 0, move_start_time, ctx, move=True, click=False)
                else:
                    time.sleep(reaction_time)
                    if not self.config_data.get("autoplay", False):
                        print("[ClickWorker] Autoplay đã bị tắt giữa chừng. Hủy click.")
                        continue

                # Kiểm tra lại FEN phòng khi đối thủ đã đi trong lúc chờ
                with self.engine.lock:
                    current_fen = self.engine.board.fen()
                if current_fen != decision_fen:
                    print("[ClickWorker] FEN mismatch sau reaction time. Hủy click.")
                    continue

                # Execute clicks
                if enable_human:
                    # Chuột đã tới quân cờ rồi, giờ chỉ cần click chọn quân cờ
                    self.mouse_controller.move_and_click(start_px[0], start_px[1], 0, 0, ctx, move=False, click=True)
                else:
                    # Nếu tắt Human, teleport tới start_sq và click
                    self.mouse_controller.move_and_click(start_px[0], start_px[1], 0, 0, ctx)
                
                # Di chuyển chuột tới ô cần đến và click thả quân cờ
                self.mouse_controller.move_and_click(end_px[0], end_px[1], 0, travel_time, ctx)
                
                self.last_bot_click_time = time.time()
                self.waiting_for_board_change = True
                
                # Di chuyển chuột ra ngoài để tránh che OCR
                time.sleep(0.05)
                if enable_human:
                    offset_x = random.choice([-1.5, 1.5]) * self.capture.sq_width
                    offset_y = random.choice([-1.5, 1.5]) * self.capture.sq_width
                    
                    target_x = max(self.capture.bbox["left"], min(self.capture.bbox["left"] + self.capture.bbox["width"], end_px[0] + offset_x))
                    target_y = max(self.capture.bbox["top"], min(self.capture.bbox["top"] + self.capture.bbox["height"], end_px[1] + offset_y))
                    
                    curvature_val = self.config_data.get("mouse_curvature", 30)
                    self.mouse_controller.human_move_mouse(target_x, target_y, 0.15, curvature_val)
                else:
                    # Tắt human thì cứ vứt tạm ra rìa bàn cờ
                    ctypes.windll.user32.SetCursorPos(self.capture.bbox["left"], self.capture.bbox["top"])
                    
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[ClickWorker Error] {e}")

