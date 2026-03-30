"""
ocr_overlay_window.py
---------------------
Giao diện xem kết quả OCR dưới dạng một lớp văn bản trong suốt (Invisible Text Layer)
có thể chọn, bôi đen, nhấp chuột và sao chép như trên trình duyệt nguyên bản.

Tối ưu:
  - QWebEngineView được lazy-import để tránh bắt buộc PyQt6-WebEngine khi không dùng
  - Ảnh lớn sẽ được scale down trước khi encode base64 để giảm bộ nhớ
  - Copy All Text button cho phép copy toàn bộ nội dung không cần bôi đen
  - Zoom in/out bằng Ctrl+Scroll
"""

from __future__ import annotations

import base64
import html as html_mod
from io import BytesIO

from PIL import Image
from PyQt6.QtCore import Qt, QPoint, QUrl
from PyQt6.QtGui import QMouseEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QApplication
)

# Lazy import — không import QWebEngineView ở top-level
# để tránh crash nếu PyQt6-WebEngine chưa cài
from src.vietocr_engine import OcrOverlayResult


# ─── Constants ────────────────────────────────────────────────────────────────

_TITLE_BAR_HEIGHT = 42
_MAX_IMAGE_DIM = 3000  # Scale down nếu ảnh vượt quá pixel này


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _pil_to_base64_png(image: Image.Image) -> str:
    """Mã hoá PIL Image → Base64 PNG. Scale down nếu quá lớn."""
    img = image.copy()
    if img.mode != "RGB":
        img = img.convert("RGB")
    # Scale down ảnh quá lớn để giảm bộ nhớ WebEngine
    if img.width > _MAX_IMAGE_DIM or img.height > _MAX_IMAGE_DIM:
        img.thumbnail((_MAX_IMAGE_DIM, _MAX_IMAGE_DIM), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _scale_factor(image: Image.Image) -> float:
    """Tính tỉ lệ thu nhỏ nếu ảnh đã bị scale down."""
    if image.width <= _MAX_IMAGE_DIM and image.height <= _MAX_IMAGE_DIM:
        return 1.0
    return min(_MAX_IMAGE_DIM / image.width, _MAX_IMAGE_DIM / image.height)


# ─── Window ──────────────────────────────────────────────────────────────────

class OCROverlayWindow(QMainWindow):
    """
    Cửa sổ độc lập (frameless, draggable) hiển thị ảnh + lớp text trong suốt.
    Người dùng có thể bôi đen text → Ctrl+C để copy, hoặc bấm nút Copy All.
    """

    def __init__(
        self,
        image: Image.Image,
        overlay_result: OcrOverlayResult,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._image = image
        self._overlay_result = overlay_result
        self._scale = _scale_factor(image)

        # Frameless + luôn ở trên
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Draggable state
        self._is_dragging = False
        self._drag_origin = QPoint()

        self._build_ui()
        self._setup_shortcuts()

    # ─── UI Build ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Kích thước cửa sổ
        display_w = int(self._image.width * self._scale)
        display_h = int(self._image.height * self._scale) + _TITLE_BAR_HEIGHT + 40
        self.resize(max(display_w, 420), min(display_h, 920))

        central = QWidget()
        self.setCentralWidget(central)
        central.setObjectName("overlay_central")
        central.setStyleSheet("""
            #overlay_central {
                background-color: #1E1E22;
                border: 1px solid #3E3E42;
                border-radius: 6px;
            }
        """)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title bar (draggable) ────────────────────────────────────────────
        title_bar = QWidget()
        title_bar.setFixedHeight(_TITLE_BAR_HEIGHT)
        title_bar.setStyleSheet(
            "background: #2D2D30; border-top-left-radius: 6px; border-top-right-radius: 6px;"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(14, 0, 8, 0)

        lbl_title = QLabel("📄 VietOCR Overlay — Bôi đen để copy")
        lbl_title.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 13px;")
        tb_layout.addWidget(lbl_title)

        lbl_hint = QLabel("  (kéo thanh này để di chuyển)")
        lbl_hint.setStyleSheet("color: #666; font-size: 10px;")
        tb_layout.addWidget(lbl_hint)
        tb_layout.addStretch()

        btn_copy_all = QPushButton("📋 Copy All")
        btn_copy_all.setFixedHeight(28)
        btn_copy_all.setToolTip("Copy toàn bộ nội dung OCR (Ctrl+Shift+C)")
        btn_copy_all.setStyleSheet("""
            QPushButton {
                color: #ccc; background: rgba(255,255,255,8);
                border: 1px solid #555; border-radius: 4px;
                padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background: rgba(255,255,255,18); color: white; }
        """)
        btn_copy_all.clicked.connect(self._copy_all_text)
        tb_layout.addWidget(btn_copy_all)

        tb_layout.addSpacing(4)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setToolTip("Đóng (Esc)")
        btn_close.setStyleSheet("""
            QPushButton {
                color: #ccc; background: transparent; border: none;
                font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover { background: #E81123; color: white; }
        """)
        btn_close.clicked.connect(self.close)
        tb_layout.addWidget(btn_close)

        # Mouse events cho title bar → draggable
        title_bar.mousePressEvent = self._on_title_press
        title_bar.mouseMoveEvent = self._on_title_move
        title_bar.mouseReleaseEvent = self._on_title_release

        root.addWidget(title_bar)

        # ── WebEngine View ───────────────────────────────────────────────────
        from PyQt6.QtWebEngineWidgets import QWebEngineView

        self._web = QWebEngineView()
        self._web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._web.setHtml(self._build_html())
        root.addWidget(self._web)

        # ── Bottom status ────────────────────────────────────────────────────
        bottom = QWidget()
        bottom.setFixedHeight(28)
        bottom.setStyleSheet("background: #252529;")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(12, 0, 12, 0)
        word_count = len(self._overlay_result.word_boxes)
        char_count = len(self._overlay_result.plain_text)
        lbl_stats = QLabel(f"🔤 {word_count} dòng  •  {char_count} ký tự  •  Ctrl+Scroll zoom")
        lbl_stats.setStyleSheet("color: #888; font-size: 10px;")
        bl.addWidget(lbl_stats)
        bl.addStretch()
        root.addWidget(bottom)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(self._copy_all_text)

    # ─── HTML Generation ─────────────────────────────────────────────────────

    def _build_html(self) -> str:
        b64 = _pil_to_base64_png(self._image)
        scale = self._scale

        spans = []
        for box in self._overlay_result.word_boxes:
            # Tính toạ độ đã scale
            sx = int(box.x * scale)
            sy = int(box.y * scale)
            sw = int(box.width * scale)
            sh = int(box.height * scale)
            fs = max(int(sh * 0.78), 9)

            escaped = html_mod.escape(box.text, quote=True)
            spans.append(
                f'<span class="w" title="{escaped}" '
                f'style="left:{sx}px;top:{sy}px;width:{sw}px;height:{sh}px;'
                f'font-size:{fs}px;line-height:{sh}px;">'
                f'{escaped}</span>'
            )

        spans_html = "\n".join(spans)
        img_w = int(self._image.width * scale)
        img_h = int(self._image.height * scale)

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  html, body {{
    background: #1a1a24;
    overflow: auto;
    /* Ngăn highlight ngoài vùng text */
    user-select: none;
    -webkit-user-select: none;
  }}

  .container {{
    position: relative;
    display: inline-block;
    width: {img_w}px;
    height: {img_h}px;
    /* Shadow nhẹ quanh ảnh để tăng readability */
    box-shadow: 0 4px 24px rgba(0,0,0,0.6);
    margin: 8px;
  }}

  .container img {{
    display: block;
    width: {img_w}px;
    height: {img_h}px;
    pointer-events: none;
    -webkit-user-drag: none;
    user-select: none;
    -webkit-user-select: none;
  }}

  .text-layer {{
    position: absolute;
    top: 0; left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }}

  /* Mỗi span text = 1 dòng OCR */
  .w {{
    position: absolute;
    /* Near-invisible: mắt thường không thấy, selection vẫn hoạt động */
    color: rgba(0, 0, 0, 0.002);
    cursor: text;
    user-select: text;
    -webkit-user-select: text;
    pointer-events: all;
    white-space: nowrap;
    overflow: visible;
    font-family: 'Segoe UI', 'Arial Unicode MS', sans-serif;
    /* Scale chữ vừa khít box để selection khớp với ảnh */
    transform-origin: left top;
  }}

  /* Hover: gợi ý người dùng biết có text ở đây */
  .w:hover {{
    background: rgba(80, 160, 255, 0.12);
    border-radius: 2px;
    outline: 1px dashed rgba(80, 160, 255, 0.35);
  }}

  /* Selection: contrast cao — chữ trắng nền xanh đậm */
  .w::selection {{
    background: rgba(0, 100, 220, 0.75);
    color: #ffffff;
  }}
  .w::-moz-selection {{
    background: rgba(0, 100, 220, 0.75);
    color: #ffffff;
  }}

  /* Ctrl+A select all: highlight toàn bộ text layer */
  .text-layer.all-selected .w {{
    background: rgba(0, 100, 220, 0.35);
  }}
</style>
</head>
<body>
<div class="container">
  <img src="data:image/png;base64,{b64}" alt="OCR Image" draggable="false">
  <div class="text-layer" id="tl">
    {spans_html}
  </div>
</div>
<script>
/* Ctrl+A: chọn toàn bộ text */
document.addEventListener('keydown', function(e) {{
  if ((e.ctrlKey || e.metaKey) && e.key === 'a') {{
    e.preventDefault();
    var sel = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(document.getElementById('tl'));
    sel.removeAllRanges();
    sel.addRange(range);
  }}
}});
</script>
</body></html>"""

    # ─── Copy All ────────────────────────────────────────────────────────────

    def _copy_all_text(self) -> None:
        text = self._overlay_result.plain_text
        if text:
            QApplication.clipboard().setText(text)

    # ─── Draggable Title Bar ─────────────────────────────────────────────────

    def _on_title_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_origin = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def _on_title_move(self, event: QMouseEvent) -> None:
        if self._is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()

    def _on_title_release(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            event.accept()
