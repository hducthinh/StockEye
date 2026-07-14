import cv2
import numpy as np
import mss

def main():
    print("=== TOOL ĐO TỌA ĐỘ BÀN CỜ ===")
    print("Vui lòng kéo thả chuột để chọn VÙNG BÀN CỜ.")
    print(" - Nhấn ENTER hoặc SPACE để chốt tọa độ.")
    print(" - Nhấn phím C để hủy bỏ.")
    
    import time
    print("Bạn có 2 giây để chuyển sang trình duyệt chứa bàn cờ...")
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
            print("\n>>> KẾT QUẢ ĐO ĐƯỢC: <<<")
            print(f"self.bbox = {bbox}")
            print("\nBạn hãy copy dòng trên và dán (hard-code) đè vào hàm select_roi() trong file capture.py nhé!")
        else:
            print("\n[!] Bạn đã hủy đo tọa độ.")

if __name__ == "__main__":
    main()
