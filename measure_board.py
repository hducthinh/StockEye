import os
import json
import cv2
import numpy as np
import mss
import time

def measure_and_save_bbox():
    print("=== BƯỚC 1: CHỌN VÙNG BÀN CỜ ===")
    print("Vui lòng kéo thả chuột để chọn VÙNG BÀN CỜ.")
    print(" - Nhấn ENTER hoặc SPACE để chốt tọa độ.")
    print(" - Nhấn phím C để hủy bỏ.")
    
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
        return True

if __name__ == "__main__":
    measure_and_save_bbox()
