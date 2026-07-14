import cv2
import numpy as np
import mss
import json
import os

class BoardCapture:
    def __init__(self):
        self.sct = mss.mss()
        self.bbox = None
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
        """Sử dụng vùng bàn cờ mặc định thay vì chọn tay"""
        self.bbox = {'top': 192, 'left': 284, 'width': 743, 'height': 741}
        self.sq_width = self.bbox["width"] / 8.0
        self.sq_height = self.bbox["height"] / 8.0
        print(f"Đã thiết lập vùng bàn cờ mặc định: {self.bbox}")

    def get_board_image(self):
        """Chụp và trả về ảnh vùng bàn cờ hiện tại"""
        if not self.bbox:
            raise ValueError("Chưa chọn vùng bàn cờ. Vui lòng gọi select_roi() trước.")
            
        img = np.array(self.sct.grab(self.bbox))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def pixel_to_square(self, x, y):
        col = int(x / self.sq_width)
        row = int(y / self.sq_height)
        
        # Đảm bảo giới hạn trong [0, 7]
        col = max(0, min(7, col))
        row = max(0, min(7, row))
        
        # Chuyển đổi thành tọa độ bàn cờ dựa vào phe
        if self.player_color == "black":
            # Nếu là quân Đen, góc trái trên là h1, góc phải dưới là a8
            file_char = chr(ord('h') - col)
            rank_char = str(row + 1)
        else:
            # Nếu là quân Trắng, góc trái trên là a8, góc phải dưới là h1
            file_char = chr(ord('a') + col)
            rank_char = str(8 - row)
            
        return file_char + rank_char

    def auto_detect_color(self, img):
        """
        Tự động nhận diện màu quân bằng cách so sánh độ sáng trung bình của
        hàng quân trên cùng và hàng quân dưới cùng.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Cắt lấy hàng trên cùng và hàng dưới cùng
        top_row_roi = gray[0 : int(self.sq_height), :]
        bottom_row_roi = gray[int(7 * self.sq_height) : int(8 * self.sq_height), :]
        
        # Bỏ đi 25% lề trên dưới để tập trung vào tâm ô cờ (nơi chứa quân)
        margin_y = int(self.sq_height * 0.25)
        top_row_center = top_row_roi[margin_y : int(self.sq_height) - margin_y, :]
        bottom_row_center = bottom_row_roi[margin_y : int(self.sq_height) - margin_y, :]
        
        top_brightness = np.mean(top_row_center)
        bottom_brightness = np.mean(bottom_row_center)
        
        # Quân trắng sáng hơn quân đen. Background 2 hàng giống hệt nhau (4 sáng, 4 tối)
        # Nên nếu hàng dưới sáng hơn hàng trên -> Hàng dưới là quân Trắng -> Người chơi cầm Trắng
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
        
        # 2. Lấy chênh lệch lớn nhất ở bất kỳ kênh màu nào (B, G hoặc R)
        # Không dùng BGR2GRAY vì kênh Blue bị nhân hệ số rất nhỏ (0.114),
        # trong khi màu highlight của chess.com chủ yếu thay đổi mạnh ở kênh Blue!
        gray = np.max(diff, axis=2).astype(np.uint8)
        # [SỬA ĐỔI 1] Nâng ngưỡng threshold từ 5 lên 40. 
        # Triệt tiêu hoàn toàn nhiễu do nén video và highlight mờ nhạt.
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
                
                # Cắt vùng ảnh nhị phân của ô này
                square_thresh = thresh[y1:y2, x1:x2]
                
                # Đếm số pixel bị thay đổi (màu trắng)
                intersect_area = cv2.countNonZero(square_thresh)
                square_area = (x2 - x1) * (y2 - y1)
                
                crop_gray = gray[y1:y2, x1:x2]
                if intersect_area > 0:
                    max_diff = np.max(crop_gray[square_thresh > 0])
                else:
                    max_diff = 0
                
                # [Sửa lỗi] Kết hợp AND và nâng diện tích lên 15% (0.15) để lọc trỏ chuột
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
                    
        # Sắp xếp theo ĐỘ MẠNH của sự thay đổi màu sắc (max_diff) thay vì diện tích
        # Quân cờ biến mất/xuất hiện luôn tạo ra chênh lệch màu lớn hơn (max_diff > 150) so với Highlight (max_diff < 110)
        changed_squares_data.sort(key=lambda x: x['max_diff'], reverse=True)
        return [sq['name'] for sq in changed_squares_data]

    def image_to_fen(self, img, turn_to_move=None):
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
        
        # Tự động nhận diện góc nhìn bàn cờ 1 lần
        board_orientation = self.auto_detect_color(img)

        # Lặp qua 64 ô cờ trên ảnh
        for row in range(8):
            for col in range(8):
                x1 = int(col * self.sq_width)
                y1 = int(row * self.sq_height)
                x2 = int((col + 1) * self.sq_width)
                y2 = int((row + 1) * self.sq_height)
                
                square_img = img[y1:y2, x1:x2]
                
                best_match_val = 0
                best_match_piece = ''
                
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
                            
                # Ngưỡng chấp nhận (có thể cần tinh chỉnh tuỳ ảnh mẫu của người dùng)
                if best_match_val > 0.70:
                    if board_orientation == "black":
                        actual_row = 7 - row
                        actual_col = 7 - col
                    else:
                        actual_row = row
                        actual_col = col
                        
                    board[actual_row][actual_col] = best_match_piece

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
            
        # Mặc định mất quyền nhập thành và không bắt tốt qua đường khi resync giữa ván
        fen_full = f"{fen_board} {turn} - - 0 1"
        
        return fen_full
