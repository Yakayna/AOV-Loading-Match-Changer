LoadTran Combo - goi share
===========================

File chay nhanh:
  run_combo.bat

File auto batch goc:
  chay_auto.bat
  auto_full_200.py

Hoac chay bang PowerShell/CMD:
  python loadtran_combo.py

Can cai:
  pip install -r requirements.txt
  Node.js de sign_bridge hoat dong

Flow su dung:
  1) Chay run_combo.bat
  2) Chon co update HAR hay khong
  3) Neu update HAR: dan link player-poster co itopencodeparam
  4) Chon file .har neu co nhieu file .har
  5) Chon BRUTAL MODE neu muon auto chay nhieu anh:
     - Bo anh goc vao thu muc anh_goc/ hoac de ngang hang run_combo.bat
     - KHONG xoa / khong move anh trong anh_goc/
     - Tool test anh goc truoc
     - Neu anh goc fail, tool moi tu nen ra ban tam trong _brutal_work/ va test tiep
     - Anh dat duoc se duoc copy vao anh_OK/
     - Luon xoa anh/candidate fail, tru anh nam trong anh_goc/
     - Chay 5 anh moi batch
     - Nghi 6 giay giua batch
     - Preset nen mac dinh: 70,60,50,40,45,40,36,35,32,30
     - Tong ket hien ro OK, FAIL cuoi, FAIL giu trong anh_goc/, FAIL da xoa ngoai anh_goc/, candidate fail da xoa
  6) Neu khong dung brutal: chon anh/media, chon co nen anh khong
  7) Neu nen anh thuong: nhap KB, khuyen nghi 100KB; nhap 0 = MAX-READABLE
  8) Tool tu chay loadtran.py

Luu y:
  - Goi ZIP nay khong kem anh va khong kem file .har.
  - Moi nguoi dung tu bo anh vao thu muc tool.
  - Moi nguoi dung tu cap nhat/tai tao synthetic_player_poster.har bang link cua acc minh.
  - Che do nen thuong se thay file goc trong thu muc dang chay.
  - Brutal mode chi bao ve anh trong anh_goc/; file fail ngoai anh_goc/ se bi xoa.

File chinh:
  loadtran_combo.py
  brutal_mode.py
  auto_full_200.py
  loadtran.py
  compress_for_loadtran.py
  update_synthetic_har.py
  sign_bridge.js
  camp-security-oversea.0.1.0.js
