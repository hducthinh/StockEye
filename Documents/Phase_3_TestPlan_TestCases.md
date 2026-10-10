# KẾ HOẠCH KIỂM THỬ STOCKEYE V2

## 1. Functional tests

| Mã | Trường hợp | Kết quả |
|---|---|---|
| MOVE-01 | Nước thường | Đúng 2 ô và đúng legal move |
| MOVE-02 | Bắt quân | Đúng 2 ô và đúng legal move |
| MOVE-03 | En passant | Đúng 3 ô, xóa đúng tốt bị bắt |
| MOVE-04 | Nhập thành | Đúng 4 ô, cập nhật vua và xe |
| MOVE-05 | Promotion | Chọn đúng quân; fallback Hậu khi ảnh không đủ |
| MOVE-06 | Tập ô không hợp lệ/mơ hồ | Không commit, xóa overlay, yêu cầu Resync |
| MOVE-07 | Hơn 4 ô thay đổi | Xóa overlay và tự Resync ở frame kế tiếp |
| SYNC-01 | FEN hợp lệ | Commit atomically và tăng revision |
| SYNC-02 | Thiếu/thừa vua hoặc unknown square | Giữ nguyên board cũ |
| SYNC-03 | Nối được một legal move | Giữ castling/en-passant/lịch sử |
| SYNC-04 | Trắng/Đen nằm phía dưới | Tự chọn đúng orientation và lượt Resync |
| ENGINE-01 | Result revision cũ | Bị loại, không vẽ overlay |

## 2. Platform tests

- Windows 10/11, DPI 100/125/150/200%.
- Bàn cờ trên primary hoặc secondary monitor, kể cả monitor có tọa độ âm.
- Kiểm tra overlay không xuất hiện trong frame MSS.
- Đóng ứng dụng không để lại Stockfish.

## 3. Performance acceptance

- Theme xanh/quân Neo đã hiệu chuẩn, bàn khoảng 731×731.
- Normal tracking P95 dưới 100 ms từ frame mới đến dữ liệu overlay.
- Resync P95 dưới 500 ms.
- Main UI thread không gọi MSS, OpenCV hoặc Stockfish.

## 4. Lệnh kiểm thử

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
