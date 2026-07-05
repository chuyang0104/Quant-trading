@echo off
chcp 65001 >nul 2>&1
title 打包量化交易启动器
echo ========================================
echo   打包 量化交易系统启动器.exe
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查 PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 正在安装 PyInstaller...
    pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo.
echo [2/3] 开始打包...
pyinstaller --onefile --windowed --name "量化交易系统" ^
    --consoleless ^
    --icon NONE ^
    --collect-all tkinter ^
    launcher.py

echo.
echo [3/3] 打包完成!
echo.
echo exe 文件位置: dist\量化交易系统.exe
echo.
pause
