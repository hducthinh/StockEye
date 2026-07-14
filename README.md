# 👁️‍🗨️ StockEye - Real-time Chess Analysis Overlay

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)
![PyQt](https://img.shields.io/badge/PyQt-5%2F6-red.svg)
![Stockfish](https://img.shields.io/badge/Engine-Stockfish-orange.svg)

**StockEye** là một công cụ hỗ trợ phân tích cờ vua theo thời gian thực (Real-time). Dự án sử dụng công nghệ Thị giác máy tính (Computer Vision) để nhận diện trạng thái bàn cờ trực tiếp từ màn hình, sau đó giao tiếp với siêu máy tính Stockfish để hiển thị các nước đi tối ưu nhất (Top 3 Moves) qua một lớp giao diện đè (Overlay UI) trong suốt.

---

## 🌟 Tính năng nổi bật (Features)
- **Vòng lặp tự động (Auto-Tracker):** Tự động phát hiện chuyển động của quân cờ thông qua `cv2.absdiff` mà không cần tốn tài nguyên nhận diện toàn bộ bàn cờ liên tục. Chạy ngầm mượt mà và tự động đẩy nước đi cho Stockfish.
- **Mắt Thần (Mid-game Sync):** Trang bị tính năng "Hồi sinh" (Hotkeys: `1`, `2`) bằng cách quét và phân tích chính xác vị trí của 32 quân cờ, tự động sinh chuỗi FEN chuẩn xác để sửa lỗi bàn cờ khi Auto-Tracker bị lỡ nhịp.
- **Auto Perspective:** Nhận diện bàn cờ được xoay cho góc nhìn phe Trắng hay phe Đen dựa trên mật độ pixel tự động, giúp vẽ UI một cách chính xác tuyệt đối.
- **Invisible Overlay UI:** Lớp giao diện hiển thị bằng PyQt được thiết kế trong suốt (Transparent), chống chụp màn hình (WDA_EXCLUDEFROMCAPTURE) và xuyên chuột (Click-through), không gây cản trở thao tác chơi game của người dùng.
- **Asynchronous Architecture:** Sử dụng mô hình Đa luồng (Multi-threading) tách biệt UI, Camera Capture và Stockfish Engine để chống giật lag máy tính.

---

## ⌨️ Phím tắt (Hotkeys)
Khi ứng dụng đang chạy (`main.py`), bạn có thể điều khiển trực tiếp trên bàn phím:
- `F2`: Bắt đầu ván mới (Xóa sạch lịch sử, chờ quân di chuyển để nhận diện phe).
- `1`: Bật Mắt Thần - Quét toàn bộ ảnh màn hình hiện tại, tìm nước đi tốt nhất cho **Trắng**.
- `2`: Bật Mắt Thần - Quét toàn bộ ảnh màn hình hiện tại, tìm nước đi tốt nhất cho **Đen**.

---

## 🛠️ Cài đặt & Sử dụng (Installation & Usage)

### 1. Yêu cầu hệ thống:
- Hệ điều hành: Windows 10/11.
- Màn hình độ phân giải 1920x1080 (khuyến nghị).
- Python 3.9 trở lên.

### 2. Cài đặt môi trường:
```bash
git clone https://github.com/hducthinh/StockEye.git
cd StockEye
pip install -r requirements.txt
```
Tải [Stockfish Engine](https://stockfishchess.org/download/) bản nhị phân (.exe) và đặt vào thư mục `engine/` (VD: `engine/stockfish-windows-x86-64-avx2.exe`).

### 3. Huấn luyện hệ thống:
Trước khi chơi, bạn cần cho Tool biết vị trí bàn cờ và hình dạng quân cờ của bạn (do mỗi web/giao diện có kích thước khác nhau). Bạn chỉ cần làm việc này 1 lần duy nhất:

1. Mở một bàn cờ **THẾ XUẤT PHÁT** (Mới tinh, 32 quân nằm đúng vị trí chuẩn) trên trình duyệt.
2. Chạy lệnh: `python auto_get_templates.py`
3. Tool sẽ hiển thị cửa sổ ảnh để bạn **kéo chuột vẽ vùng bàn cờ**. Nhấn `Enter` hoặc `Space` để chốt tọa độ.
4. Tọa độ bàn cờ sẽ được tự động lưu vào `config.json`, đồng thời Tool sẽ tự động trích xuất luôn 32 bức ảnh mẫu hoàn hảo vào thư mục `templates/`.

### 4. Chạy ứng dụng:
```bash
python main.py
```

---

## ⚖️ TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM PHÁP LÝ (LEGAL DISCLAIMER)

**Dự án StockEye được phát triển ĐỘC QUYỀN cho các mục đích:**
1. Nghiên cứu khoa học máy tính, đặc biệt là xử lý ảnh (Computer Vision) và tương tác luồng dữ liệu (Inter-process Communication).
2. Phân tích cờ vua ngoại tuyến (Offline Analysis) chống lại các Engine khác hoặc tự luyện tập.

**NGHIÊM CẤM:**
- Việc sử dụng công cụ này trên các nền tảng cờ vua trực tuyến (như Chess.com, Lichess.org, v.v.) trong các ván đấu có tính điểm xếp hạng (Ranked/Rated games) hoặc các giải đấu. Hành vi này vi phạm nghiêm trọng Điều khoản Dịch vụ (Terms of Service) cũng như Chính sách Công bằng (Fair Play Policy) của các nền tảng kể trên.

**Trách nhiệm người dùng:**
- Tác giả dự án (hducthinh) KHÔNG chịu bất kỳ trách nhiệm pháp lý nào đối với các hành vi sử dụng sai mục đích, bao gồm nhưng không giới hạn: việc tài khoản bị khóa (Account Banned), tước bỏ danh hiệu, hoặc các vấn đề liên đới phát sinh từ việc gian lận trực tuyến.
- Việc tải xuống và sử dụng mã nguồn đồng nghĩa với việc bạn ĐÃ ĐỌC, HIỂU và ĐỒNG Ý hoàn toàn với các điều khoản miễn trừ trách nhiệm này.

---
*Developed with ❤️ by hducthinh.*
