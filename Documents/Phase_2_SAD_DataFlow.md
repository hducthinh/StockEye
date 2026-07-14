# TÀI LIỆU THIẾT KẾ KIẾN TRÚC & LUỒNG DỮ LIỆU (SAD & DATA FLOW)
**Dự án:** StockEye - Real-time Chess Analysis Overlay
**Phiên bản:** 1.0
**Ngày tạo:** 14/07/2026

---

## 1. KIẾN TRÚC TỔNG THỂ (HIGH-LEVEL ARCHITECTURE)
StockEye được thiết kế theo mô hình **Producer-Consumer** kết hợp **Event-driven Architecture** để đảm bảo ứng dụng xử lý ảnh và Stockfish Engine có thể chạy song song (Asynchronously) mà không làm đóng băng (Freeze) giao diện người dùng.

Hệ thống bao gồm 4 khối chính (Modules):
1. **Screen Capture Module (Producer 1):** Chịu trách nhiệm chụp ảnh màn hình vùng chọn ở tốc độ khung hình cao (FPS).
2. **Computer Vision Module (Consumer 1 / Producer 2):** Xử lý hình ảnh, nhận diện nước đi và sinh ra chuỗi FEN.
3. **Engine Interface Module (Consumer 2 / Producer 3):** Quản lý tiến trình (Subprocess) Stockfish, truyền FEN vào và bóc tách kết quả phân tích.
4. **Overlay UI Module (Consumer 3):** Lớp PyQt nhận dữ liệu từ Engine và vẽ đồ họa đè lên màn hình.

---

## 2. THIẾT KẾ ĐA LUỒNG (MULTI-THREADING DESIGN)
Bởi vì Stockfish khi hoạt động sẽ chiếm dụng rất nhiều tài nguyên CPU, tất cả các tác vụ I/O và tính toán phải được cô lập (isolated) trên các luồng riêng biệt.

- **Main Thread (UI Thread):** Chỉ chạy Event Loop của PyQt. Chịu trách nhiệm render độ trong suốt, vẽ mũi tên/highlight. Tuyệt đối không có vòng lặp tính toán nặng ở đây.
- **Thread 1 (Capture Thread):** Vòng lặp `while True` chụp màn hình và đẩy frame vào `Queue(maxsize=1)`.
- **Thread 2 (CV Thread):** Đọc frame từ Queue, chạy `cv2.absdiff` và `cv2.matchTemplate`. Khi trạng thái bàn cờ thay đổi, đẩy chuỗi FEN vào `Engine Queue`.
- **Thread 3 (Stockfish I/O Thread):** Giao tiếp với Stockfish Subprocess qua `stdin` và `stdout`. Đọc liên tục stdout để lấy kết quả thời gian thực (`info depth...`) và phát (emit) tín hiệu tới Main Thread qua PyQt Signals.

---

## 3. SƠ ĐỒ LUỒNG DỮ LIỆU (DATA FLOW DIAGRAM)

```text
+---------------------+       +------------------------+      +------------------------+
|   Capture Thread    | ----> |     Queue (Frames)     | ---> |       CV Thread        |
| (Grab Screen @30Hz) |       | (Lưu frame mới nhất)   |      | (Diff & Template Match)|
+---------------------+       +------------------------+      +-----------+------------+
                                                                          |
                                                                          v
+---------------------+       +------------------------+      +-----------+------------+
|      UI Thread      | <---- | PyQt Signals / Events  | <--- |   Stockfish I/O Thread |
| (Render PyQt Overlay|       | (Gửi Top 3 Moves)      |      | (Quản lý Subprocess)   |
+---------------------+       +------------------------+      +-----------+------------+
                                                                          |
                                                                          v
                                                              +-----------+------------+
                                                              |  Stockfish Executable  |
                                                              |   (100% CPU usage)     |
                                                              +------------------------+
```

---

## 4. QUẢN LÝ TÀI NGUYÊN VÀ THẮT CỔ CHAI (BOTTLENECK MANAGEMENT)
Để tránh tình trạng giật chuột (Mouse Lag) trên hệ thống Single-PC, cấu trúc sẽ áp dụng các biện pháp sau:
1. **Giới hạn luồng (Thread Limiting):** Truyền lệnh `setoption name Threads value <N>` cho Stockfish (với N = Số nhân CPU vật lý - 2, để dành tài nguyên cho OS và Mouse Event).
2. **Loại bỏ Frame cũ (Drop stale frames):** Queue chuyển ảnh từ Capture sang CV sẽ chỉ lưu 1 phần tử (LIFO hoặc Queue with maxsize=1 & Put without blocking). Nếu CV Thread xử lý chậm, các khung hình cũ sẽ bị bỏ qua, chỉ phân tích trên khung hình mới nhất.
3. **Cấu hình độ sâu (Depth Cap):** Giới hạn `go depth 18` hoặc `go movetime 1000` (1 giây) thay vì để Stockfish chạy vô hạn (infinite search).
