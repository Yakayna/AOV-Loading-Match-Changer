@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title LoadTran Combo
cls
cd /d "%~dp0"
echo ================================================
echo   LoadTran Combo - HAR ^> Brutal/Compress ^> Run
echo ================================================
echo.
python "%~dp0loadtran_combo.py" %*
pause
