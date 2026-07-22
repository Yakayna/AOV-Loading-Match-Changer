#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper tuong thich chay_auto.bat: goi brutal_mode moi.
- Khong xoa/move anh trong anh_goc/.
- Anh fail ngoai anh_goc/ se bi xoa.
- Test anh goc truoc; fail thi tu nen variants va test tiep.
- Neu co nhieu HAR/anh, brutal_mode se hoi chon 1 file hay toan bo.
- Anh pass o moc nao thi dung o moc do, khong nen tiep moc thap hon.
- Batch 5 anh va nghi 6 giay nhu source auto 2 anh do len.
- Preset nen mac dinh: 70,60,50,40,45,40,36,35,32,30.
"""

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import brutal_mode


if __name__ == "__main__":
    brutal_mode.run_brutal(
        har=None,
        source_dir="anh_goc",
        ok_dir="anh_OK",
        fail_dir="anh_FAIL",
        work_dir="_brutal_work",
        batch_size=5,
        sleep_between_batch=6,
        targets=brutal_mode.DEFAULT_TARGETS,
        include_root=True,
        rerun_all=False,
    )
    input("\nNhan Enter de thoat...")
