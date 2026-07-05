@echo off
chcp 65001 >nul 2>&1
title 量化交易系统
cd /d "%~dp0"
python -u main.py
pause
