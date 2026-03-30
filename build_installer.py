"""
build_installer.py
------------------
Script build .exe bằng PyInstaller.

Cách dùng:
    python build_installer.py

Output: dist/OCRViewer.exe

Yêu cầu trước khi build:
    pip install pyinstaller
    pip install vietocr torch torchvision PyQt6 PyQt6-WebEngine
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    print("=" * 60)
    print("  OCR Viewer — Build Installer")
    print("=" * 60)

    # Kiểm tra pyinstaller
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[ERR] PyInstaller chưa cài. Chạy:")
        print("      pip install pyinstaller")
        sys.exit(1)

    entry = HERE / "main.py"
    if not entry.exists():
        print(f"[ERR] Không tìm thấy: {entry}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                          # Đóng gói thành 1 file exe
        "--windowed",                         # Không hiện cmd window
        "--name", "OCRViewer",
        "--icon", str(HERE / "assets" / "icon.ico") if (HERE / "assets" / "icon.ico").exists() else "NONE",

        # PyQt6 + WebEngine data
        "--collect-data", "PyQt6",
        "--collect-data", "PyQt6.QtWebEngineWidgets",

        # VietOCR config files
        "--collect-data", "vietocr",

        # Torch (nặng nhưng cần thiết cho VietOCR)
        "--collect-data", "torch",

        str(entry),
    ]

    # Bỏ icon nếu không có file
    cmd = [c for c in cmd if c != "NONE" and not (c == "--icon" and "NONE" in cmd)]

    print(f"\n[CMD] {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=HERE)

    if result.returncode == 0:
        exe_path = HERE / "dist" / "OCRViewer.exe"
        print("\n" + "=" * 60)
        print(f"  ✅ Build thành công!")
        print(f"  📦 Output: {exe_path}")
        size_mb = exe_path.stat().st_size / 1_048_576 if exe_path.exists() else 0
        print(f"  📏 Kích thước: {size_mb:.1f} MB")
        print("=" * 60)
    else:
        print("\n[ERR] Build thất bại! Xem log ở trên để biết nguyên nhân.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
