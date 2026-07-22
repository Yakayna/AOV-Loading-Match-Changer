@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title BRUTAL LOADTRAN - XÓA FAIL NGOÀI ANH_GOC

cd /d "%~dp0"

echo ================================================
echo        BRUTAL LOADTRAN - XÓA FAIL NGOÀI ANH_GOC
echo        Test gốc trước, fail thì tự nén
echo        Batch 5 ảnh, nghỉ 6 giây giữa batch
echo        Preset: 70 60 50 40 45 40 36 35 32 30 KB
echo ================================================
echo.

python "%~dp0auto_full_200.py"

echo.
echo ================================================
echo        DA KET THUC
echo ================================================
pause
