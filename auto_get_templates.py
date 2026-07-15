import os
import json
import cv2
import numpy as np
import mss
import time
from capture import BoardCapture

def measure_and_save_bbox():
    print("=== BƯỚC 1: CHỌN VÙNG BÀN CỜ ===")
    print("Vui lòng kéo thả chuột để chọn VÙNG BÀN CỜ.")
    print(" - Nhấn ENTER hoặc SPACE để chốt tọa độ.")
    print(" - Nhấn phím C để hủy bỏ.")
    
    print("\nBạn có 2 giây để chuyển sang trình duyệt chứa bàn cờ...")
    time.sleep(2)
    print("Đang chụp màn hình...")
    
    with mss.mss() as sct:
        monitor = sct.monitors[1] # Màn hình chính
        img = np.array(sct.grab(monitor))
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        window_name = "Select Board (Nhan ENTER de chot)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        roi = cv2.selectROI(window_name, img_bgr, showCrosshair=True, fromCenter=False)
        cv2.destroyAllWindows()
        
        if roi[2] > 0 and roi[3] > 0:
            bbox = {
                'top': int(roi[1] + monitor['top']), 
                'left': int(roi[0] + monitor['left']), 
                'width': int(roi[2]), 
                'height': int(roi[3])
            }
            print(f"\n[Thành công] Đã lấy tọa độ bàn cờ: {bbox}")
            
            # Lưu vào config.json
            config = {}
            if os.path.exists("config.json"):
                try:
                    with open("config.json", "r", encoding="utf-8") as f:
                        config = json.load(f)
                except:
                    pass
            
            config["bbox"] = bbox
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
                
            print("Đã tự động lưu tọa độ vào config.json!")
            return True
        else:
            print("\n[!] Bạn đã hủy đo tọa độ.")
            return False

def main():
    print("=========================================")
    print("    AUTO SETUP SCRIPT (ĐO BÀN CỜ & LẤY ẢNH MẪU)")
    print("=========================================")
    print("Vui lòng đảm bảo:")
    print("1. Trình duyệt đang mở Chess.com (hoặc trang cờ của bạn).")
    print("2. Bàn cờ đang ở vị trí XUẤT PHÁT (chưa có nước đi nào).")
    print("3. Góc nhìn của bạn có thể là Trắng hoặc Đen (Tool sẽ tự nhận diện).")
    print("=========================================")
    input("Nhấn Enter để bắt đầu...")

    # Bước 1: Đo và lưu tọa độ bàn cờ
    if not measure_and_save_bbox():
        return
        
    print("\n=== BƯỚC 2: TRÍCH XUẤT ẢNH MẪU TỰ ĐỘNG ===")

    if not os.path.exists("templates"):
        os.makedirs("templates")

    cap = BoardCapture()
    try:
        cap.select_roi()
    except Exception as e:
        print(f"[!] Lỗi: {e}")
        return
        
    img = cap.get_board_image()
    
    # Tự động nhận diện màu quân cờ hiện tại
    detected_color = cap.auto_detect_color(img)
    cap.player_color = detected_color
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
        # Nếu là Black, màn hình lật ngược:
        # Hàng trên cùng (Row 0) là Rank 1 (chứa quân Trắng)
        # Hàng dưới cùng (Row 7) là Rank 8 (chứa quân Đen)
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
        
        # Cắt bớt 15% lề ở mỗi cạnh để loại bỏ viền của ô vuông nếu có
        pad_x = int((x2 - x1) * 0.15)
        pad_y = int((y2 - y1) * 0.15)
        cropped_img = square_img[pad_y:-pad_y, pad_x:-pad_x]
        
        filename = f"templates/{piece_name}_{row}_{col}.png"
        cv2.imwrite(filename, cropped_img)
        count += 1

    print(f"\n[Thành công] Đã trích xuất {count} ảnh mẫu vào thư mục 'templates/'!")
    print("Bây giờ bạn có thể mở lại Terminal và chạy: python main.py")

if __name__ == "__main__":
    main()
