# 👁️‍🗨️ StockEye - Real-time Chess Analysis Overlay

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)
![PyQt](https://img.shields.io/badge/PyQt-5%2F6-red.svg)
![Stockfish](https://img.shields.io/badge/Engine-Stockfish-orange.svg)

**StockEye** là một công cụ hỗ trợ phân tích cờ vua theo thời gian thực (Real-time). Dự án sử dụng công nghệ Thị giác máy tính (Computer Vision) để nhận diện trạng thái bàn cờ trực tiếp từ màn hình, sau đó giao tiếp với siêu máy tính Stockfish để hiển thị các nước đi tối ưu nhất (Top 3 Moves) qua một lớp giao diện đè (Overlay UI) trong suốt.

---

## 🌟 Tính năng nổi bật (Features)
- **Computer Vision Pipeline:** Nhận diện bàn cờ cực nhanh bằng `cv2.absdiff` (phát hiện chuyển động) và `cv2.matchTemplate` (nhận diện quân cờ).
- **Auto FEN Generation:** Tự động sinh chuỗi FEN chuẩn xác, bao gồm cả các luật phức tạp (Nhập thành, Phong cấp, Bắt tốt qua đường).
- **Invisible Overlay UI:** Lớp giao diện hiển thị bằng PyQt được thiết kế trong suốt (Transparent) và xuyên chuột (Click-through), không gây cản trở thao tác chơi game của người dùng.
- **Asynchronous Architecture:** Sử dụng mô hình Đa luồng (Multi-threading) tách biệt UI, Camera Capture và Stockfish Engine để chống giật lag máy tính.

---

## 🛠️ Cài đặt & Sử dụng (Installation & Usage)

### Yêu cầu hệ thống:
- Hệ điều hành: Windows 10/11.
- Màn hình độ phân giải 1920x1080 (khuyến nghị).
- Python 3.9 trở lên.

### Cài đặt:
1. Clone repository này về máy:
   ```bash
   git clone https://github.com/hducthinh/StockEye.git
   cd StockEye
   ```
2. Cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```
3. Tải [Stockfish Engine](https://stockfishchess.org/download/) bản nhị phân (.exe) và đặt vào thư mục `engine/`.

### Chạy ứng dụng:
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
