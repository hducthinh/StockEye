# StockEye

StockEye là công cụ theo dõi một bàn cờ 2D trên màn hình và phân tích trạng thái đó bằng Stockfish. Dự án dành cho phân tích và luyện tập cờ offline.

## Luồng hoạt động

```text
ROI bàn cờ → phát hiện 2–4 ô thay đổi → đối chiếu legal move
            → cập nhật chess.Board → Stockfish → overlay
```

Nhận diện đầy đủ 64 ô chạy khi khởi động, khi người dùng nhấn **Resync**, hoặc tự động khi phát hiện hơn 4 ô thay đổi. Nếu 2–4 ô thay đổi không khớp chính xác một nước hợp lệ, tracker dừng cập nhật và yêu cầu Resync thay vì đoán.

Hệ thống nhận diện:

- Nước thường và bắt quân: 2 ô.
- En passant: 3 ô.
- Nhập thành: 4 ô.
- Promotion: 2 ô, có nhận diện quân tại ô đích.

## Cài đặt

Yêu cầu Windows 10/11 và Python 3.9+.

```powershell
python -m pip install -r requirements.txt
```

Đặt Stockfish tại:

```text
engine/stockfish19.exe
```

## Hiệu chuẩn

Mở bàn cờ ở thế xuất phát, đúng theme xanh/quân Neo, tắt toàn bộ animation rồi chạy:

```powershell
python auto_setup.py
```

Setup sẽ tìm vùng có cấu trúc 8×8 trên toàn virtual desktop, cho phép xác nhận/chọn tay, lưu ROI và tạo templates.

## Chạy

```powershell
python main.py
```

Control panel có các chức năng:

- **Phím tắt nhanh (Toàn hệ thống / Global Hotkey):**
  - **Phím 3:** Kích hoạt **Resync** lại toàn bộ bàn cờ.
  - **Phím 4:** **Tạm dừng / Tiếp tục** quá trình tracking.
  - **Phím 5:** Chuyển ngay sang **Bàn cờ thông thường** (standard) và kích hoạt Resync.
  - **Phím 6:** Chuyển ngay sang **Puzzle Rush** (puzzle) và kích hoạt Resync.
  - **Phím 7:** **Ẩn/Hiện toàn bộ giao diện tool** (Control Panel và cửa sổ tiến trình) nhưng **vẫn giữ nguyên gợi ý nước đi** trên bàn cờ.
  *(Hoạt động trực tiếp ngay cả khi đang tập trung chơi trên trình duyệt)*
- **Resync:** tự nhận diện màu quân đang ở phía dưới, chọn hướng bàn và lượt tương ứng, rồi nhận diện lại toàn bộ bàn cờ.
- **Tạm dừng/Tiếp tục:** dừng hoặc bật tracking.
- Chọn hướng bàn và lượt dùng khi Resync không thể nối với lịch sử cũ.
- Điều chỉnh thời gian Stockfish và số gợi ý.

Khi phát hiện hơn 4 ô thay đổi, StockEye tự Resync trên frame kế tiếp. Nếu full-board recognition thất bại, overlay được xóa và control panel yêu cầu người dùng Resync thủ công.

## Kiểm thử

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Giới hạn

- Chỉ hỗ trợ profile theme đã hiệu chuẩn.
- Bàn cờ phải hiển thị đầy đủ và không bị cửa sổ khác che.
- Overlay cần được Windows cho phép loại khỏi screen capture; nếu không, tracking sẽ không khởi động.
- Dự án không có autoplay, auto-click, bàn cờ phụ, stealth hoặc ngụy trang tiến trình.
