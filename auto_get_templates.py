import os
import cv2
from capture import BoardCapture

def main():
    print("=========================================")
    print("    AUTO-GET TEMPLATES SCRIPT")
    print("=========================================")
    print("Vui lòng đảm bảo:")
    print("1. Trình duyệt đang mở Chess.com (hoặc trang cờ của bạn).")
    print("2. Bàn cờ đang ở vị trí XUẤT PHÁT (chưa có nước đi nào).")
    print("3. Góc nhìn của bạn có thể là Trắng hoặc Đen (Tool sẽ tự nhận diện).")
    print("=========================================")
    input("Nhấn Enter để tiến hành chụp và trích xuất ảnh mẫu...")

    if not os.path.exists("templates"):
        os.makedirs("templates")

    cap = BoardCapture()
    cap.select_roi()
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
        
        # Cắt bớt 5% lề ở mỗi cạnh để loại bỏ viền của ô vuông nếu có
        pad_x = int((x2 - x1) * 0.05)
        pad_y = int((y2 - y1) * 0.05)
        cropped_img = square_img[pad_y:-pad_y, pad_x:-pad_x]
        
        filename = f"templates/{piece_name}_{row}_{col}.png"
        cv2.imwrite(filename, cropped_img)
        count += 1

    print(f"\n[Thành công] Đã trích xuất {count} ảnh mẫu vào thư mục 'templates/'!")
    print("Bạn có thể kiểm tra các file ảnh trong thư mục này.")
    print("Vì chúng ta trích xuất toàn bộ 32 quân cờ, hệ thống đã học được hầu hết")
    print("tất cả các trường hợp (quân cờ nằm trên nền tối / nền sáng).")
    print("Bây giờ bạn có thể quay lại main.py và nhấn F3 giữa ván để test Mắt Thần!")

if __name__ == "__main__":
    main()
