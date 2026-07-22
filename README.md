# AOV Loading Match Changer

Tool đổi ảnh loading match/player image cho AOV/KGVN, có menu combo, auto batch và **Brutal Mode**.

## Tính năng chính

- Chạy `loadtran.py` với HAR capture từ game.
- Hỗ trợ JPG, JPEG, PNG, WEBP, GIF, MP4.
- Auto resize media về kích thước poster `1080x1701`.
- Sign bridge bằng Node.js qua `sign_bridge.js`.
- Menu combo: cập nhật HAR, nén ảnh, chạy LoadTran.
- Menu đầu vào hỏi rõ:
  - `Thay ảnh load`
  - hoặc `Nén đa ảnh` để nén hàng loạt ra thư mục riêng, chưa thay ảnh gốc.
- Brutal Mode:
  - Test ảnh gốc trước.
  - Nếu có nhiều hơn 1 file HAR: hiện menu chọn `1 HAR` hoặc `toàn bộ HAR`.
  - Nếu có nhiều hơn 1 ảnh: hiện menu chọn `1 ảnh` hoặc `toàn bộ ảnh`.
  - Nếu ảnh gốc fail mới tạo bản nén để thử tiếp.
  - Batch tối đa `5 ảnh`.
  - Nghỉ `6 giây` giữa các batch để giữ nhịp như source auto.
  - Preset nén mặc định: `70,60,50,40,45,40,36,35,32,30` KB.
  - Ảnh đã pass ở mốc nào thì dừng ở mốc đó, không nén tiếp các mốc thấp hơn.
  - Luôn xóa ảnh/candidate fail, trừ ảnh nằm trong thư mục `anh_goc/`.
  - Ảnh chạy được được copy vào `anh_OK/`.
  - Tổng kết hiển thị rõ OK, FAIL cuối, fail giữ trong `anh_goc/`, fail đã xóa ngoài `anh_goc/`, candidate fail đã xóa.
- Lọc ảnh:
  - Chọn ở khu vực Brutal/auto ảnh.
  - Chạy thẳng ảnh gốc, không nén.
  - Vẫn chạy batch 5 ảnh và nghỉ 6 giây giữa batch.
  - Dùng để lọc nhanh ảnh nào pass trực tiếp.

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

Cách dùng nhanh:

1. Capture traffic khi mở/chỉnh poster load trận trong game.
2. Export file `.har`.
3. Đặt file `.har` vào cùng thư mục tool.

Nếu có link `player-poster?...itopencodeparam=...`, có thể cập nhật/tạo HAR:

```bat
python update_synthetic_har.py --text "PASTE_LINK_PLAYER_POSTER"
```

Hoặc chạy menu combo rồi chọn update HAR.

## Cách chạy nhanh

### Menu combo

```bat
run_combo.bat
```

Hoặc:

```bat
python loadtran_combo.py
```

Flow menu:

1. Chọn `Thay ảnh load` hoặc `Nén đa ảnh`.
2. Nếu chọn `Nén đa ảnh`: chọn ảnh, nhập KB, chọn thư mục xuất; ảnh gốc giữ nguyên.
3. Nếu chọn `Thay ảnh load`: chọn có update HAR hay không.
4. Chọn chế độ auto ảnh:
   - `0`: chạy thường
   - `1`: Brutal Mode
   - `2`: Lọc ảnh
5. Nếu chọn Brutal Mode: chọn preset mặc định hoặc tự nhập list KB, ví dụ `20,30,40`.
6. Nếu chạy thường: chọn HAR, chọn media và chế độ nén/chạy thường.

### Brutal Mode trực tiếp

Đặt ảnh vào `anh_goc/`, sau đó chạy:

```bat
chay_auto.bat
```

Hoặc:

```bat
python brutal_mode.py --har synthetic_player_poster.har
```

Tùy chọn preset thủ công:

```bat
python brutal_mode.py --har synthetic_player_poster.har --targets 70,60,50,40,45,40,36,35,32,30
```

Dùng toàn bộ HAR, không hỏi menu chọn HAR:

```bat
python brutal_mode.py --all-har
```

Chọn sẵn 1 ảnh hoặc chạy toàn bộ ảnh không cần hỏi:

```bat
python brutal_mode.py --image ten_anh.jpg
python brutal_mode.py --all-images
```

Chạy không tương tác, tự dùng toàn bộ HAR/ảnh nếu có nhiều:

```bat
python brutal_mode.py --non-interactive
```

Lọc ảnh trực tiếp, chạy ảnh gốc không nén:

```bat
python brutal_mode.py --filter-images --all-images
```

Nén đa ảnh riêng, chưa thay ảnh gốc:

```bat
python loadtran_combo.py
:: Chọn: 2. Nén đa ảnh
```

Chỉ lấy ảnh trong `anh_goc/`, không quét ảnh nằm ngang thư mục tool:

```bat
python brutal_mode.py --har synthetic_player_poster.har --no-root
```

Chạy lại cả ảnh đã từng OK:

```bat
python brutal_mode.py --har synthetic_player_poster.har --rerun-all
```

## Quy tắc thư mục

Tool tự tạo các thư mục cần thiết:

- `anh_goc/`: ảnh gốc được bảo vệ, không xóa/move dù fail.
- `anh_OK/`: ảnh hoặc bản nén đã chạy OK.
- `anh_FAIL/`: giữ để tương thích, Brutal Mode không lưu ảnh fail vào đây.
- `_brutal_work/`: file nén tạm; candidate fail được xóa tự động.

Quy tắc xóa fail:

- Ảnh fail nằm trong `anh_goc/`: giữ nguyên.
- Ảnh fail nằm ngoài `anh_goc/`: xóa.
- Candidate nén fail trong `_brutal_work/`: xóa.
- Nếu ảnh gốc ngoài `anh_goc/` fail nhưng bản nén OK: bản gốc fail đó bị xóa, bản OK được copy vào `anh_OK/`.

## Test trước khi chạy thật

Kiểm tra syntax:

```bat
python -m py_compile brutal_mode.py auto_full_200.py loadtran.py loadtran_combo.py compress_for_loadtran.py update_synthetic_har.py
```

Dry-run LoadTran với HAR và ảnh có sẵn:

```bat
python loadtran.py --har synthetic_player_poster.har --dir anh_goc --dry-run
```

## File chính

- `run_combo.bat`: chạy menu combo.
- `chay_auto.bat`: chạy Brutal Mode nhanh.
- `loadtran_combo.py`: menu tổng hợp.
- `brutal_mode.py`: batch brutal/test gốc/nén/xóa fail.
- `auto_full_200.py`: wrapper tương thích cho `chay_auto.bat`.
- `loadtran.py`: flow chính upload/save poster.
- `compress_for_loadtran.py`: nén/crop ảnh về `1080x1701`.
- `update_synthetic_har.py`: cập nhật/tạo HAR từ link player-poster.
- `sign_bridge.js` + `camp-security-oversea.0.1.0.js`: sign bridge.

## Lưu ý

- Nếu gặp lỗi auth/token, capture hoặc cập nhật HAR mới.
- Nếu sign bridge lỗi, kiểm tra Node.js và đảm bảo `sign_bridge.js`, `camp-security-oversea.0.1.0.js` nằm cùng thư mục.
- Trên Windows, nên chạy bằng `run_combo.bat` hoặc `chay_auto.bat`; hai file này đã set `chcp 65001`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` để tránh lỗi dấu tiếng Việt trong console/release.
