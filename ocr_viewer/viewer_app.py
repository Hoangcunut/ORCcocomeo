"""
viewer_app.py
-------------
Standalone OCR Image Viewer — ViewerApp + SplashWindow.

Flow:
  ViewerApp.open(image_path)
    → SplashWindow.show()   (preview ảnh + progress bar)
    → OCR chạy background thread
    → OCROverlayWindow.show()
    → SplashWindow.close()
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QPushButton, QFrame, QMessageBox,
)

from src.config import OCR_ENGINE_PREFERENCE
from src.ocr_engine import EnginePreference


# ─── Worker Thread ─────────────────────────────────────────────────────────────

class _OcrWorker(QThread):
    """Chạy VietOCR trong background thread."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)   # OcrOverlayResult
    failed   = pyqtSignal(str)

    def __init__(self, image: Image.Image, parent=None) -> None:
        super().__init__(parent)
        self._image = image
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            from src.vietocr_engine import VietOCREngine
            engine = VietOCREngine(model_name="vgg_seq2seq", device="cpu")

            def _progress_cb(msg: str) -> None:
                if not self._cancelled:
                    self.progress.emit(msg)

            result = engine.recognize(self._image, progress_cb=_progress_cb)
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as exc:
            if not self._cancelled:
                self.failed.emit(str(exc))


# ─── Splash Window ─────────────────────────────────────────────────────────────

