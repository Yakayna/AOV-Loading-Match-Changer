# AOV Loading Match Changer

Tool đổi ảnh loading match/player image cho AOV/KGVN, có menu combo, auto batch, nén ảnh và sanitize ảnh.

## Tính năng chính

- Chạy `loadtran.py` với HAR capture từ game.
- Hỗ trợ JPG, JPEG, PNG, WEBP, GIF, MP4.
- Auto resize media về kích thước poster `1080x1701`.
- Sign bridge bằng Node.js qua `sign_bridge.js`.
- Menu combo: cập nhật HAR, nén ảnh, chạy LoadTran.
- Nén đa ảnh ra thư mục riêng, chưa thay ảnh gốc.
- Các chế độ auto ảnh:
  - `Brutal Mode`
  - `Lọc ảnh`
  - `Sanitize + load ảnh`
  - `Sanitize + nén ảnh + load`
- Brutal preset mặc định: `70,60,50,40,45,40,36,35,32,30` KB.
- Sanitize có 2 kiểu: `gạch trắng mờ` và `gạch trắng rõ`.
- File pass được copy vào `anh_OK/`; ảnh gốc trong `anh_goc/` được giữ nguyên.

## Cài đặt

Yêu cầu:

- Python 3.10+
- Node.js
- pip packages trong `requirements.txt`

```bat
pip install -r requirements.txt
node --version
```

## Chuẩn bị HAR

Tool cần file `.har` có request player-poster của tài khoản.

1. Capture traffic khi mở/chỉnh poster load trận trong game.
2. Export file `.har`.
3. Đặt file `.har` vào cùng thư mục tool.

Nếu có link `player-poster?...itopencodeparam=...`, có thể cập nhật/tạo HAR bằng menu combo.

## Cách chạy nhanh

Chạy:

```bat
run_combo.bat
```

Hoặc:

```bat
python loadtran_combo.py
```

Flow menu:

1. Chọn `Thay ảnh load` hoặc `Nén đa ảnh`.
2. Nếu chọn `Nén đa ảnh`: chọn ảnh, nhập KB, chọn thư mục xuất.
3. Nếu chọn `Thay ảnh load`: chọn có update HAR hay không.
4. Chọn chế độ auto ảnh:
   - `0`: chạy thường
   - `1`: Brutal Mode
   - `2`: Lọc ảnh
   - `3`: Sanitize + load ảnh
   - `4`: Sanitize + nén ảnh + load
5. Làm theo câu hỏi trên màn hình.

## File chính

- `run_combo.bat`: chạy menu combo.
- `chay_auto.bat`: chạy Brutal Mode nhanh.
- `loadtran_combo.py`: menu tổng hợp.
- `brutal_mode.py`: các chế độ auto ảnh.
- `auto_full_200.py`: wrapper tương thích cho `chay_auto.bat`.
- `loadtran.py`: flow chính upload/save poster.
- `compress_for_loadtran.py`: nén/crop ảnh về `1080x1701`.
- `update_synthetic_har.py`: cập nhật/tạo HAR từ link player-poster.
- `sign_bridge.js` + `camp-security-oversea.0.1.0.js`: sign bridge.

## Lưu ý

- Không commit/push file `.har`, ảnh cá nhân, token, cache hoặc thư mục tạm.
- Nếu gặp lỗi auth/token, capture hoặc cập nhật HAR mới.
- Nếu sign bridge lỗi, kiểm tra Node.js và đảm bảo `sign_bridge.js`, `camp-security-oversea.0.1.0.js` nằm cùng thư mục.
- Trên Windows, nên chạy bằng `run_combo.bat` hoặc `chay_auto.bat` để dùng UTF-8.
