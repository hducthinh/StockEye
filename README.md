# 👁️‍🗨️ StockEye - The Ultimate Real-time Chess Assistant & Autobot

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=flat&logo=python)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg?style=flat&logo=opencv)
![PyQt](https://img.shields.io/badge/PyQt-5%2F6-red.svg?style=flat)
![Stockfish](https://img.shields.io/badge/Engine-Stockfish-orange.svg?style=flat)

**StockEye** là công cụ hỗ trợ phân tích cờ vua theo thời gian thực (Real-time) mạnh mẽ. Bằng sự kết hợp giữa **Thị giác máy tính (Computer Vision)** và siêu máy tính **Stockfish**, công cụ có khả năng đọc hiểu thế cờ ngay trên màn hình và gợi ý các nước đi tối ưu nhất thông qua một giao diện HUD (Heads-Up Display) tinh gọn, trực quan và hoàn toàn trong suốt.

---

## 🌟 Các Tính Năng Nổi Bật

- **Auto-Detect Chessboard & Templates:** Tự động phát hiện vị trí bàn cờ trên màn hình và tự động trích xuất bộ template 32 quân cờ mà không cần thao tác phức tạp hay cài đặt thêm phần mềm bên ngoài.
- **Auto-Tracker & Auto-Sync:** Tự động theo dõi chuyển động của quân cờ thông qua thuật toán `cv2.absdiff` siêu nhẹ, không tốn tài nguyên. Khả năng tự động đồng bộ lại thế cờ (Mid-game Sync) và nhận diện khi bắt đầu ván mới (New Game) cực kỳ mượt mà.
- **Visual Move Suggestions:** Hiển thị trực quan các nước đi tối ưu trực tiếp trên bàn cờ hoặc qua một bàn cờ phụ với các mũi tên màu sắc rõ ràng (Best Move, 2nd, 3rd, 4th).
- **Control Panel Tinh Gọn:** Giao diện điều khiển cho phép tùy chỉnh nóng mọi thông số: Bật/tắt vẽ lên bàn cờ, Ép phe (Trắng / Đen), Độ sâu Engine, số luồng CPU...
- **Invisible Overlay UI:** Lớp giao diện hiển thị bằng PyQt được thiết kế trong suốt (Transparent), xuyên cảm ứng (Click-through) và chống chụp màn hình (WDA_EXCLUDEFROMCAPTURE), mang đến trải nghiệm mượt mà không cản trở thao tác chuột.

---

## ⌨️ Hệ Thống Phím Tắt (Global Hotkeys)

Điều khiển ứng dụng từ bất kỳ đâu trên máy tính:

- `2` : **Bật / Tắt Gợi ý** (Vẽ mũi tên phân tích nước đi trên màn hình).
- `5` : **Ép phe Trắng** (Bắt công cụ hiểu rằng bạn đang cầm quân Trắng).
- `6` : **Ép phe Đen** (Bắt công cụ hiểu rằng bạn đang cầm quân Đen).
- `ESC` : **Hủy / Dừng khẩn cấp**.
- `F4` : **Thoát hoàn toàn ứng dụng**.

---

## 🛠️ Hướng Dẫn Cài Đặt (Installation)

### 1. Yêu Cầu Hệ Thống

- **Hệ điều hành:** Windows 10/11.
- **Python:** 3.9 trở lên.
- **Màn hình:** Độ phân giải 1920x1080 (khuyến nghị).

### 2. Cài Đặt Môi Trường

```bash
git clone https://github.com/hducthinh/StockEye.git
cd StockEye
pip install -r requirements.txt
```

> **Lưu ý Quan Trọng:** Hãy tải [Stockfish Engine](https://stockfishchess.org/download/) bản nhị phân (.exe) mới nhất và đặt vào thư mục `engine/` (Ví dụ: `engine/stockfish-windows-x86-64-avx2.exe`).

### 3. Cân Chỉnh Bàn Cờ (Chỉ làm 1 lần duy nhất)

Mỗi bàn cờ trên trình duyệt có kích thước khác nhau. Việc setup cực kỳ đơn giản:

1. Mở một bàn cờ **THẾ XUẤT PHÁT** (mới bắt đầu, 32 quân nằm đúng vị trí chuẩn) trên trình duyệt.
2. Chạy file cấu hình tự động:
   ```bash
   python auto_setup.py
   ```
3. Công cụ sẽ tự động quét và nhận diện bàn cờ. Bạn chỉ cần nhấn `Enter` để xác nhận (hoặc nhấn `C` để tự kéo thả vùng chọn bằng tay).
4. Tọa độ bàn cờ và bộ 32 ảnh mẫu (templates) sẽ được cắt và trích xuất hoàn toàn tự động!

### 4. Chạy Ứng Dụng

```bash
python main.py
```

---

## ⚖️ TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM (LEGAL DISCLAIMER)

**Dự án StockEye được phát triển ĐỘC QUYỀN cho các mục đích:**

1. Nghiên cứu khoa học máy tính, đặc biệt là xử lý ảnh (Computer Vision), nhận dạng OCR và tương tác mô phỏng chuột máy tính.
2. Phân tích cờ vua ngoại tuyến (Offline Analysis) chống lại các Engine khác hoặc tự luyện tập để nâng cao trình độ.

> ⚠️ **NGHIÊM CẤM:**
> Việc sử dụng công cụ này (đặc biệt là các tính năng tự động đánh Autoplay / Autofarm nếu có) trên các nền tảng cờ vua trực tuyến (như Chess.com, Lichess.org) trong các ván đấu có tính điểm xếp hạng (Ranked games). Hành vi này vi phạm nghiêm trọng Điều khoản Dịch vụ (Terms of Service) và Chính sách Công bằng (Fair Play Policy).

**Trách nhiệm người dùng:**

- Tác giả dự án (hducthinh) **KHÔNG chịu bất kỳ trách nhiệm pháp lý nào** đối với các hành vi sử dụng sai mục đích, bao gồm việc tài khoản bị khóa (Account Banned), tước bỏ danh hiệu, hoặc các vấn đề liên đới phát sinh từ việc gian lận trực tuyến.
- Việc tải xuống và sử dụng mã nguồn đồng nghĩa với việc bạn **ĐÃ ĐỌC, HIỂU và ĐỒNG Ý** hoàn toàn với các điều khoản miễn trừ trách nhiệm này.

---

_Developed with ❤️ by hducthinh._
