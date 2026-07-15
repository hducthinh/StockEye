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

if __name__ == "__main__":
    measure_and_save_bbox()
