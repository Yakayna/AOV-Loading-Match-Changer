LoadTran Combo - gói share
==========================

File chạy nhanh:
  run_combo.bat

Hoặc chạy bằng PowerShell/CMD:
  python loadtran_combo.py

Cần cài:
  pip install -r requirements.txt
  Node.js để sign_bridge hoạt động

Flow sử dụng:
  1) Chạy run_combo.bat
  2) Chọn Thay ảnh load hoặc Nén đa ảnh
  3) Nếu chọn Thay ảnh load: chọn có update HAR hay không
  4) Nếu update HAR: dán link player-poster có itopencodeparam
  5) Chọn chế độ auto ảnh:
     - 0 = chạy thường
     - 1 = Brutal Mode
     - 2 = Lọc ảnh
     - 3 = Sanitize + load ảnh
     - 4 = Sanitize + nén ảnh + load
  6) Làm theo câu hỏi trên màn hình

Lưu ý:
  - Gói ZIP này không kèm ảnh và không kèm file .har.
  - Người dùng tự bỏ ảnh vào thư mục tool hoặc anh_goc/.
  - Người dùng tự cập nhật/tái tạo HAR bằng link của acc mình.
  - Trên Windows hãy chạy bằng run_combo.bat/chay_auto.bat để dùng UTF-8.

File chính:
  loadtran_combo.py
  brutal_mode.py
  auto_full_200.py
  loadtran.py
  compress_for_loadtran.py
  update_synthetic_har.py
  sign_bridge.js
  camp-security-oversea.0.1.0.js
