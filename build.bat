@echo off
:: ============================================================
:: build.bat — Build .exe bằng Nuitka (Giai đoạn 5)
:: Chạy: build.bat
:: Yêu cầu: pip install nuitka zstandard
:: ============================================================

echo [BUILD] Bat dau build Custom Snipping Tool...

python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=assets\icon.ico ^
    --output-filename=SnippingTool.exe ^
    --output-dir=dist ^
    --include-data-dir=assets=assets ^
    --plugin-enable=pyqt6 ^
    --nofollow-import-to=tkinter ^
    --nofollow-import-to=matplotlib ^
    --nofollow-import-to=scipy ^
    --assume-yes-for-downloads ^
    main.py

echo.
echo [BUILD] Hoan thanh! File: dist\SnippingTool.exe
pause
