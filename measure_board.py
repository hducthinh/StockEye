import os
import json
import cv2
import numpy as np
import mss
import time

def auto_find_chessboard(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    best_match = None
    max_area = 0
    
    for cnt in contours:
        epsilon = 0.05 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            area = w * h
            if 90000 < area < 2000000:
                aspect_ratio = float(w) / h
                if 0.95 <= aspect_ratio <= 1.05:
                    if area > max_area:
                        max_area = area
                        best_match = (x, y, w, h)
    return best_match

def measure_and_save_bbox():
    print("=== LỰA CHỌN CHẾ ĐỘ ĐO ===")
    print("1. Chỉ đo bàn cờ (không đo đồng hồ)")
    print("2. Đo bàn cờ và chọn khu vực đồng hồ")
    choice = input("Nhập lựa chọn của bạn (1 hoặc 2): ").strip()
    
    print("\n=== BƯỚC 1: TỰ ĐỘNG ĐO BÀN CỜ ===")
    print("\nBạn có 2 giây để chuyển sang trình duyệt chứa bàn cờ...")
    time.sleep(2)
    print("Đang chụp màn hình...")
    
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
        
        board_rect = auto_find_chessboard(img_bgr)
        
        if board_rect:
            x, y, w, h = board_rect
            bbox = {
                'top': int(y + monitor['top']), 
                'left': int(x + monitor['left']), 
                'width': int(w), 
                'height': int(h)
            }
            print(f"\n[Thành công] Đã tự động nhận diện bàn cờ: {bbox}")
            config["bbox"] = bbox
            pass
        else:
            print("\n[!] Không thể tự động nhận diện bàn cờ, chuyển sang đo thủ công...")
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
                print(f"\n[Thành công] Đã lấy tọa độ bàn cờ: {bbox}")
                config["bbox"] = bbox
            else:
                print("\n[!] Bạn đã hủy chọn vùng bàn cờ.")
                return False

        if choice == '2':
            print("\n=== BƯỚC 2: CHỌN VÙNG ĐỒNG HỒ CỦA BẠN (TÙY CHỌN) ===")
            print("Vui lòng kéo thả chuột để chọn VÙNG ĐỒNG HỒ THỜI GIAN của bạn (để BOT biết lúc nào cạn giờ).")
            print(" - Nhấn ENTER hoặc SPACE để chốt tọa độ.")
            print(" - Nhấn phím C để bỏ qua bước này.")
            
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
            else:
                print("\n[INFO] Đã bỏ qua chọn vùng đồng hồ.")
                
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
            
        print("Đã tự động lưu tọa độ vào config.json!")
        
        # Xem trước kết quả chung
        preview_img = img_bgr.copy()
        if "bbox" in config:
            bx = config["bbox"]["left"] - monitor["left"]
            by = config["bbox"]["top"] - monitor["top"]
            bw = config["bbox"]["width"]
            bh = config["bbox"]["height"]
            cv2.rectangle(preview_img, (bx, by), (bx+bw, by+bh), (0, 0, 255), 3)
            
        if "clock_region" in config and choice == '2':
            cx = config["clock_region"]["left"] - monitor["left"]
            cy = config["clock_region"]["top"] - monitor["top"]
            cw = config["clock_region"]["width"]
            ch = config["clock_region"]["height"]
            cv2.rectangle(preview_img, (cx, cy), (cx+cw, cy+ch), (0, 255, 0), 2)
            
        window_preview = "Kiem tra vung da chon (Nhan phim bat ky de dong)"
        cv2.namedWindow(window_preview, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(window_preview, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.imshow(window_preview, preview_img)
        print("\n=> Vui lòng xem khung màu trên màn hình và nhấn phím bất kỳ để kết thúc...")
        cv2.waitKey(0)
        cv2.destroyWindow(window_preview)
        return True

if __name__ == "__main__":
    measure_and_save_bbox()
