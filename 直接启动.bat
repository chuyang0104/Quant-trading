@echo off
chcp 65001 >nul 2>&1
title Quant Trading System
cd /d D:\project\Quant-trading
python startup.py
if errorlevel 1 pause
