import os
import json
import cv2
import numpy as np
import mss
import time
import sys

from core.capture import BoardCapture

def find_board_auto(img_bgr):
    """
    Tự động tìm vùng bàn cờ bằng cách tìm Contour hình vuông lớn nhất trên màn hình.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # Tìm viền cạnh
    edges = cv2.Canny(gray, 50, 150)
    
    # Lấy contours
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    best_bbox = None
    max_area = 0
    
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        
        # Bỏ qua các contour quá nhỏ
        if w < 200 or h < 200:
            continue
            
        aspect_ratio = float(w) / h
        
        # Bàn cờ luôn là hình vuông (tỷ lệ xấp xỉ 1)
        if 0.95 <= aspect_ratio <= 1.05:
            if area > max_area:
                max_area = area
                best_bbox = (x, y, w, h)
                
    return best_bbox

def measure_and_save_bbox():
    print("=========================================")
    print("    AUTO DETECT SETUP (TỰ ĐỘNG ĐO BÀN CỜ)")
    print("=========================================")
    print("Vui lòng đảm bảo:")
    print("1. Trình duyệt đang mở Chess.com (hoặc trang cờ của bạn) và THẤY RÕ BÀN CỜ.")
    print("2. Bàn cờ đang ở vị trí XUẤT PHÁT (chưa có nước đi nào).")
    print("3. Góc nhìn của bạn có thể là Trắng hoặc Đen (Tool sẽ tự nhận diện).")
    print("=========================================")
    input("Nhấn Enter để bắt đầu tìm bàn cờ tự động...")
    
    print("\nĐang quét màn hình trong 3 giây...")
    time.sleep(3)
    
    config = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except:
            pass

    with mss.mss() as sct:
        monitor = sct.monitors[1] # Màn hình chính
        img = np.array(sct.grab(monitor))
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        print("Đang phân tích hình ảnh...")
        bbox_rect = find_board_auto(img_bgr)
        
        if bbox_rect:
            x, y, w, h = bbox_rect
            bbox = {
                'top': int(y + monitor['top']), 
                'left': int(x + monitor['left']), 
                'width': int(w), 
                'height': int(h)
            }
            print(f"\n[Thành công] Đã TỰ ĐỘNG tìm thấy bàn cờ tại: {bbox}")
            
            # Hiển thị để xác nhận (chỉ vẽ hình chữ nhật)
            preview = img_bgr.copy()
            cv2.rectangle(preview, (x, y), (x+w, y+h), (0, 255, 0), 3)
            cv2.putText(preview, "Ban co duoc tim thay! Nhan ENTER de xac nhan, C de huy", 
                        (x, max(30, y-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            window_name = "Xac nhan Ban Co (ENTER = OK, C = Huy)"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            cv2.imshow(window_name, preview)
            
            key = cv2.waitKey(0)
            cv2.destroyWindow(window_name)
            
            if key in [13, 32]: # Enter or Space
                config["bbox"] = bbox
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4)
                print("Đã lưu tọa độ bàn cờ vào config.json!")
            else:
                print("\n[!] Bạn đã từ chối vùng nhận diện tự động.")
                return False
        else:
            print("\n[Thất bại] Không thể tìm thấy bàn cờ tự động.")
            print("Sử dụng chế độ chọn bằng tay...")
            
            window_name = "Select Board (Nhan ENTER de chot)"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            
            roi_board = cv2.selectROI(window_name, img_bgr, showCrosshair=True, fromCenter=False)
            cv2.destroyWindow(window_name)
            
            if roi_board[2] > 0 and roi_board[3] > 0:
                bbox = {
                    'top': int(roi_board[1] + monitor['top']), 
                    'left': int(roi_board[0] + monitor['left']), 
                    'width': int(roi_board[2]), 
                    'height': int(roi_board[3])
                }
                print(f"\n[Thành công] Đã lấy tọa độ bàn cờ thủ công: {bbox}")
                config["bbox"] = bbox
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4)
            else:
                print("\n[!] Bạn đã hủy chọn vùng bàn cờ.")
                return False

        return True

def extract_templates():
    print("\n=== BƯỚC 2: TRÍCH XUẤT ẢNH MẪU TỰ ĐỘNG ===")

    if not os.path.exists("templates"):
        os.makedirs("templates")

    cap = BoardCapture()
    try:
        cap.select_roi()
    except Exception as e:
        print(f"[!] Lỗi: {e}")
        return False
        
    img = cap.get_board_image()
    
    detected_color = cap.auto_detect_color(img)
    cap.player_color = detected_color
    
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        config["player_color"] = detected_color
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    print(f"[System] Tự động nhận diện góc nhìn: {detected_color.upper()}")

    if detected_color == "white":
        starting_board = {
            (0, 0): 'br', (0, 1): 'bn', (0, 2): 'bb', (0, 3): 'bq',
            (0, 4): 'bk', (0, 5): 'bb', (0, 6): 'bn', (0, 7): 'br',
            (1, 0): 'bp', (1, 1): 'bp', (1, 2): 'bp', (1, 3): 'bp',
            (1, 4): 'bp', (1, 5): 'bp', (1, 6): 'bp', (1, 7): 'bp',
            
            (6, 0): 'wp', (6, 1): 'wp', (6, 2): 'wp', (6, 3): 'wp',
            (6, 4): 'wp', (6, 5): 'wp', (6, 6): 'wp', (6, 7): 'wp',
            (7, 0): 'wr', (7, 1): 'wn', (7, 2): 'wb', (7, 3): 'wq',
            (7, 4): 'wk', (7, 5): 'wb', (7, 6): 'wn', (7, 7): 'wr'
        }
    else:
        starting_board = {
            (0, 0): 'wr', (0, 1): 'wn', (0, 2): 'wb', (0, 3): 'wk',
            (0, 4): 'wq', (0, 5): 'wb', (0, 6): 'wn', (0, 7): 'wr',
            (1, 0): 'wp', (1, 1): 'wp', (1, 2): 'wp', (1, 3): 'wp',
            (1, 4): 'wp', (1, 5): 'wp', (1, 6): 'wp', (1, 7): 'wp',
            
            (6, 0): 'bp', (6, 1): 'bp', (6, 2): 'bp', (6, 3): 'bp',
            (6, 4): 'bp', (6, 5): 'bp', (6, 6): 'bp', (6, 7): 'bp',
            (7, 0): 'br', (7, 1): 'bn', (7, 2): 'bb', (7, 3): 'bk',
            (7, 4): 'bq', (7, 5): 'bb', (7, 6): 'bn', (7, 7): 'br'
        }

    count = 0
    for (row, col), piece_name in starting_board.items():
        x1 = int(col * cap.sq_width)
        y1 = int(row * cap.sq_height)
        x2 = int((col + 1) * cap.sq_width)
        y2 = int((row + 1) * cap.sq_height)
        
        square_img = img[y1:y2, x1:x2]
        
        pad_x = int((x2 - x1) * 0.15)
        pad_y = int((y2 - y1) * 0.15)
        cropped_img = square_img[pad_y:-pad_y, pad_x:-pad_x]
        
        filename = f"templates/{piece_name}_{row}_{col}.png"
        cv2.imwrite(filename, cropped_img)
        count += 1

    print(f"\n[Thành công] Đã trích xuất {count} ảnh mẫu vào thư mục 'templates/'!")
    return True

def setup_clock():
    print("\n=== BƯỚC 3: CHỌN VÙNG ĐỒNG HỒ CỦA BẠN (TÙY CHỌN) ===")
    ans = input("Bạn có muốn thiết lập tọa độ đồng hồ không? (Y/n): ")
    if ans.lower() == 'n':
        print("[INFO] Đã bỏ qua thiết lập đồng hồ.")
        return

    print("\nVui lòng kéo thả chuột để chọn VÙNG ĐỒNG HỒ THỜI GIAN của bạn.")
    print(" - Nhấn ENTER hoặc SPACE để chốt tọa độ.")
    print(" - Nhấn phím C để bỏ qua bước này.")
    
    print("\nĐang chụp màn hình trong 3 giây...")
    time.sleep(3)
    
    config = {}
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        window_name_clock = "Select Clock (Nhan ENTER de chot, C de huy)"
        cv2.namedWindow(window_name_clock, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(window_name_clock, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        roi_clock = cv2.selectROI(window_name_clock, img_bgr, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow(window_name_clock)
        
        if roi_clock[2] > 0 and roi_clock[3] > 0:
            clock_region = {
                'top': int(roi_clock[1] + monitor['top']), 
                'left': int(roi_clock[0] + monitor['left']), 
                'width': int(roi_clock[2]), 
                'height': int(roi_clock[3])
            }
            print(f"\n[Thành công] Đã lấy tọa độ đồng hồ: {clock_region}")
            config["clock_region"] = clock_region
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            print("Đã lưu tọa độ đồng hồ vào config.json!")
        else:
            print("\n[INFO] Đã bỏ qua chọn vùng đồng hồ.")

if __name__ == "__main__":
    if measure_and_save_bbox():
        if extract_templates():
            setup_clock()
    print("\nHoàn tất cài đặt! Bạn có thể chạy 'python main.py' để bắt đầu.")
