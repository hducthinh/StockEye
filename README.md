# 👁️‍🗨️ StockEye - The Ultimate Real-time Chess Assistant & Autobot

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)
![PyQt](https://img.shields.io/badge/PyQt-5%2F6-red.svg)
![Stockfish](https://img.shields.io/badge/Engine-Stockfish-orange.svg)
![Tesseract OCR](https://img.shields.io/badge/Tesseract-OCR-blueviolet.svg)

**StockEye** là công cụ hỗ trợ phân tích và tự động hóa cờ vua theo thời gian thực (Real-time) mạnh mẽ nhất. Bằng sự kết hợp giữa **Thị giác máy tính (Computer Vision)**, **Nhận dạng ký tự (OCR)** và siêu máy tính **Stockfish**, công cụ không chỉ phân tích trận đấu mà còn có khả năng tự động chơi (Autoplay) với các hành vi mô phỏng người thật tinh vi nhất.

---

## 🌟 Các tính năng đột phá (Killer Features)

- **Auto-Tracker & Auto-Sync:** Tự động phát hiện chuyển động của quân cờ thông qua `cv2.absdiff` siêu nhẹ, không tốn tài nguyên. Khả năng tự động đồng bộ lại thế cờ (Mid-game Sync) và **nhận diện khi bắt đầu ván mới (New Game)** cực kỳ mượt mà.
- **Smart Autoplay (Bot tự đánh):** Thay vì can thiệp vào web, StockEye điều khiển chuột vật lý. Sử dụng thuật toán tiệm cận Fitts' Law để mô phỏng độ cong của đường chuột, thời gian chần chừ (hesitation), giúp những nước đi trông hoàn toàn giống con người.
- **Time Management (OCR Đồng hồ):** Đọc đồng hồ đếm ngược của bạn theo thời gian thực bằng Tesseract OCR. Khi thời gian cạn kiệt, Bot tự động chuyển sang trạng thái **Time Scramble** (Đánh siêu tốc, bỏ qua các bước mô phỏng người thật để chiến thắng thời gian).
- **Predictive Premove:** Stockfish dự đoán nước đi bắt buộc của đối thủ, Bot sẽ tự động cầm sẵn quân cờ (hover) ở ô xuất phát và thả tay ngay lập tức (0.001s) khi đối thủ vừa đi đúng nước dự đoán.
- **Auto-Farm Mode (Cày rank tự động):** Khả năng tự động tìm nút "New Game" hoặc "Rematch" trên màn hình. Cho phép treo máy chơi liên tục 24/7 không cần bất kỳ sự can thiệp nào của con người.
- **Control Panel Trực quan:** Giao diện điều khiển cho phép tùy chỉnh nóng mọi thông số như: Bot Delay, Số luồng CPU (Threads), Độ cong chuột (Mouse Curvature), Thời gian Scramble...
- **Invisible Overlay UI:** Lớp giao diện hiển thị bằng PyQt được thiết kế hoàn toàn trong suốt (Transparent), chống chụp màn hình (WDA_EXCLUDEFROMCAPTURE) để qua mặt các công cụ Anti-Cheat, đồng thời click-through (xuyên chuột) không làm phiền người chơi.

---

## ⌨️ Hệ thống Phím tắt (Global Hotkeys)
Các phím tắt hoạt động toàn cầu trên máy tính của bạn:

- `1` : **Bật / Tắt Tool** (Tạm dừng mọi hoạt động của bot/nhận diện).
- `2` : **Bật / Tắt Gợi ý** (Bật/tắt mũi tên phân tích nước đi trên màn hình).
- `3` : **Bật / Tắt Autoplay** (Cho phép bot tự điều khiển chuột để chơi).
- `4` : **Bật / Tắt Autofarm** (Chế độ tự động tìm ván mới khi ván cũ kết thúc).
- `5` : **Ép phe Trắng** (Bắt tool hiểu rằng bạn đang cầm quân Trắng).
- `6` : **Ép phe Đen** (Bắt tool hiểu rằng bạn đang cầm quân Đen).
- `ESC` : **Kill-switch** (Hủy ngay lập tức mọi hàng đợi click chuột, dùng khi bot bị lỗi hoặc mất kiểm soát).
- `F4` : **Thoát hoàn toàn ứng dụng**.

---

## 🛠️ Cài đặt & Sử dụng (Installation & Usage)

### 1. Yêu cầu hệ thống:
- Hệ điều hành: Windows 10/11.
- Tesseract OCR (Bắt buộc cho tính năng đọc đồng hồ). Cài đặt tại `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- Màn hình độ phân giải 1920x1080 (khuyến nghị).
- Python 3.9 trở lên.

### 2. Cài đặt môi trường:
```bash
git clone https://github.com/hducthinh/StockEye.git
cd StockEye
pip install -r requirements.txt
```
> **Lưu ý:** Tải [Stockfish Engine](https://stockfishchess.org/download/) bản nhị phân (.exe) và đặt vào thư mục `engine/` (VD: `engine/stockfish-windows-x86-64-avx2.exe`).

### 3. Huấn luyện hệ thống (Chỉ 1 lần duy nhất):
Do mỗi bàn cờ trên trình duyệt có kích thước khác nhau, bạn cần setup hình dạng quân cờ:

1. Mở một bàn cờ **THẾ XUẤT PHÁT** (Mới tinh, 32 quân nằm đúng vị trí chuẩn) trên trình duyệt.
2. Chạy file cấu hình tự động: `python auto_get_templates.py`
3. Kéo chuột vẽ vùng bàn cờ. Nhấn `Enter` hoặc `Space` để chốt tọa độ.
4. Tọa độ bàn cờ và 32 bức ảnh mẫu (templates) sẽ được trích xuất hoàn hảo và lưu lại để sử dụng cho các lần sau.

### 4. Chạy ứng dụng:
```bash
python main.py
```

---

## ⚖️ TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM PHÁP LÝ (LEGAL DISCLAIMER)

**Dự án StockEye được phát triển ĐỘC QUYỀN cho các mục đích:**
1. Nghiên cứu khoa học máy tính, đặc biệt là xử lý ảnh (Computer Vision), nhận dạng OCR và tương tác mô phỏng vật lý chuột.
2. Phân tích cờ vua ngoại tuyến (Offline Analysis) chống lại các Engine khác hoặc tự luyện tập để nâng cao trình độ.

**NGHIÊM CẤM:**
- Việc sử dụng công cụ này (đặc biệt là tính năng Autoplay / Autofarm) trên các nền tảng cờ vua trực tuyến (như Chess.com, Lichess.org) trong các ván đấu có tính điểm xếp hạng (Ranked games). Hành vi này vi phạm nghiêm trọng Điều khoản Dịch vụ (Terms of Service) và Chính sách Công bằng (Fair Play Policy).

**Trách nhiệm người dùng:**
- Tác giả dự án (hducthinh) **KHÔNG chịu bất kỳ trách nhiệm pháp lý nào** đối với các hành vi sử dụng sai mục đích, bao gồm việc tài khoản bị khóa (Account Banned), tước bỏ danh hiệu, hoặc các vấn đề liên đới phát sinh từ việc gian lận trực tuyến.
- Việc tải xuống và sử dụng mã nguồn đồng nghĩa với việc bạn ĐÃ ĐỌC, HIỂU và ĐỒNG Ý hoàn toàn với các điều khoản miễn trừ trách nhiệm này.

---
*Developed with ❤️ by hducthinh.*
