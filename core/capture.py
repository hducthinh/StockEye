import cv2
import numpy as np
import mss
import json
import os
import pytesseract
import re

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class BoardCapture:
    def __init__(self):
        self.sct = mss.mss()
        self.bbox = None
        self.clock_region = None
        self.sq_width = 0
        self.sq_height = 0
        
        self.player_color = "white"
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    self.player_color = json.load(f).get("player_color", "white").lower()
            except:
                pass

    def select_roi(self, force_reselect=False):
        import json, os
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "bbox" in config:
                        self.bbox = config["bbox"]
                        self.sq_width = self.bbox["width"] / 8.0
                        self.sq_height = self.bbox["height"] / 8.0
                        print(f"Loaded bbox: {self.bbox}")
                    if "clock_region" in config:
                        self.clock_region = config["clock_region"]
                        print(f"Loaded clock_region: {self.clock_region}")
                    if self.bbox:
                        return
            except Exception as e:
                print("Exception loading config:", e)
                
        raise ValueError("No bbox found!")

    def get_board_image(self):
        """Chụp và trả về ảnh vùng bàn cờ hiện tại"""
        if not self.bbox:
            raise ValueError("Chưa chọn vùng bàn cờ. Vui lòng gọi select_roi() trước.")
            
        img = np.array(self.sct.grab(self.bbox))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
    def get_remaining_time(self):
        """Chụp và đọc thời gian từ vùng đồng hồ bằng OCR"""
        if not self.clock_region:
            return None
            
        try:
            img = np.array(self.sct.grab(self.clock_region))
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            # Thresholding to make text clear
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
            
            # OCR đặc tả chữ số và dấu phân cách thời gian
            text = pytesseract.image_to_string(thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789:.,')
            text = text.strip().replace(',', '.')
            
            # Tìm định dạng mm:ss hoặc mm:ss.s
            match_colon = re.search(r'(\d+):(\d{2}(?:\.\d+)?)', text)
            if match_colon:
                m = int(match_colon.group(1))
                s = float(match_colon.group(2))
                return float(m * 60 + s)
                
            # Tìm định dạng ss.s (khi < 10s)
            match_dot = re.search(r'(\d+\.\d+)', text)
            if match_dot:
                return float(match_dot.group(1))
                
            # Lọc số nguyên cuối cùng để tránh rác OCR
            nums = re.findall(r'\d+', text)
            if nums:
                return float(nums[-1])
        except Exception:
            # Giữ giá trị cũ nếu OCR lỗi
            return None
            
        return None

    def pixel_to_square(self, x, y):
        col = int(x / self.sq_width)
        row = int(y / self.sq_height)
        
        # Đảm bảo giới hạn trong [0, 7]
        col = max(0, min(7, col))
        row = max(0, min(7, row))
        
        # Chuyển Pixel sang tọa độ bàn cờ
        if self.player_color == "black":
            # Đen: Top-Left là h1, Bottom-Right là a8
            file_char = chr(ord('h') - col)
            rank_char = str(row + 1)
        else:
            # Trắng: Top-Left là a8, Bottom-Right là h1
            file_char = chr(ord('a') + col)
            rank_char = str(8 - row)
            
        return file_char + rank_char

    def auto_detect_color(self, img):
        """
        Tự động nhận diện màu quân bằng cách so sánh độ sáng trung bình của
        hàng quân trên cùng và hàng quân dưới cùng.
        Chỉ hoạt động chính xác ở thế cờ xuất phát.
        """
        if not self.is_start_position_fast(img):
            return getattr(self, "player_color", "white")
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Trích xuất hàng trên và dưới cùng
        top_row_roi = gray[0 : int(self.sq_height), :]
        bottom_row_roi = gray[int(7 * self.sq_height) : int(8 * self.sq_height), :]
        
        # Cắt lề 25% để tập trung vào tâm ô cờ
        margin_y = int(self.sq_height * 0.25)
        top_row_center = top_row_roi[margin_y : int(self.sq_height) - margin_y, :]
        bottom_row_center = bottom_row_roi[margin_y : int(self.sq_height) - margin_y, :]
        
        top_brightness = np.mean(top_row_center)
        bottom_brightness = np.mean(bottom_row_center)
        
        # So sánh độ sáng để phân biệt phe
        # Hàng dưới sáng hơn -> Người chơi cầm Trắng
        if bottom_brightness > top_brightness:
            return "white"
        else:
            return "black"

    def detect_move(self, prev_img, curr_img):
        """
        So sánh 2 khung hình để tìm ra tọa độ nước đi bị thay đổi.
        Trả về danh sách các ô thay đổi, ví dụ: ['e2', 'e4']
        """
        # 1. So sánh sự khác biệt tuyệt đối
        diff = cv2.absdiff(prev_img, curr_img)
        
        # Lấy chênh lệch màu lớn nhất giữa 3 kênh RGB
        # Giữ nguyên RGB vì highlight của Chess.com rất đậm màu Blue
        gray = np.max(diff, axis=2).astype(np.uint8)
        # Ngưỡng threshold 40 để lọc nhiễu 
        # Triệt tiêu nhiễu video và highlight mờ
        _, thresh = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)
        
        changed_squares_data = []
        
        # Tính diện tích tối thiểu (10% của 1 ô)
        min_pixels = (self.sq_width * self.sq_height) * 0.1
        
        # 3. Quét qua từng ô trên bàn cờ (8x8)
        for row in range(8):
            for col in range(8):
                # Tính toạ độ của ô này trong ảnh
                x1 = int(col * self.sq_width)
                y1 = int(row * self.sq_height)
                x2 = int((col + 1) * self.sq_width)
                y2 = int((row + 1) * self.sq_height)
                
                # Cắt viền 15% của ô cờ để tập trung vùng lõi
                margin_x = int((x2 - x1) * 0.15)
                margin_y = int((y2 - y1) * 0.15)
                
                x1_core = x1 + margin_x
                x2_core = x2 - margin_x
                y1_core = y1 + margin_y
                y2_core = y2 - margin_y
                
                # Cắt vùng ảnh nhị phân của lõi ô cờ
                square_thresh = thresh[y1_core:y2_core, x1_core:x2_core]
                
                # Đếm số pixel bị thay đổi (màu trắng)
                intersect_area = cv2.countNonZero(square_thresh)
                square_area = (x2_core - x1_core) * (y2_core - y1_core)
                
                crop_gray = gray[y1_core:y2_core, x1_core:x2_core]
                if intersect_area > 0:
                    max_diff = np.max(crop_gray[square_thresh > 0])
                else:
                    max_diff = 0
                
                # Ngưỡng diện tích 15% để lọc trỏ chuột
                if intersect_area > 0.15 * square_area and max_diff > 50:
                        
                    # Chuyển đổi row, col sang toạ độ cờ
                    if self.player_color == "black":
                        file_char = chr(ord('h') - col)
                        rank_char = str(row + 1)
                    else:
                        file_char = chr(ord('a') + col)
                        rank_char = str(8 - row)
                    
                    sq_name = f"{file_char}{rank_char}"
                    changed_squares_data.append({
                        "name": sq_name,
                        "max_diff": max_diff
                    })
                    
        # Ưu tiên theo cường độ thay đổi màu (max_diff)
        # Quân cờ có chênh lệch màu lớn hơn Highlight
        changed_squares_data.sort(key=lambda x: x['max_diff'], reverse=True)
        return [sq['name'] for sq in changed_squares_data]

    def image_to_fen(self, img, turn_to_move=None, fallback_board=None):
        import glob
        import os
        import cv2
        import numpy as np

        if not os.path.exists("templates"):
            print("[System] Thư mục 'templates' không tồn tại. Vui lòng tạo thư mục và thêm các ảnh mẫu.")
            return None

        templates = {}
        fen_map = {
            'wk': 'K', 'wq': 'Q', 'wr': 'R', 'wb': 'B', 'wn': 'N', 'wp': 'P',
            'bk': 'k', 'bq': 'q', 'br': 'r', 'bb': 'b', 'bn': 'n', 'bp': 'p'
        }

        for path in glob.glob("templates/*.png"):
            filename = os.path.basename(path).lower()
            piece_type = filename[:2] 
            if piece_type in fen_map:
                tpl = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if tpl is not None:
                    if piece_type not in templates:
                        templates[piece_type] = []
                    templates[piece_type].append(tpl)

        if not templates:
            print("[System] Không tìm thấy ảnh mẫu nào trong thư mục 'templates'.")
            return None

        board = [['' for _ in range(8)] for _ in range(8)]
        
        # Xác định góc nhìn bàn cờ
        board_orientation = self.auto_detect_color(img)

        import chess
        fen_to_type = {v: k for k, v in fen_map.items()}

        # Lặp qua 64 ô cờ trên ảnh
        for row in range(8):
            for col in range(8):
                x1 = int(col * self.sq_width)
                y1 = int(row * self.sq_height)
                x2 = int((col + 1) * self.sq_width)
                y2 = int((row + 1) * self.sq_height)
                
                square_img = img[y1:y2, x1:x2]
                
                actual_row = 7 - row if board_orientation == "black" else row
                actual_col = 7 - col if board_orientation == "black" else col
                
                best_match_val = 0
                best_match_piece = ''
                
                # Tối ưu hóa đối chiếu template
                # Ưu tiên kiểm tra quân cờ cũ từ fallback_board 
                # Nếu khớp > 75%, bỏ qua quét các quân khác
                skip_others = False
                if fallback_board:
                    sq = (7 - actual_row) * 8 + actual_col
                    p = fallback_board.piece_at(sq)
                    if p:
                        expected_char = p.symbol()
                        expected_type = fen_to_type.get(expected_char)
                        if expected_type and expected_type in templates:
                            for tpl in templates[expected_type]:
                                if tpl.shape[2] == 4:
                                    mask = tpl[:, :, 3]
                                    tpl_color = tpl[:, :, :3]
                                    if tpl_color.shape[0] > square_img.shape[0] or tpl_color.shape[1] > square_img.shape[1]: continue
                                    res = cv2.matchTemplate(square_img, tpl_color, cv2.TM_CCORR_NORMED, mask=mask)
                                else:
                                    if tpl.shape[0] > square_img.shape[0] or tpl.shape[1] > square_img.shape[1]: continue
                                    res = cv2.matchTemplate(square_img, tpl, cv2.TM_CCOEFF_NORMED)
                                _, max_val, _, _ = cv2.minMaxLoc(res)
                                if max_val > 0.75:
                                    best_match_val = max_val
                                    best_match_piece = expected_char
                                    skip_others = True
                                    break
                
                if not skip_others:
                    for piece_type, tpl_list in templates.items():
                        for tpl in tpl_list:
                            if tpl.shape[2] == 4:
                                mask = tpl[:, :, 3]
                                tpl_color = tpl[:, :, :3]
                                if tpl_color.shape[0] > square_img.shape[0] or tpl_color.shape[1] > square_img.shape[1]:
                                    continue
                                result = cv2.matchTemplate(square_img, tpl_color, cv2.TM_CCORR_NORMED, mask=mask)
                            else:
                                if tpl.shape[0] > square_img.shape[0] or tpl.shape[1] > square_img.shape[1]:
                                    continue
                                result = cv2.matchTemplate(square_img, tpl, cv2.TM_CCOEFF_NORMED)
                                
                            _, max_val, _, _ = cv2.minMaxLoc(result)
                            if max_val > best_match_val:
                                best_match_val = max_val
                                best_match_piece = fen_map[piece_type]
                            
                # Ngưỡng template matching
                if best_match_val > 0.55:
                    board[actual_row][actual_col] = best_match_piece

        # --- RECOVERY TỐI THƯỢNG ---
        # Khôi phục Vua bị lỗi do nhiễu 
        # Thiếu Vua thường do nhiễu OpenCV
        # Dùng fallback_board để khôi phục Vua
        if fallback_board:
            import chess
            
            has_wk = any('K' in r for r in board)
            has_bk = any('k' in r for r in board)
            
            if not has_wk:
                wk_sq = fallback_board.king(chess.WHITE)
                if wk_sq is not None:
                    r = 7 - (wk_sq // 8)
                    c = wk_sq % 8
                    board[r][c] = 'K'
                    
            if not has_bk:
                bk_sq = fallback_board.king(chess.BLACK)
                if bk_sq is not None:
                    r = 7 - (bk_sq // 8)
                    c = bk_sq % 8
                    board[r][c] = 'k'

        fen_rows = []
        for row in range(8):
            empty_count = 0
            row_str = ""
            for col in range(8):
                piece = board[row][col]
                if piece == '':
                    empty_count += 1
                else:
                    if empty_count > 0:
                        row_str += str(empty_count)
                        empty_count = 0
                    row_str += piece
            if empty_count > 0:
                row_str += str(empty_count)
            fen_rows.append(row_str)
            
        fen_board = "/".join(fen_rows)
        
        if turn_to_move is None:
            turn = 'w' if self.player_color == "white" else 'b'
        else:
            turn = turn_to_move
            
        # Khôi phục trạng thái nhập thành
        castling = ""
        # Trắng: e1 (Vua), h1 (Xe), a1 (Xe)
        if board[7][4] == 'K':
            if board[7][7] == 'R': castling += "K"
            if board[7][0] == 'R': castling += "Q"
        # Đen: e8 (Vua), h8 (Xe), a8 (Xe)
        if board[0][4] == 'k':
            if board[0][7] == 'r': castling += "k"
            if board[0][0] == 'r': castling += "q"
            
        if not castling:
            castling = "-"
            
        # Thế cờ mặc định: Lượt của Trắng
        # Ngăn chặn đánh nhầm lượt lúc mới vào game
        start_fen_w = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        start_fen_b = "RNBQKBNR/PPPPPPPP/8/8/8/8/pppppppp/rnbqkbnr" # FEN xuất phát góc nhìn Đen
        
        if fen_board == start_fen_w or fen_board == start_fen_b:
            turn = 'w'
            castling = "KQkq"
            
        # Bỏ qua En Passant khi resync vì thiếu lịch sử
        fen_full = f"{fen_board} {turn} {castling} - 0 1"
        
        return fen_full

    def find_new_game_button(self, img):
        import cv2
        import numpy as np
        import glob
        import os

        if not hasattr(self, '_new_game_templates'):
            self._new_game_templates = []
            for path in glob.glob("templates/ui/*.png"):
                if os.path.exists(path):
                    tpl = cv2.imread(path, cv2.IMREAD_COLOR)
                    if tpl is not None:
                        self._new_game_templates.append(tpl)

        if not self._new_game_templates:
            return None

        # Tìm trên toàn bộ bàn cờ thay vì crop
        crop = img
        x1, y1 = 0, 0

        for tpl in self._new_game_templates:
            if tpl.shape[0] > crop.shape[0] or tpl.shape[1] > crop.shape[1]:
                continue
                
            res = cv2.matchTemplate(crop, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val > 0.8:
                # Get center of template
                cx = max_loc[0] + tpl.shape[1] // 2
                cy = max_loc[1] + tpl.shape[0] // 2
                
                # Convert to absolute screen coordinates
                abs_x = self.bbox["left"] + x1 + cx
                abs_y = self.bbox["top"] + y1 + cy
                return (abs_x, abs_y)
        return None

    def is_start_position_fast(self, img):
        import cv2
        
        row_height = self.sq_height
        
        # Rank 7 (index 1) and Rank 2 (index 6)
        y1_r7 = int(1 * row_height)
        y2_r7 = int(2 * row_height)
        rank7_img = img[y1_r7:y2_r7, :]
        
        y1_r2 = int(6 * row_height)
        y2_r2 = int(7 * row_height)
        rank2_img = img[y1_r2:y2_r2, :]
        
        y1_r4 = int(3 * row_height)
        y2_r4 = int(4 * row_height)
        rank4_img = img[y1_r4:y2_r4, :]
        
        def get_edges(roi):
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            return cv2.countNonZero(edges)
            
        edge7 = get_edges(rank7_img)
        edge2 = get_edges(rank2_img)
        edge4 = get_edges(rank4_img)
        
        # Vị trí xuất phát: Hàng 2, 7 có quân, hàng 4 trống
        # So sánh cạnh để xác thực khởi đầu ván
        # Phát hiện Midgame qua cấu trúc hàng
        if edge7 > edge4 * 2 and edge2 > edge4 * 2:
            return True
        return False
