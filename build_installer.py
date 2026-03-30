"""
build_installer.py
------------------
Script build .exe bằng PyInstaller cho 2 target:

  1. OCRViewer.exe         — standalone image viewer (chính)
  2. SnippingTool.exe      — custom snipping tool (tool gốc)

Cách dùng:
    python build_installer.py            # build OCRViewer (mặc định)
    python build_installer.py --viewer   # build OCRViewer
    python build_installer.py --snipping # build SnippingTool
    python build_installer.py --all      # build cả hai

Yêu cầu:
    pip install pyinstaller
    pip install vietocr torch torchvision PyQt6 PyQt6-WebEngine pytesseract Pillow
"""

from __future__ import annotations

import subprocess
import sys
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _run_pyinstaller(args: list[str]) -> int:
    """Chạy PyInstaller và trả về exit code."""
    cmd = [sys.executable, "-m", "PyInstaller"] + args
    print(f"\n>>> {' '.join(cmd)}\n")
    return subprocess.run(cmd, cwd=HERE).returncode


def build_viewer() -> int:
    """Build OCR Image Viewer standalone."""
    print("=" * 60)
    print("  Building: OCR Image Viewer (OCRViewer.exe)")
    print("=" * 60)

    icon_path = HERE / "assets" / "icon.ico"

    args = [
        "--onefile",
        "--windowed",
        "--name", "OCRViewer",
        "--clean",

        # ── Hidden imports cần thiết ──────────────────────────────────────
        "--hidden-import", "vietocr",
        "--hidden-import", "vietocr.tool.predictor",
        "--hidden-import", "vietocr.tool.config",
        "--hidden-import", "torch",
        "--hidden-import", "torchvision",
        "--hidden-import", "pytesseract",
        "--hidden-import", "PIL",
        "--hidden-import", "PyQt6.QtWebEngineWidgets",
        "--hidden-import", "PyQt6.QtWebEngineCore",

        # ── Collect data packages ─────────────────────────────────────────
        "--collect-data", "vietocr",
        "--collect-data", "PyQt6",

        # ── Đường dẫn tìm module ─────────────────────────────────────────
        "--paths", str(HERE),
    ]

    # Icon nếu có
    if icon_path.exists():
        args += ["--icon", str(icon_path)]

    # Entry point
    args.append(str(HERE / "ocr_viewer" / "main.py"))

    rc = _run_pyinstaller(args)
    _report("OCRViewer.exe", rc)
    return rc


def build_snipping() -> int:
    """Build Custom Snipping Tool."""
    print("=" * 60)
    print("  Building: Custom Snipping Tool (SnippingTool.exe)")
    print("=" * 60)

    icon_path = HERE / "assets" / "icon.ico"

    args = [
        "--onefile",
        "--windowed",
        "--name", "SnippingTool",
        "--clean",
        "--hidden-import", "PyQt6.QtWebEngineWidgets",
        "--hidden-import", "PyQt6.QtWebEngineCore",
        "--hidden-import", "vietocr",
        "--hidden-import", "torch",
        "--hidden-import", "pytesseract",
        "--collect-data", "PyQt6",
        "--collect-data", "vietocr",
        "--paths", str(HERE),
    ]

    if icon_path.exists():
        args += ["--icon", str(icon_path)]

    args.append(str(HERE / "main.py"))

    rc = _run_pyinstaller(args)
    _report("SnippingTool.exe", rc)
    return rc


def _report(name: str, rc: int) -> None:
    exe = HERE / "dist" / name
    if rc == 0 and exe.exists():
        size_mb = exe.stat().st_size / 1_048_576
        print("\n" + "=" * 60)
        print(f"  ✅ Build thành công!")
        print(f"  📦 {exe}")
        print(f"  📏 Kích thước: {size_mb:.1f} MB")
        print("=" * 60)
    elif rc != 0:
        print("\n❌ Build thất bại! Xem log ở trên.")


def main() -> None:
    # Kiểm tra PyInstaller
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[ERR] PyInstaller chưa cài. Chạy:")
        print("      pip install pyinstaller")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Build OCRViewer / SnippingTool EXE")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--viewer",   action="store_true", help="Build OCRViewer.exe (mặc định)")
    group.add_argument("--snipping", action="store_true", help="Build SnippingTool.exe")
    group.add_argument("--all",      action="store_true", help="Build cả hai")
    args = parser.parse_args()

    results = []

    if args.snipping:
        results.append(build_snipping())
    elif args.all:
        results.append(build_viewer())
        results.append(build_snipping())
    else:
        # Mặc định: build viewer
        results.append(build_viewer())

    sys.exit(max(results) if results else 0)


if __name__ == "__main__":
    main()
