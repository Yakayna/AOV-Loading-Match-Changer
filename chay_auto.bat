@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title BRUTAL LOADTRAN - XOA FAIL NGOAI ANH_GOC

cd /d "%~dp0"

echo ================================================
echo        BRUTAL LOADTRAN - XOA FAIL NGOAI ANH_GOC
echo        Test goc truoc, fail thi tu nen
echo        Batch 5 anh, nghi 6 giay giua batch
echo        Preset: 70 60 50 40 45 40 36 35 32 30 KB
echo ================================================
echo.

python "%~dp0auto_full_200.py"

echo.
echo ================================================
echo        DA KET THUC
echo ================================================
pause
