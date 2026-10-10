# KIẾN TRÚC VÀ LUỒNG DỮ LIỆU STOCKEYE V2

## 1. Nguyên tắc

- Chỉ một worker được phép chụp màn hình.
- Full-board recognition chạy lúc khởi động, Resync thủ công hoặc khi phát hiện hơn 4 ô thay đổi.
- State chỉ thay đổi sau khi candidate đã được xác thực.
- Mỗi state có revision; kết quả Stockfish cũ không được vẽ.
- Qt main thread chỉ xử lý control panel và overlay.

## 2. Các thành phần

1. **CaptureWorker:** chụp ROI ở 60 FPS và ghi vào queue kích thước 1.
2. **BoardTrackingWorker:** so sánh frame với ảnh mốc, tìm 2–4 ô thay đổi và đối chiếu legal move.
3. **EngineWorker:** worker duy nhất sở hữu Stockfish, chỉ xử lý request mới nhất.
4. **AppCoordinator/UI:** kiểm tra revision, đổi UCI square thành pixel và vẽ overlay.

## 3. Luồng thường xuyên

```text
MSS capture
  → latest-frame queue
  → per-square diff
  → exact legal-move match
  → BoardState.push + revision++
  → latest-analysis queue
  → Stockfish MultiPV
  → revision check
  → Overlay
```

Tập ô kỳ vọng được tạo bằng cách so sánh piece map trước/sau mỗi legal move. Nước thường/capture có 2 ô, en passant 3 ô và castling 4 ô. Tập 2–4 ô không khớp duy nhất sẽ chuyển tracker sang trạng thái cần Resync; hơn 4 ô sẽ tự lên lịch full-board Resync ở frame kế tiếp.

## 4. Luồng Resync

```text
Nút Resync → frame mới nhất → classify 64 ô → nhận diện màu ở phía dưới
           → cập nhật orientation + lượt Resync → candidate FEN
           → validate → commit atomically → revision++ → Stockfish
```

Nếu piece placement nối được với state cũ bằng đúng một legal move, nước đó được replay để giữ metadata. Nếu không, dùng lượt do người dùng chọn và bỏ castling/en-passant. Candidate lỗi không được thay state hiện tại.

## 5. Đồng thời và đóng ứng dụng

- Queue capture và engine đều có kích thước 1; dữ liệu cũ bị thay bằng dữ liệu mới.
- Stockfish không được gọi từ UI hoặc tracker thread.
- Khi đóng ứng dụng: dừng capture, tracker, engine; join thread; đóng đúng PID Stockfish.
