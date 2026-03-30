"""
ocr_viewer/main.py
------------------
Entry point của ứng dụng OCR Image Viewer standalone.

Cách dùng:
    python ocr_viewer/main.py                    # mở File Dialog
    python ocr_viewer/main.py path/to/image.png  # mở thẳng ảnh
    OCRViewer.exe                                # mở File Dialog
    OCRViewer.exe C:\\path\\to\\image.png         # mở thẳng ảnh

Hỗ trợ: PNG, JPG, JPEG, BMP, WEBP, TIFF, GIF
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Đảm bảo import được từ thư mục gốc (custom-snipping-tool/)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

# ─── Hằng số ─────────────────────────────────────────────────────────────────

APP_NAME    = "OCR Image Viewer"
APP_VERSION = "1.0.0"
SUPPORTED   = "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.tif *.gif)"
RECENT_FILE = Path.home() / ".ocrviewer_recent"
MAX_RECENT  = 10


# ─── Recent Files ────────────────────────────────────────────────────────────

def _load_recent() -> list[str]:
    try:
        if RECENT_FILE.exists():
            return [l for l in RECENT_FILE.read_text("utf-8").splitlines()
                    if l and Path(l).exists()]
    except Exception:
        pass
    return []


def _save_recent(path: str) -> None:
    recent = _load_recent()
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    try:
        RECENT_FILE.write_text("\n".join(recent[:MAX_RECENT]), "utf-8")
    except Exception:
        pass


# ─── File picker ─────────────────────────────────────────────────────────────

def _pick_file() -> str | None:
    recent = _load_recent()
    start  = str(Path(recent[0]).parent) if recent else str(Path.home())
    path, _ = QFileDialog.getOpenFileName(
        None, f"{APP_NAME} — Chọn ảnh", start, SUPPORTED
    )
    return path or None


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Hoangcunut")
    app.setStyle("Fusion")

    # Xác định đường dẫn ảnh từ arg hoặc file dialog
    if len(sys.argv) >= 2:
        image_path = sys.argv[1]
        if not Path(image_path).exists():
            QMessageBox.critical(None, "Không tìm thấy file",
                                 f"File không tồn tại:\n{image_path}")
            sys.exit(1)
    else:
        image_path = _pick_file()
        if not image_path:
            sys.exit(0)   # Người dùng bấm Cancel

    _save_recent(image_path)

    from ocr_viewer.viewer_app import ViewerApp
    viewer = ViewerApp(app)
    if not viewer.open(image_path):
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
