@echo off
chcp 65001 >nul
title 马丁策略机器人

echo ========================================
echo   币安合约马丁策略机器人
echo ========================================
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.9+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b
)

:: 检查依赖
echo [1/3] 检查依赖...
pip show ccxt >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络
        pause
        exit /b
    )
)

:: 检查.env
echo [2/3] 检查配置...
if not exist .env (
    echo [警告] 未找到.env配置文件!
    echo 正在从.env.example创建.env...
    copy .env.example .env
    echo.
    echo ⚠️ 请编辑 .env 文件，填入你的币安API Key和Secret!
    echo 然后重新运行此脚本。
    notepad .env
    pause
    exit /b
)

:: 启动
echo [3/3] 启动机器人...
echo.
python main.py

pause
