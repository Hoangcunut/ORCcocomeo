@echo off
chcp 65001 >nul
echo ========================================================
echo   Dang bien dich Inno Setup (.iss) thanh file Cai Dat...
echo ========================================================
echo.

set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not exist %ISCC% (
    echo [Loi] Khong tim thay Inno Setup Compiler tai %ISCC%!
    echo Vui long dam bao ban da cai Inno Setup Compiler.
    pause
    exit /b 1
)

if not exist "dist\SnippingTool\SnippingTool.exe" (
    echo [Loi] Chua tim thay thu muc dist\SnippingTool hoac app build chua xong!
    echo Vui long cho tien trinh PyInstaller chay ket thuc roi thu lai.
    pause
    exit /b 1
)

%ISCC% setup.iss

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [Thanh cong] File cai dat da duoc tao trong thu muc "dist".
) else (
    echo.
    echo [Loi] Da xay ra loi trong qua trinh tao file cài đặt.
)

pause
