LoadTran Combo - gói share
==========================

File chạy nhanh:
  run_combo.bat

File auto batch gốc:
  chay_auto.bat
  auto_full_200.py

Hoặc chạy bằng PowerShell/CMD:
  python loadtran_combo.py

Cần cài:
  pip install -r requirements.txt
  Node.js để sign_bridge hoạt động

Flow sử dụng:
  1) Chạy run_combo.bat
  2) Chọn có update HAR hay không
  3) Nếu update HAR: dán link player-poster có itopencodeparam
  4) Chọn BRUTAL MODE nếu muốn auto chạy nhiều ảnh:
     - Bỏ ảnh gốc vào thư mục anh_goc/ hoặc để ngang hàng run_combo.bat
     - Nếu có nhiều hơn 1 file HAR: tool hỏi chọn 1 HAR hay toàn bộ HAR
     - Nếu có nhiều hơn 1 ảnh: tool hỏi chọn 1 ảnh hay toàn bộ ảnh
     - KHÔNG xóa / không move ảnh trong anh_goc/
     - Tool test ảnh gốc trước
     - Nếu ảnh gốc fail, tool mới tự nén ra bản tạm trong _brutal_work/ và test tiếp
     - Ảnh đã pass ở mốc nào thì dừng ở mốc đó, không nén tiếp mốc thấp hơn
     - Ảnh đạt được sẽ được copy vào anh_OK/
     - Luôn xóa ảnh/candidate fail, trừ ảnh nằm trong anh_goc/
     - Chạy 5 ảnh mỗi batch
     - Nghỉ 6 giây giữa batch
     - Preset nén mặc định: 70,60,50,40,45,40,36,35,32,30
     - Tổng kết hiện rõ OK, FAIL cuối, FAIL giữ trong anh_goc/, FAIL đã xóa ngoài anh_goc/, candidate fail đã xóa
  5) Nếu không dùng Brutal Mode: chọn HAR, chọn ảnh/media, chọn có nén ảnh không
  6) Nếu nén ảnh thường: nhập KB, khuyến nghị 100KB; nhập 0 = MAX-READABLE
  7) Tool tự chạy loadtran.py

Lưu ý:
  - Gói ZIP này không kèm ảnh và không kèm file .har.
  - Người dùng tự bỏ ảnh vào thư mục tool.
  - Người dùng tự cập nhật/tái tạo synthetic_player_poster.har bằng link của acc mình.
  - Chế độ nén thường sẽ thay file gốc trong thư mục đang chạy.
  - Brutal Mode chỉ bảo vệ ảnh trong anh_goc/; file fail ngoài anh_goc/ sẽ bị xóa.
  - Trên Windows hãy chạy bằng run_combo.bat/chay_auto.bat để dùng UTF-8, tránh lỗi dấu tiếng Việt.

File chính:
  loadtran_combo.py
  brutal_mode.py
  auto_full_200.py
  loadtran.py
  compress_for_loadtran.py
  update_synthetic_har.py
  sign_bridge.js
  camp-security-oversea.0.1.0.js
