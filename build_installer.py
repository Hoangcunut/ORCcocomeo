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


import shutil

def _copy_engines(dist_dir: Path) -> None:
    """Sao chép các engine vào thư mục dist sau khi build onedir."""
    engines_dest = dist_dir / "engines"
    engines_dest.mkdir(parents=True, exist_ok=True)
    
    print("\n[+] Đang copy các OCR Engine vào bản Build...")

    # 1. Cop lại Umi-OCR
    umi_src = HERE / "umi-ocr"
    if umi_src.exists():
        umi_dest = engines_dest / "umi-ocr"
        if not umi_dest.exists():
            shutil.copytree(umi_src, umi_dest)
            print(f"  -> Umi-OCR ({umi_src} -> {umi_dest})")
    
    # 2. Copy Tesseract
    tess_src = HERE / "tesseract"
    if tess_src.exists():
        tess_dest = engines_dest / "tesseract"
        if not tess_dest.exists():
            shutil.copytree(tess_src, tess_dest)
            print(f"  -> Tesseract ({tess_src} -> {tess_dest})")

    # 3. Copy VietOCR models từ bộ nhớ tạm OS
    vietocr_dest = engines_dest / "vietocr" / ".cache"
    vietocr_dest.mkdir(parents=True, exist_ok=True)
    
    # Model cũ của VietOCR thường ở C:\Users\<user>\.cache\torch\hub\checkpoints 
    # VGG Transformer: vgg_transformer.pth
    # VGG seq2seq: vgg_seq2seq.pth
    os_cache_dir = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
    if os_cache_dir.exists():
        hub_dest = vietocr_dest / "hub" / "checkpoints"
        hub_dest.mkdir(parents=True, exist_ok=True)
        for pth in os_cache_dir.glob("vgg_*.pth"):
            shutil.copy2(pth, hub_dest / pth.name)
            print(f"  -> VietOCR model: {pth.name} vào {hub_dest}")
            
    print("[+] Hoàn thành copy Engines!\n")

def build_snipping() -> int:
    """Build Custom Snipping Tool dạng Modular Dir."""
    print("=" * 60)
    print("  Building: Custom Snipping Tool (SnippingTool Dir)")
    print("=" * 60)

    icon_path = HERE / "assets" / "icon.ico"

    args = [
        "--noconfirm",  # Ghi đè thư mục cũ
        "--onedir",     # Thay vì --onefile
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
    if rc == 0:
        dist_dir = HERE / "dist" / "SnippingTool"
        if dist_dir.exists():
            _copy_engines(dist_dir)
            
    _report("SnippingTool/SnippingTool.exe", rc)
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
