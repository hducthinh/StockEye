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
    autofarm_ui_signal = pyqtSignal(bool)
    exit_app_signal = pyqtSignal()

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
        
        self.auto_farm = False
        def toggle_autofarm_switch(_):
            self.auto_farm = not getattr(self, 'auto_farm', False)
            state = "BẬT" if self.auto_farm else "TẮT"
            print(f"\n[Autofarm] Chức năng tự động tìm trận đã được {state} (Bấm 4 để chuyển đổi)!")
            self.autofarm_ui_signal.emit(self.auto_farm)
            
        keyboard.on_press_key("4", toggle_autofarm_switch)
        keyboard.on_press_key("f4", lambda _: self.exit_app_signal.emit())

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
        
        # Thread Autofarm (Tự động bấm New Game)
        self.is_waiting_for_match = False
        self.match_search_start_time = 0
        
        def autofarm_worker():
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

        threading.Thread(target=autofarm_worker, daemon=True).start()
        
        # Thread điều khiển chuột (Click Worker)
        def click_worker():
            import ctypes
            import random
            import math
            import time
            import chess
            
            def ease_in_out_cubic(t):
                if t < 0.5:
                    return 4 * t * t * t
                else:
                    return 1 - math.pow(-2 * t + 2, 3) / 2

            def generate_bezier_curve(p0, p1, p2, p3, steps):
                curve = []
                for i in range(steps + 1):
                    t = i / steps if steps > 0 else 1
                    t = ease_in_out_cubic(t)
                    x = (1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0]
                    y = (1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1]
                    curve.append((int(x), int(y)))
                return curve

            def human_move_mouse(target_x, target_y, duration, curvature_val):
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                pt = POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                start_x, start_y = pt.x, pt.y
                
                p0 = (start_x, start_y)
                p3 = (target_x, target_y)
                dist = math.hypot(target_x - start_x, target_y - start_y)
                
                offset_val = dist * (curvature_val / 100.0)
                p1 = (
                    start_x + (target_x - start_x) * 0.3 + random.uniform(-offset_val, offset_val),
                    start_y + (target_y - start_y) * 0.3 + random.uniform(-offset_val, offset_val)
                )
                p2 = (
                    start_x + (target_x - start_x) * 0.7 + random.uniform(-offset_val, offset_val),
                    start_y + (target_y - start_y) * 0.7 + random.uniform(-offset_val, offset_val)
                )
                
                steps = max(5, int(duration * 120))
                curve = generate_bezier_curve(p0, p1, p2, p3, steps)
                
                start_time = time.perf_counter()
                for i, (cx, cy) in enumerate(curve):
                    ctypes.windll.user32.SetCursorPos(cx, cy)
                    target_elapsed = (i / steps) * duration
                    while time.perf_counter() - start_time < target_elapsed:
                        pass
                ctypes.windll.user32.SetCursorPos(int(target_x), int(target_y))

            def move_and_click(px_x, px_y, delay, travel_time, context=None, move=True, click=True):
                if move:
                    offset_limit = self.capture.sq_width * 0.15
                    rx = px_x + random.uniform(-offset_limit, offset_limit)
                    ry = px_y + random.uniform(-offset_limit, offset_limit)
                    
                    enable_human = self.config_data.get("human_mouse", True)
                    curvature_val = self.config_data.get("mouse_curvature", 30)
                    
                    if not enable_human:
                        time.sleep(travel_time)
                        ctypes.windll.user32.SetCursorPos(int(rx), int(ry))
                    else:
                        fullmove = context.get("fullmove_number", 99) if context else 99
                        apply_overshoot = fullmove < 20 or self.current_time_left > 30.0
                        
                        # Không teleport, chỉ đẩy nhanh tốc độ vẽ
                        actual_travel = max(0.005, travel_time)
                        
                        if apply_overshoot and random.random() < 0.5 and actual_travel > 0.05:
                            os_x = rx + random.uniform(-offset_limit * 1.5, offset_limit * 1.5)
                            os_y = ry + random.uniform(-offset_limit * 1.5, offset_limit * 1.5)
                            human_move_mouse(os_x, os_y, actual_travel * 0.8, curvature_val)
                            human_move_mouse(rx, ry, actual_travel * 0.2, curvature_val)
                        else:
                            human_move_mouse(rx, ry, actual_travel, curvature_val)
                
                if click:
                    is_scr = context.get("is_scramble", False) if context else False
                    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0) # LEFTDOWN
                    time.sleep(0.005 if is_scr else random.uniform(0.02, 0.05))
                    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0) # LEFTUP
                    time.sleep(0.005 if is_scr else 0.03)
                
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
                        move_and_click(start_px[0], start_px[1], 0, 0.05, ctx, move=True, click=False)
                        # 2. Nhấn giữ chuột trái (mô phỏng nhặt quân cờ)
                        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
                        # 3. Rê chuột tới end_px
                        move_and_click(end_px[0], end_px[1], 0, 0.05, ctx, move=True, click=False)
                        
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
                                    # Nếu đối thủ đi nước khác hoặc đến lượt chúng ta bằng cách nào đó
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
                    if self.current_time_left < 5.0:
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
                    
                    # Quy tắc Tối thượng: Troll Mode
                    if ctx.get("is_troll_check", False):
                        reaction_time = 0.01
                        travel_time = 0.02
                        action_log = "Troll Check"
                    # Quy tắc Tối thượng: Mate Premove (Hard-Override)
                    elif is_mate_premove:
                        reaction_time = 0.01
                        travel_time = 0.02
                        action_log = "Mate Premove"
                    # Quy tắc: Phong Hậu Cờ Tàn (Premove)
                    elif ctx.get("is_promotion", False):
                        reaction_time = 0.01
                        travel_time = 0.02
                        action_log = "Promotion Premove"
                    # Quy tắc Tối thượng: Time Scramble (Hard-Override)
                    elif self.current_time_left <= 5.0:
                        reaction_time = 0.01
                        travel_time = 0.01
                        is_scramble = True
                        action_log = "Scramble"
                    else:
                        # 4 Lớp Màng Lọc Ngữ Cảnh
                        # Bước 4: Hesitation (Trượt chuột)
                        if random.random() < 0.03:
                            reaction_time = random.uniform(1.5, 3.0)
                            action_log = "Hesitation"
                        # Bước 2: Forced/Evasion
                        elif ctx["opponent_captured"]:
                            reaction_time = max(0.05, bot_delay * 0.8 + random.gauss(0.05, 0.02))
                            action_log = "Recapture"
                        elif ctx["is_in_check"]:
                            if self.current_time_left < 15.0:
                                reaction_time = random.uniform(0.01, 0.05)
                                action_log = "Scramble Evasion"
                            elif ctx["legal_moves_count"] <= 3:
                                hesitation_delay = max(0.0, random.gauss(bot_delay * 0.5, 0.05))
                                reaction_time = (bot_delay * 0.8) + hesitation_delay
                                action_log = "Instinct Evasion"
                            else:
                                hesitation_delay = max(0.0, random.gauss(bot_delay, 0.1))
                                reaction_time = (bot_delay * 1.5) + hesitation_delay
                                action_log = "Calculated Evasion"
                        # Bước 3: Premove (Khai cuộc <= 4)
                        elif ctx["fullmove_number"] <= 4:
                            reaction_time = max(0.01, bot_delay * 0.3 + random.uniform(0.01, 0.05))
                            action_log = "Opening Premove"
                        # Bước 1: Game Phases (Bình thường)
                        else:
                            # Phân bổ thời gian dựa trên bot_delay do người dùng cài đặt
                            if self.current_time_left > 15.0:
                                variance = random.uniform(0.8, 1.5)
                                reaction_time = max(0.01, (bot_delay * variance) + random.gauss(0.05, 0.02))
                            else:
                                # Scramble (<15s): Ép tốc độ xuống siêu nhanh
                                reaction_time = max(0.01, (bot_delay * 0.2) + random.uniform(0.01, 0.03))
                            action_log = "Tactical Move"

                    print(f"[ClickWorker] {action_log}! Executing {start_sq}{end_sq} (Reaction: {reaction_time:.2f}s, Travel: {travel_time:.2f}s, Scramble: {is_scramble})")
                    
                    enable_human = self.config_data.get("human_mouse", True)
                    
                    ctx["is_scramble"] = is_scramble
                    
                    if enable_human:
                        # Tối ưu thời gian: Vừa suy nghĩ vừa rê chuột tới quân cờ cần đi (pre-hovering)
                        move_start_time = min(reaction_time, 0.15)
                        sleep_time = reaction_time - move_start_time
                        
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                        
                        # Rê chuột tới start_px nhưng chưa click
                        move_and_click(start_px[0], start_px[1], 0, move_start_time, ctx, move=True, click=False)
                    else:
                        time.sleep(reaction_time)

                    # Double check again just in case the long reaction time allowed opponent to move
                    with self.engine.lock:
                        current_fen = self.engine.board.fen()
                    if current_fen != decision_fen:
                        print("[ClickWorker] FEN mismatch sau reaction time. Hủy click.")
                        continue

                    # Execute clicks
                    if enable_human:
                        # Chuột đã tới quân cờ rồi, giờ chỉ cần click chọn quân cờ
                        move_and_click(start_px[0], start_px[1], 0, 0, ctx, move=False, click=True)
                    else:
                        # Nếu tắt Human, teleport tới start_sq và click
                        move_and_click(start_px[0], start_px[1], 0, 0, ctx)
                    
                    # Di chuyển chuột tới ô cần đến và click thả quân cờ
                    move_and_click(end_px[0], end_px[1], 0, travel_time, ctx)
                    
                    self.last_bot_click_time = time.time()
                    self.waiting_for_board_change = True
                    
                    # Rút chuột nhẹ ra chỗ khác để tránh hover tooltip che mất tầm nhìn OCR
                    time.sleep(0.05)
                    if enable_human:
                        offset_x = random.choice([-1.5, 1.5]) * self.capture.sq_width
                        offset_y = random.choice([-1.5, 1.5]) * self.capture.sq_width
                        
                        target_x = max(self.capture.bbox["left"], min(self.capture.bbox["left"] + self.capture.bbox["width"], end_px[0] + offset_x))
                        target_y = max(self.capture.bbox["top"], min(self.capture.bbox["top"] + self.capture.bbox["height"], end_px[1] + offset_y))
                        
                        curvature_val = self.config_data.get("mouse_curvature", 30)
                        human_move_mouse(target_x, target_y, 0.15, curvature_val)
                    else:
                        # Tắt human thì cứ vứt tạm ra rìa bàn cờ
                        ctypes.windll.user32.SetCursorPos(self.capture.bbox["left"], self.capture.bbox["top"])
                        
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
                    
            # Auto-Recovery: Nếu đã click mà 3s sau bàn cờ không đổi (nước đi không hợp lệ)
            if getattr(self, 'waiting_for_board_change', False) and time.time() - getattr(self, 'last_bot_click_time', 0) > 3.0:
                print("[System] CẢNH BÁO: Đã quá 3s kể từ khi Bot click mà bàn cờ không đổi. Tự động phục hồi (Auto-Recovery)!")
                self.waiting_for_board_change = False
                self.request_midgame_sync(turn="auto")
                
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
            
            # [SỬA ĐỔI 4] Nâng ngưỡng motion_pixels lên 500 để tránh nhiễu từ các icon nhấp nháy (như đồng hồ đỏ báo sắp hết giờ)
            if motion_pixels > 500: 
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
                        self.waiting_for_board_change = False
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
                                    print(f"[Worker] Đã bỏ qua rác/hoạt ảnh lơ lửng sau nước đi: {changed_squares_stable}")
                                    last_failed_squares = changed_squares_stable
                                    # [SỬA LỖI] KHÔNG LƯU last_stable_img TẠI ĐÂY ĐỂ KHÔNG BỊ "NUỐT" NƯỚC ĐI!
                        elif changed_squares_stable != last_failed_squares:
                            print(f"[Worker] Đã bỏ qua rác/hoạt ảnh lơ lửng: {changed_squares_stable}")
                            last_failed_squares = changed_squares_stable
                            
                            # Nếu rác quá lớn (>= 5 ô), gần như chắc chắn là do popup biến mất hoặc màn hình bị cuộn.
                            # Cần auto-sync ngay lập tức để lấy lại mốc FEN chuẩn, tránh kẹt vĩnh viễn!
                            if len(changed_squares_stable) >= 5:
                                print(f"[Worker] ⚠️ Phát hiện thay đổi diện rộng ({len(changed_squares_stable)} ô). Tự động đồng bộ FEN!")
                                self.request_midgame_sync(turn="auto")
                                stable_counter = 0
                                
                        elif stable_counter > (10 if getattr(self, 'current_time_left', 60) < 15.0 else 45):
                            print(f"[Worker] ⚠️ Phát hiện bàn cờ bị Desync! Bỏ qua tự động phục hồi để tránh nhận diện nhầm lượt.")
                            stable_counter = 0
                            
            prev_img = curr_img
                
    def process_and_emit_top_moves(self):
        """Hỏi Stockfish và đẩy kết quả lên UI"""
        import chess
        
        # [TỐI ƯU] Không phân tích nước đi của đối thủ để tiết kiệm CPU và tránh lỗi Autoplay nhầm
        with self.engine.lock:
            board_turn = self.engine.board.turn
            
        if self.capture.player_color == "white" and board_turn == chess.BLACK:
            self.moves_ready.emit([]) # Xóa UI mũi tên
            return
        if self.capture.player_color == "black" and board_turn == chess.WHITE:
            self.moves_ready.emit([]) # Xóa UI mũi tên
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
                
        # [TỐI ƯU] Tắt/đóng băng Overlay nếu còn dưới 5s để tập trung 100% CPU cho Auto-Sync và Engine
        if self.current_time_left < 5.0:
            ui_data = []
            
        # Phát tín hiệu an toàn qua thread ranh giới (cross-thread)
        self.moves_ready.emit(ui_data)
        
        # Xử lý Autoplay
        import chess
        if self.config_data.get('autoplay', False) and not self.is_paused and best_m:
            if getattr(self, 'waiting_for_board_change', False):
                return  # Đang chờ OpenCV nhận diện cú click trước đó. Tránh spam click!
                
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
                        "legal_moves_count": len(list(self.engine.board.legal_moves)),
                        "score": best_score,
                        "is_promotion": len(best_m) == 5,
                        "is_troll_check": top_moves[0].get("is_troll_check", False) if len(top_moves) > 0 else False
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
                    "is_scramble": self.current_time_left < 15.0,
                    "context": {"is_premove_hover": True, "expected_opp_move": premove_data["expected_opp_move"]},
                    "is_premove_hover": True
                }
                self.click_queue.put(premove_task)

