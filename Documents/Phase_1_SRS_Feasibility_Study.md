# TÀI LIỆU KHẢO SÁT & ĐẶC TẢ YÊU CẦU (SRS) VÀ NGHIÊN CỨU TÍNH KHẢ THI
**Dự án:** StockEye - Real-time Chess Analysis Overlay
**Phiên bản:** 1.0
**Ngày tạo:** 14/07/2026

---

## 1. TỔNG QUAN DỰ ÁN (PROJECT OVERVIEW)

### 1.1. Mục đích (Purpose)
Tài liệu này định nghĩa các yêu cầu chức năng, phi chức năng và phân tích tính khả thi cho dự án **StockEye**. Hệ thống được thiết kế để hỗ trợ người chơi cờ vua trên nền tảng Web (ví dụ: Chess.com, Lichess) bằng cách cung cấp các gợi ý nước đi tối ưu theo thời gian thực thông qua công nghệ Thị giác Máy tính (Computer Vision) và Stockfish Engine.

### 1.2. Phạm vi (Scope)
StockEye hoạt động như một ứng dụng phân tích cờ offline độc lập trên máy tính. Hệ thống sẽ:
- Liên tục chụp và phân tích màn hình để nhận diện trạng thái bàn cờ.
- Chuyển đổi trạng thái hình ảnh sang chuỗi định dạng FEN (Forsyth-Edwards Notation).
- Giao tiếp với Stockfish Engine để tính toán Top 3 nước đi tốt nhất (MultiPV=3).
- Hiển thị kết quả lên một lớp giao diện đè (Overlay UI) trong suốt, không viền và cho phép thao tác chuột xuyên qua (Click-through) trực tiếp lên bàn cờ gốc.

---

## 2. NGHIÊN CỨU TÍNH KHẢ THI (FEASIBILITY STUDY)

### 2.1. Tính khả thi về Kỹ thuật (Technical Feasibility)
- **Computer Vision:** Sử dụng **OpenCV** với kỹ thuật *Frame Difference* để phát hiện sự thay đổi trạng thái (nước đi mới) và *Template Matching* để nhận diện quân cờ. Đây là cách tiếp cận tối ưu về hiệu năng tính toán so với Deep Learning (YOLO), phù hợp để chạy đồng thời cùng Stockfish.
- **Overlay UI:** Sử dụng **PyQt (PyQt5/PyQt6)**. PyQt cung cấp các API cấp thấp tương tác tốt với Window Manager của hệ điều hành, cho phép tạo ra các cửa sổ có thuộc tính `FramelessWindowHint`, `WindowStaysOnTopHint` và `TransparentForMouseEvents`, đáp ứng hoàn hảo yêu cầu UI.
- **Chess Engine:** Sử dụng **Stockfish** (nhị phân) kết nối qua giao thức chuẩn UCI (Universal Chess Interface).

### 2.2. Tính khả thi về Vận hành & Môi trường (Operational Feasibility)
- **Môi trường triển khai:** Hệ thống chạy kiểu "All-in-one" trên cùng một máy tính. Việc đóng gói sẽ được thực hiện qua PyInstaller hoặc Auto-py-to-exe thành một tệp thực thi duy nhất (Standalone Executable).
- **Phạm vi sử dụng:** Công cụ chỉ phục vụ phân tích/luyện tập offline; không có autoplay, auto-click, stealth hoặc ngụy trang tiến trình.
- **Rủi ro Hiệu năng:** Stockfish ở độ sâu (depth) lớn sẽ chiếm tối đa tài nguyên CPU. Điều này có thể gây hiện tượng "nghẽn cổ chai" (Bottleneck), làm giật lag thao tác chuột. Giải pháp khắc phục là giới hạn luồng (Threads) cấp cho Stockfish hoặc giới hạn thời gian suy nghĩ (Time/Depth limit) trong cấu hình.

---

## 3. ĐẶC TẢ YÊU CẦU HỆ THỐNG (SYSTEM REQUIREMENTS SPECIFICATION)

### 3.1. Yêu cầu Chức năng (Functional Requirements)

| Mã YC | Tên chức năng | Mô tả chi tiết |
|---|---|---|
| **FR01** | Bắt khung hình (Screen Capture) | Hệ thống phải có khả năng khoanh vùng bàn cờ trên màn hình và liên tục chụp ảnh vùng này với tốc độ tối thiểu 10 FPS. |
| **FR02** | Nhận diện nước đi (Move Detection) | Sử dụng *Frame Difference* để so sánh 2 khung hình liên tiếp, phát hiện vùng pixel thay đổi để xác định khi nào có lượt đi mới, tránh việc phân tích lại toàn bộ bàn cờ liên tục. |
| **FR03** | Nhận diện quân cờ (Piece Recognition) | Template matching toàn bộ 64 ô chỉ chạy khi khởi động hoặc khi người dùng nhấn Resync. Theo dõi thường xuyên chỉ dùng tập 2–4 ô thay đổi và luật cờ. |
| **FR04** | Sinh mã FEN (FEN Generation) | Board state được cập nhật bằng legal move; candidate FEN từ Resync phải được kiểm tra hợp lệ trước khi commit. |
| **FR05** | Giao tiếp UCI (UCI Integration) | Một engine worker duy nhất gửi FEN sang Stockfish, lấy MultiPV theo time budget và loại kết quả có revision cũ. |
| **FR06** | Hiển thị Overlay UI | Dựng lớp giao diện đè hiển thị Top 3 nước đi (mũi tên hoặc highlight ô vuông). Giao diện này phải cập nhật theo thời gian thực (Real-time). |

### 3.2. Yêu cầu Phi chức năng (Non-Functional Requirements)

- **NFR01 - Usability (Tính khả dụng):** Overlay UI phải tuyệt đối **trong suốt** và **xuyên chuột** (Click-through) 100%. Người dùng không được phép vô tình click nhầm vào Overlay làm mất Focus của trình duyệt web.
- **NFR02 - Performance (Hiệu năng):** 
  - Pipeline từ frame bàn cờ mới đến dữ liệu overlay có P95 dưới 100ms; Resync có P95 dưới 500ms.
  - Cho phép người dùng giới hạn tài nguyên CPU (số luồng) của Stockfish qua file cấu hình `config.json`.
- **NFR03 - Maintainability (Tính bảo trì):** Kiến trúc mã nguồn phải áp dụng mô hình Producer-Consumer (ví dụ: luồng chụp ảnh, luồng xử lý CV, và luồng UI chạy riêng biệt để tránh block Main Thread của UI).

---

## 4. KIẾN TRÚC LUỒNG DỮ LIỆU SƠ BỘ (PRELIMINARY DATA FLOW)

```text
[Màn hình Web] --> (Screen Capture) --> Khung hình (Images)
                                            |
                                            v
[OpenCV Module] <-- (Frame Diff & Template Matching)
      |
      +-- Sinh chuỗi --> (FEN String)
                              |
                              v
                      [Stockfish Engine] (UCI Protocol)
                              |
                              +-- Đánh giá --> (Top 3 Moves - UCI format)
                                                    |
                                                    v
[PyQt UI Overlay] <----- (Render Arrows/Highlights) +
```
