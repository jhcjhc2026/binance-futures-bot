@echo off
chcp 65001 >nul
title ETH Grid Bot - LIVE (Auto Restart)
cd /d "%~dp0"
:loop
python -u grid_bot.py --yes
echo.
echo ========================================
echo  Bot exited. Restarting in 5 seconds...
echo  Press Ctrl+C to stop completely.
echo ========================================
timeout /t 5 /nobreak >nul
goto loop
