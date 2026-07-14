# TÀI LIỆU KIỂM THỬ VÀ ĐẢM BẢO CHẤT LƯỢNG (TEST PLAN & TEST CASES)
**Dự án:** StockEye - Real-time Chess Analysis Overlay
**Phiên bản:** 1.0
**Ngày tạo:** 14/07/2026

---

## 1. MỤC ĐÍCH VÀ PHẠM VI KIỂM THỬ (TEST OBJECTIVES & SCOPE)
Tài liệu này xác định các chiến lược và kịch bản kiểm thử (Test Cases) nhằm đảm bảo hệ thống StockEye hoạt động ổn định, chính xác về thuật toán (Computer Vision, FEN), không ảnh hưởng đến trải nghiệm chơi game (UI/UX) và tối ưu được hiệu năng trên môi trường máy tính cá nhân.

**Phạm vi kiểm thử bao gồm:**
- Module xử lý thị giác máy tính (CV).
- Chức năng sinh chuỗi FEN và giao tiếp Stockfish.
- Trải nghiệm giao diện đè (Overlay UI).
- Các trường hợp ngoại lệ (Edge Cases) thực tế trong ván cờ.

---

## 2. KỊCH BẢN KIỂM THỬ CHI TIẾT (TEST CASES)

### 2.1. Kiểm thử Tính năng (Functional Testing)

| Mã TC | Tên Kịch bản (Test Scenario) | Các bước thực hiện (Steps) | Kết quả mong đợi (Expected Result) | Trạng thái |
|---|---|---|---|---|
| **TC_F01** | Bắt đầu ván mới (Initial Board) | 1. Mở bàn cờ Web trạng thái khởi tạo.<br>2. Bật StockEye. | StockEye nhận diện đúng FEN chuẩn: `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -`. UI hiển thị gợi ý mở màn hợp lệ (ví dụ: e4, d4). | [ ] |
| **TC_F02** | Cập nhật nước đi thường | 1. Đối thủ đi một nước cờ.<br>2. Chờ StockEye phân tích. | OpenCV nhận diện chính xác sự thay đổi, sinh đúng FEN mới. Stockfish update Top 3 moves trong thời gian < 1000ms. | [ ] |
| **TC_F03** | Nhập thành (Castling) | 1. Thực hiện nước nhập thành (O-O hoặc O-O-O). | StockEye hiểu đây là 1 nước đi đơn lẻ, cập nhật lại trạng thái FEN, vô hiệu hóa quyền nhập thành. | [ ] |
| **TC_F04** | Phong cấp (Promotion) | 1. Đưa Tốt xuống hàng cuối và phong Hậu. | Hệ thống bắt được hình ảnh Hậu mới xuất hiện, cập nhật FEN thay vì báo lỗi mất quân Tốt. | [ ] |
| **TC_F05** | Bắt tốt qua đường (En Passant) | 1. Thực hiện nước En Passant. | Cập nhật đúng cấu trúc bàn cờ khi quân Tốt đối phương biến mất. | [ ] |

### 2.2. Kiểm thử Giao diện (UI/UX & Usability Testing)

| Mã TC | Tên Kịch bản (Test Scenario) | Các bước thực hiện (Steps) | Kết quả mong đợi (Expected Result) | Trạng thái |
|---|---|---|---|---|
| **TC_U01** | Click-through (Xuyên chuột) | 1. Bật StockEye với Overlay.<br>2. Nhấp chuột, kéo thả quân cờ xuyên qua hình mũi tên do StockEye vẽ. | Thao tác chuột tương tác trực tiếp với trình duyệt Web, StockEye không cản trở thao tác vật lý nào. | [ ] |
| **TC_U02** | Độ trong suốt (Transparency) | 1. Bật Overlay. | Nền của Overlay trong suốt 100%, chỉ hiện các đường vẽ/mũi tên, không che khuất màu sắc bàn cờ gốc. | [ ] |
| **TC_U03** | Thay đổi kích thước (Resize) | 1. Phóng to/thu nhỏ trình duyệt. | Overlay tự động scale tỷ lệ hoặc có nút bấm để người dùng hiệu chỉnh (Recalibrate) lại góc nhìn. | [ ] |

### 2.3. Kiểm thử Ngoại lệ & Biên (Edge Cases)

| Mã TC | Tên Kịch bản (Test Scenario) | Các bước thực hiện (Steps) | Kết quả mong đợi (Expected Result) | Trạng thái |
|---|---|---|---|---|
| **TC_E01** | Quân cờ bị Highlight che lấp | 1. Web (Chess.com) highlight ô cờ màu vàng cho nước vừa đi làm nhiễu ảnh.<br>2. Chờ StockEye nhận diện. | Thuật toán Template Matching có Threshold phù hợp để bỏ qua nhiễu màu, vẫn nhận diện đúng quân cờ. | [ ] |
| **TC_E02** | Cửa sổ bị che khuất | 1. Mở một cửa sổ khác (ví dụ Notepad) đè lên một nửa bàn cờ. | StockEye tạm ngưng cập nhật hoặc báo lỗi "Không tìm thấy bàn cờ", không sinh FEN rác làm crash Stockfish. | [ ] |
| **TC_E03** | Giới hạn CPU (CPU Limit) | 1. Thiết lập Thread Limit = 2.<br>2. Bật Stockfish depth 20. | Chuột và máy tính không bị đóng băng. UI của PyQt vẫn phản hồi bình thường. | [ ] |

---

## 3. MÔI TRƯỜNG KIỂM THỬ (TEST ENVIRONMENT)
- **Hệ điều hành:** Windows 10/11 (Do sử dụng API cấp thấp của OS cho Overlay UI).
- **Độ phân giải:** 1920x1080 (Chuẩn hóa để test Template Matching).
- **Nền tảng mục tiêu:** Trình duyệt Chrome/Edge (Truy cập Chess.com ở chế độ màu bảng chuẩn).
- **Phần cứng:** CPU tối thiểu 4 Core (Khuyến nghị 6+ Core để cấp tối thiểu 2 Core cho Stockfish).