class SplashWindow(QWidget):
    """
    Cửa sổ loading: hiện preview ảnh + thanh tiến trình OCR.
    Frameless + draggable.
    """

    cancel_requested = pyqtSignal()

    _STYLE = """
    QWidget#splash {
        background: #12121e;
        border: 1px solid #2a2a4a;
        border-radius: 12px;
    }
    QLabel#title {
        color: #e0e0ff;
        font-size: 15px;
        font-weight: 700;
    }
    QLabel#subtitle {
        color: #6688cc;
        font-size: 11px;
    }
    QLabel#status {
        color: #9999bb;
        font-size: 11px;
    }
    QProgressBar {
        background: #1c1c2e;
        border: 1px solid #2a2a4a;
        border-radius: 5px;
        height: 8px;
        text-align: center;
        color: transparent;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #4466ff, stop:1 #22ddaa);
        border-radius: 4px;
    }
    QPushButton#btn_cancel {
        background: transparent;
        color: #555577;
        border: 1px solid #2a2a44;
        border-radius: 5px;
        padding: 4px 16px;
        font-size: 11px;
    }
    QPushButton#btn_cancel:hover {
        color: #ff6666;
        border-color: #883333;
    }
    """

    def __init__(
        self,
        image: Image.Image,
        image_path: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._drag_pos: Optional[QPoint] = None
        self._image = image

        self.setObjectName("splash")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet(self._STYLE)
        self.setFixedSize(420, 330)

        self._setup_ui(image_path)
        self._center()

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _setup_ui(self, image_path: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        ico = QLabel("🔍")
        ico.setStyleSheet("font-size: 26px;")
        hdr.addWidget(ico)

        col = QVBoxLayout()
        col.setSpacing(2)
        lbl_title = QLabel("OCR Image Viewer")
        lbl_title.setObjectName("title")
        lbl_sub = QLabel(Path(image_path).name)
        lbl_sub.setObjectName("subtitle")
        lbl_sub.setWordWrap(True)
        col.addWidget(lbl_title)
        col.addWidget(lbl_sub)
        hdr.addLayout(col, stretch=1)
        root.addLayout(hdr)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background: #2a2a44; max-height: 1px; border: none;")
        root.addWidget(div)

        # Preview
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setFixedHeight(150)
        self._preview.setStyleSheet(
            "background: #0d0d1a; border-radius: 6px; border: 1px solid #1e1e36;"
        )
        self._render_preview()
        root.addWidget(self._preview)

        # Status
        self._lbl_status = QLabel("⏳ Đang chuẩn bị VietOCR model...")
        self._lbl_status.setObjectName("status")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setMinimumHeight(30)
        root.addWidget(self._lbl_status)

        # Progress bar (indeterminate)
        self._bar = QProgressBar()
        self._bar.setRange(0, 0)
        self._bar.setFixedHeight(8)
        root.addWidget(self._bar)

        # Cancel
        row = QHBoxLayout()
        row.addStretch()
        btn = QPushButton("✕  Hủy")
        btn.setObjectName("btn_cancel")
        btn.clicked.connect(self.cancel_requested.emit)
        row.addWidget(btn)
        root.addLayout(row)

    def _render_preview(self) -> None:
        img = self._image.copy()
        img.thumbnail((380, 144))
        rgb = img.convert("RGB")
        raw = rgb.tobytes("raw", "RGB")
        qi = QImage(raw, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888)
        self._preview.setPixmap(
            QPixmap.fromImage(qi).scaled(
                376, 144,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def update_status(self, msg: str) -> None:
        self._lbl_status.setText(msg)

    def _center(self) -> None:
        scr = QGuiApplication.primaryScreen()
        if scr:
            g = scr.availableGeometry()
            self.move(g.center().x() - self.width() // 2,
                      g.center().y() - self.height() // 2)

    # ── Draggable ────────────────────────────────────────────────────────────

    def mousePressEvent(self, e) -> None:   # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e) -> None:   # type: ignore[override]
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e) -> None:   # type: ignore[override]
        self._drag_pos = None


# ─── ViewerApp ────────────────────────────────────────────────────────────────

class ViewerApp:
    """
    Controller standalone OCR Image Viewer.

    Usage:
        app = QApplication(sys.argv)
        ok = ViewerApp(app).open(image_path)
        if ok: sys.exit(app.exec())
    """

    def __init__(self, app: QApplication) -> None:
        self._app     = app
        self._splash: Optional[SplashWindow]  = None
        self._worker: Optional[_OcrWorker]    = None
        self._overlay = None   # OCROverlayWindow — lazy import
        self._image: Optional[Image.Image]    = None
        self._image_path: str = ""

    def open(self, image_path: str) -> bool:
        """Mở ảnh → splash + OCR. Returns False nếu lỗi đọc file."""
        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as exc:
            QMessageBox.critical(
                None, "Không mở được file",
                f"Lỗi đọc ảnh:\n{image_path}\n\n{exc}"
            )
            return False

        self._image      = image
        self._image_path = image_path

        # Hiện splash
        self._splash = SplashWindow(image, image_path)
        self._splash.cancel_requested.connect(self._on_cancel)
        self._splash.show()

        engine_pref = EnginePreference(OCR_ENGINE_PREFERENCE)

        # Pre-import torch trên main thread để tránh WinError 1114
        if engine_pref in (EnginePreference.AUTO, EnginePreference.VIETOCR):
            self._splash.update_status("Đang tải thư viện AI...")
            QApplication.processEvents()
            try:
                import torch
            except ImportError:
                pass

        # Chạy OCR trong background
        self._worker = _OcrWorker(image)
        self._worker.progress.connect(self._splash.update_status)
        self._worker.finished.connect(self._on_ocr_done)
        self._worker.failed.connect(self._on_ocr_failed)
        self._worker.start()

        return True

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_ocr_done(self, ocr_result) -> None:
        """OCR xong → đóng splash, mở overlay."""
        self._close_splash()

        from src.ui.ocr_overlay_window import OCROverlayWindow
        self._overlay = OCROverlayWindow(self._image, ocr_result)
        self._overlay.show()

        # Khi overlay đóng → thoát app
        self._overlay.destroyed.connect(self._app.quit)

    def _on_ocr_failed(self, msg: str) -> None:
        if self._splash:
            self._splash.update_status(f"❌ {msg[:100]}")
        QMessageBox.critical(
            self._splash, "Lỗi OCR",
            f"VietOCR gặp lỗi:\n\n{msg}\n\n"
            "Hãy chạy: pip install vietocr torch torchvision"
        )
        self._close_splash()

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._worker.quit()
        self._close_splash()
        self._app.quit()

    def _close_splash(self) -> None:
        if self._splash:
            self._splash.close()
            self._splash = None