class ControlPanelUI(QWidget):
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.setWindowTitle("StockEye Control")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        
        # Thiết lập kích thước
        self.resize(250, 500)
        
        # Tự động chuyển cửa sổ sang góc trên cùng bên phải
        try:
            desktop_geom = QApplication.desktop().availableGeometry()
            x = desktop_geom.width() - self.width() - 20
            y = 20
            self.move(x, y)
        except:
            pass
        
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
        
        # Threads (SpinBox)
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 32)
        self.spin_threads.setValue(self.config_data.get("threads", 2))
        form_layout.addRow("Threads:", self.spin_threads)
        
        # Stable Frames (SpinBox)
        self.spin_stable = QSpinBox()
        self.spin_stable.setRange(1, 10)
        self.spin_stable.setValue(self.config_data.get("stable_frames", 4))
        form_layout.addRow("Stable Frames:", self.spin_stable)
        
        # Trade Bias (SpinBox)
        self.spin_trade_bias = QSpinBox()
        self.spin_trade_bias.setRange(0, 1000)
        self.spin_trade_bias.setSingleStep(10)
        self.spin_trade_bias.setValue(self.config_data.get("trade_bias", 150))
        form_layout.addRow("Trade Bias (cp):", self.spin_trade_bias)
        
        # BM Threshold (SpinBox)
        self.spin_bm_thresh = QSpinBox()
        self.spin_bm_thresh.setRange(0, 10000)
        self.spin_bm_thresh.setSingleStep(50)
        self.spin_bm_thresh.setValue(self.config_data.get("bm_threshold", 400))
        form_layout.addRow("BM Threshold (cp):", self.spin_bm_thresh)
        
        # Enable Human Mouse (Checkbox)
        self.chk_human_mouse = QCheckBox()
        self.chk_human_mouse.setChecked(self.config_data.get("human_mouse", True))
        form_layout.addRow("Human Mouse:", self.chk_human_mouse)
        
        # Mouse Curvature (SpinBox)
        self.spin_curvature = QSpinBox()
        self.spin_curvature.setRange(0, 100)
        self.spin_curvature.setValue(self.config_data.get("mouse_curvature", 30))
        form_layout.addRow("Mouse Curvature:", self.spin_curvature)
        
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
        self.btn_suggest = QPushButton("[2] GỢI Ý")
        self.btn_suggest.setStyleSheet("background-color: white; color: black; font-weight: bold; padding: 10px;")
        self.btn_suggest.clicked.connect(lambda: self.worker.request_midgame_sync("auto_suggest"))
        layout.addWidget(self.btn_suggest)
        
        # Nút Autoplay
        init_autoplay_state = "ĐANG CHẠY" if self.config_data.get("autoplay", False) else "ĐÃ DỪNG"
        self.btn_auto = QPushButton(f"[3] AUTOPLAY: {init_autoplay_state}")
        self.btn_auto.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; padding: 10px;")
        self.btn_auto.clicked.connect(lambda: self.worker.request_midgame_sync("auto"))
        
        def update_autoplay_btn_text(state):
            txt = "ĐANG CHẠY" if self.chk_autoplay.isChecked() else "ĐÃ DỪNG"
            self.btn_auto.setText(f"[3] AUTOPLAY: {txt}")
        self.chk_autoplay.stateChanged.connect(update_autoplay_btn_text)
        
        layout.addWidget(self.btn_auto)
        
        # Nút Autofarm
        init_autofarm_state = "ĐANG CHẠY" if getattr(self.worker, 'auto_farm', False) else "ĐÃ DỪNG"
        self.btn_autofarm = QPushButton(f"[4] AUTOFARM: {init_autofarm_state}")
        self.btn_autofarm.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 10px;")
        def on_autofarm_click():
            self.worker.auto_farm = not getattr(self.worker, 'auto_farm', False)
            state = "ĐANG CHẠY" if self.worker.auto_farm else "ĐÃ DỪNG"
            self.btn_autofarm.setText(f"[4] AUTOFARM: {state}")
            print(f"\n[Autofarm] Chức năng tự động tìm trận đã được {state}!")
        self.btn_autofarm.clicked.connect(on_autofarm_click)
        
        def update_autofarm_btn_text(is_on):
            txt = "ĐANG CHẠY" if is_on else "ĐÃ DỪNG"
            self.btn_autofarm.setText(f"[4] AUTOFARM: {txt}")
        self.worker.autofarm_ui_signal.connect(update_autofarm_btn_text, Qt.QueuedConnection)
        
        layout.addWidget(self.btn_autofarm)
        
        self.setLayout(layout)
        
        self.worker.exit_app_signal.connect(self.close, Qt.QueuedConnection)
        
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
        self.config_data["threads"] = self.spin_threads.value()
        self.config_data["stable_frames"] = self.spin_stable.value()
        self.config_data["trade_bias"] = self.spin_trade_bias.value()
        self.config_data["bm_threshold"] = self.spin_bm_thresh.value()
        self.config_data["human_mouse"] = self.chk_human_mouse.isChecked()
        self.config_data["mouse_curvature"] = self.spin_curvature.value()
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
