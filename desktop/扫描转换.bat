@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title 文档转Markdown - 扫描版（强制OCR）

if "%~1"=="" (
    echo.
    echo 请把文件拖到这个图标上（适合扫描件、拍照截图、影印PDF）
    echo.
    pause
    exit /b
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PY=__ROOT__\.venv\Scripts\python.exe"
set "SCRIPT=__ROOT__\skills\everything-to-markdown\scripts\convert_to_md.py"
set "INPUT=%~f1"
set "OUT=%~dp1%~n1.converted.md"

echo.
echo ========================================
echo  正在处理: %~nx1
echo  模式: 强制 OCR（用于扫描件/图片）
echo ========================================
echo.

if not exist "%PY%" (
    echo 找不到项目里的 Python：
    echo %PY%
    echo 请回到项目文件夹，重新运行 install.ps1
    pause
    exit /b 1
)
if not exist "%SCRIPT%" (
    echo 找不到转换脚本：
    echo %SCRIPT%
    echo 请确认项目文件夹完整，并重新运行 install.ps1
    pause
    exit /b 1
)

"%PY%" "%SCRIPT%" "%INPUT%" --mode force-ocr -o "%OUT%"
if errorlevel 1 (
    echo.
    echo 转换失败。扫描件需要已安装 Tesseract。也可先复制到短路径再拖。
    pause
    exit /b 1
)

echo.
echo ========================================
if exist "%OUT%" (
    echo  完成: %OUT%
) else (
    echo  脚本已结束，但没找到输出文件
)
echo ========================================
pause
