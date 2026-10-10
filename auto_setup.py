import os
import cv2
import numpy as np
import mss
import time
import sys
import glob

from core.config import load_config, save_config, templates_dir

def find_board_auto(img_bgr):
    """
    Tự động tìm vùng bàn cờ bằng cách tìm Contour hình vuông lớn nhất có cấu trúc ô cờ trên màn hình.
    """
    h_screen, w_screen = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    candidates = []

    def checker_score(x, y, w, h):
        roi = gray[y:y + h, x:x + w]
        means = np.zeros((8, 8), dtype=np.float32)
        for row in range(8):
            for col in range(8):
                y1, y2 = round(row * h / 8), round((row + 1) * h / 8)
                x1, x2 = round(col * w / 8), round((col + 1) * w / 8)
                cell = roi[y1:y2, x1:x2]
                margin_y, margin_x = max(1, cell.shape[0] // 5), max(1, cell.shape[1] // 5)
                core = cell[margin_y:-margin_y, margin_x:-margin_x]
                means[row, col] = float(np.mean(core))
        even = means[(np.indices((8, 8)).sum(axis=0) % 2) == 0]
        odd = means[(np.indices((8, 8)).sum(axis=0) % 2) == 1]
        contrast = abs(float(np.median(even)) - float(np.median(odd)))
        spread = float(np.std(even) + np.std(odd))
        return contrast / max(8.0, spread)
    
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        
        # Bàn cờ tối thiểu 280x280 và không vượt quá 98% kích thước màn hình
        if w < 280 or h < 280 or w > w_screen * 0.98 or h > h_screen * 0.98:
            continue
            
        aspect_ratio = float(w) / h
        
        # Bàn cờ chuẩn là hình vuông (sai số +/- 4%)
        if 0.96 <= aspect_ratio <= 1.04:
            score = checker_score(x, y, w, h)
            if score >= 0.18:
                area = w * h
                candidates.append((score * area, (x, y, w, h)))
            
    if not candidates:
        return None
        
    # Sắp xếp theo diện tích lớn nhất giảm dần
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def get_board_bbox():
    """
    Quét màn hình và xác định tọa độ bàn cờ (tự động hoặc thủ công).
    """
    sct_class = getattr(mss, 'MSS', mss.mss)
    with sct_class() as sct:
        monitor = sct.monitors[0]  # Toàn bộ virtual desktop, gồm cả màn hình phụ
        img = np.array(sct.grab(monitor))
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        print("\n[*] Đang tự động quét và phân tích hình ảnh bàn cờ...")
        bbox_rect = find_board_auto(img_bgr)
        
        if bbox_rect:
            x, y, w, h = bbox_rect
            print(f"[+] Đã TỰ ĐỘNG phát hiện bàn cờ: x={x}, y={y}, w={w}, h={h}")
            
            # Hiển thị cửa sổ xem trước để người dùng xác nhận
            preview = img_bgr.copy()
            cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 0), 3)
            
            # Thêm banner hướng dẫn
            banner_y = max(35, y - 15)
            cv2.rectangle(preview, (x, banner_y - 25), (x + min(w, 750), banner_y + 5), (0, 0, 0), -1)
            cv2.putText(
                preview, 
                "ENTER/SPACE: Chot | C: Tu keo bang tay | ESC: Huy", 
                (x + 5, banner_y - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.6, 
                (0, 255, 0), 
                2
            )
            
            window_name = "Xac nhan Ban Co (ENTER=Chot, C=Chon bang tay, ESC=Huy)"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            cv2.imshow(window_name, preview)
            
            key = cv2.waitKey(0) & 0xFF
            cv2.destroyWindow(window_name)
            
            if key in [13, 32]: # ENTER hoặc SPACE
                print("[+] Bạn đã xác nhận vùng bàn cờ tự động!")
                return {
                    'top': int(y + monitor['top']), 
                    'left': int(x + monitor['left']), 
                    'width': int(w), 
                    'height': int(h)
                }, img_bgr[y:y+h, x:x+w]
            elif key in [ord('c'), ord('C')]:
                print("[*] Chuyển sang chế độ chọn bàn cờ bằng tay...")
            else:
                print("[!] Đã hủy cài đặt.")
                return None, None
        else:
            print("[!] Không tìm thấy bàn cờ tự động. Chuyển sang chế độ chọn bằng tay...")

        # Chế độ chọn bằng tay (Fallback)
        print("\n[*] Vui lòng dùng chuột kéo thả để chọn toàn bộ vùng bàn cờ 8x8.")
        print("    - Nhấn ENTER hoặc SPACE khi đã kéo xong để chốt.")
        print("    - Nhấn C để hủy.")
        
        window_name = "Keo chon Ban Co (ENTER de chot, C de huy)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        roi = cv2.selectROI(window_name, img_bgr, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow(window_name)
        
        rx, ry, rw, rh = roi
        if rw > 50 and rh > 50:
            print(f"[+] Đã chọn bàn cờ thủ công: x={rx}, y={ry}, w={rw}, h={rh}")
            return {
                'top': int(ry + monitor['top']), 
                'left': int(rx + monitor['left']), 
                'width': int(rw), 
                'height': int(rh)
            }, img_bgr[ry:ry+rh, rx:rx+rw]
        else:
            print("[!] Bạn đã hủy chọn vùng bàn cờ.")
            return None, None


def detect_player_color(board_img):
    """
    Tự động nhận diện người chơi cầm quân Trắng hay Đen ở thế cờ xuất phát.
    So sánh độ sáng hàng quân trên (Rank 7-8) vs hàng quân dưới (Rank 1-2).
    """
    h, w = board_img.shape[:2]
    sq_h = h / 8.0
    gray = cv2.cvtColor(board_img, cv2.COLOR_BGR2GRAY)
    
    # Lấy vùng hàng 1-2 (quân trên) và hàng 7-8 (quân dưới)
    top_region = gray[0 : int(sq_h * 2), :]
    bottom_region = gray[int(sq_h * 6) : h, :]
    
    top_brightness = np.mean(top_region)
    bottom_brightness = np.mean(bottom_region)
    
    # Hàng dưới sáng hơn -> Người chơi cầm Trắng
    if bottom_brightness > top_brightness:
        return "white"
    else:
        return "black"


def extract_piece_templates(board_img, detected_color):
    """
    Trích xuất toàn bộ 32 quân cờ ở thế xuất phát và lưu vào thư mục templates/.
    """
    template_root = templates_dir()
    if not template_root.exists():
        template_root.mkdir(parents=True)
    else:
        # Xóa các template cũ để tránh lẫn lộn theme cờ
        for old_tpl in glob.glob(str(template_root / "*.png")):
            try:
                os.remove(old_tpl)
            except:
                pass

    h, w = board_img.shape[:2]
    sq_w = w / 8.0
    sq_h = h / 8.0

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
        # Góc nhìn Đen (bàn cờ bị lật ngược)
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
        x1 = int(col * sq_w)
        y1 = int(row * sq_h)
        x2 = int((col + 1) * sq_w)
        y2 = int((row + 1) * sq_h)
        
        square_img = board_img[y1:y2, x1:x2]
        filename = template_root / f"{piece_name}_{row}_{col}.png"
        cv2.imwrite(str(filename), square_img)
        count += 1

    # Lưu hai mẫu ô trống để profile có thể kiểm tra theme về sau.
    for label, row, col in (("empty_light", 2, 0), ("empty_dark", 2, 1)):
        x1, y1 = int(col * sq_w), int(row * sq_h)
        x2, y2 = int((col + 1) * sq_w), int((row + 1) * sq_h)
        square = board_img[y1:y2, x1:x2]
        cv2.imwrite(str(template_root / f"{label}.png"), square)

    print(f"[+] Đã trích xuất thành công {count} ảnh mẫu quân cờ vào thư mục 'templates/'!")
    return count


def main():
    print("=" * 55)
    print("      STOCKEYE - AUTO SETUP (TỰ ĐỘNG CÀI ĐẶT BÀN CỜ)")
    print("=" * 55)
    print("Vui lòng đảm bảo:")
    print("  1. Ứng dụng phân tích offline đang hiển thị bàn cờ đúng theme đã chọn.")
    print("  2. Bàn cờ đang ở vị trí XUẤT PHÁT (chưa có nước đi nào).")
    print("  3. Toàn bộ bàn cờ hiển thị rõ ràng trên một trong các màn hình.")
    print("=" * 55)
    input("Nhấn ENTER để bắt đầu quét bàn cờ...")
    
    print("\n[*] Bạn có 3 giây để chuyển sang cửa sổ trình duyệt...")
    for i in range(3, 0, -1):
        print(f"    Quét sau: {i}...")
        time.sleep(1)
        
    bbox, board_img = get_board_bbox()
    if bbox is None or board_img is None:
        print("\n[X] Quá trình cài đặt bị gián đoạn.")
        input("\nNhấn Enter để thoát...")
        return

    # Tự động nhận diện màu quân
    detected_color = detect_player_color(board_img)
    print(f"\n[+] Tự động nhận diện phe: {detected_color.upper()} (Độ sáng tối ưu)")

    config = load_config()
    config.update({
        "bbox": bbox,
        "board_orientation": detected_color,
        "selected_side": detected_color,
    })
    save_config(config)
    print("[+] Đã lưu cấu hình bàn cờ vào 'config.json'!")

    # Trích xuất templates
    print("\n[*] Đang trích xuất ảnh mẫu 32 quân cờ...")
    extract_piece_templates(board_img, detected_color)

    print("\n" + "=" * 55)
    print("            CÀI ĐẶT HOÀN TẤT THÀNH CÔNG!")
    print("=" * 55)
    print("Bây giờ bạn có thể khởi động StockEye bằng lệnh:")
    print("    python main.py")
    print("=" * 55)
    input("\nNhấn Enter để hoàn tất...")

if __name__ == "__main__":
    main()
