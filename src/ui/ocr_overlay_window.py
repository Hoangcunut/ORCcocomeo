"""
ocr_overlay_window.py
---------------------
Cửa sổ xem ảnh + text overlay có thể bôi đen / copy như trình duyệt.

  ┌─────────────────────────────────────────────┐
  │  Toolbar: [X Close] [🔍+] [🔍-] [📋 Copy]  │
  │─────────────────────────────────────────────│
  │  QWebEngineView:                            │
  │  ┌──────────ảnh gốc──────────┐              │
  │  │  <span>Tiếng Việt</span>  │  ← select   │
  │  │  <span>đầy đủ dấu</span>  │  ← copy     │
  │  └────────────────────────────┘             │
  └─────────────────────────────────────────────┘

Text selection: native browser selection (drag, Ctrl+A, Ctrl+C).
Draggable: nhấn giữ titlebar / bất kỳ vùng trống để kéo.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import List, Optional

from PIL import Image
from PyQt6.QtCore import Qt, QPoint, QUrl
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSizeGrip, QFrame,
)
from PyQt6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWebEngineWidgets import QWebEngineView

from src.vietocr_engine import OcrOverlayResult, WordBox


# ─── HTML Template ────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; user-select: none; }}
html, body {{ background: #1a1a2e; overflow: hidden; width: 100%; height: 100%; }}

#container {{
  position: relative;
  display: inline-block;
  /* width & height set via JS */
}}

#img-layer {{
  display: block;
  width: {img_width}px;
  height: {img_height}px;
  image-rendering: auto;
}}

/* Lớp text overlay — toàn bộ container, trong suốt */
#text-layer {{
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;  /* click xuyên qua xuống ảnh khi không chọn text */
}}

/* Từng dòng text */
.txt-box {{
  position: absolute;
  white-space: pre;
  cursor: text;
  user-select: text;
  pointer-events: all;
  color: transparent;          /* ẩn text, chỉ hiện khi select */
  background: transparent;
  font-family: Arial, sans-serif;
  line-height: 1;
  padding: 0 1px;
  border-radius: 2px;
  transition: background 0.1s;
}}

/* Khi hover: hiện viền nhẹ để user biết có text */
.txt-box:hover {{
  background: rgba(100, 180, 255, 0.18);
  outline: 1px dashed rgba(100, 180, 255, 0.5);
}}

/* Khi select: highlight xanh đậm */
::selection {{
  color: #ffffff;
  background: rgba(0, 120, 255, 0.65);
}}

/* Scroll wrapper */
#scroll-wrapper {{
  width: 100vw;
  height: 100vh;
  overflow: auto;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  background: #1a1a2e;
}}
</style>
</head>
<body>
<div id="scroll-wrapper">
  <div id="container" style="width:{img_width}px;height:{img_height}px;">
    <img id="img-layer" src="data:image/png;base64,{img_b64}" draggable="false" />
    <div id="text-layer">
{text_spans}
    </div>
  </div>
</div>
<script>
// Ctrl+A: select all text trong overlay
document.addEventListener('keydown', function(e) {{
  if ((e.ctrlKey || e.metaKey) && e.key === 'a') {{
    e.preventDefault();
    var sel = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(document.getElementById('text-layer'));
    sel.removeAllRanges();
    sel.addRange(range);
  }}
}});
</script>
</body>
</html>
"""


def _build_text_spans(word_boxes: List[WordBox], img_w: int, img_h: int) -> str:
    """Sinh HTML spans định vị theo tọa độ pixel."""
    spans = []
    for wb in word_boxes:
        if wb.is_empty:
            continue
        # font-size tỉ lệ theo chiều cao box, tối thiểu 8px
        font_size = max(8, int(wb.height * 0.85))
        text_escaped = (
            wb.text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        spans.append(
            f'      <span class="txt-box" '
            f'style="left:{wb.x}px;top:{wb.y}px;'
            f'width:{wb.width}px;height:{wb.height}px;'
            f'font-size:{font_size}px;">'
            f'{text_escaped}</span>'
        )
    return "\n".join(spans)


def _image_to_base64(image: Image.Image) -> str:
    """Chuyển PIL Image → base64 PNG string."""
    buf = BytesIO()
    image.save(buf, format="PNG", optimize=False)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ─── OCR Overlay Window ───────────────────────────────────────────────────────

class OCROverlayWindow(QMainWindow):
    """
    Cửa sổ độc lập hiển thị ảnh + text overlay có thể bôi đen / copy.

    Draggable: nhấn giữ vùng titlebar tùy chỉnh để kéo.
    Text selection: browser-native (drag, Ctrl+A, Ctrl+C / CmdC).

    Usage:
        win = OCROverlayWindow(pil_image, ocr_result)
        win.show()
    """

    def __init__(
        self,
        image: Image.Image,
        ocr_result: OcrOverlayResult,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._image      = image
        self._ocr_result = ocr_result
        self._drag_pos: Optional[QPoint] = None
        self._zoom       = 1.0

        self._setup_window()
        self._setup_ui()
        self._load_html()

    # ── Window setup ───────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle("📄 OCR Overlay Viewer")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Kích thước ban đầu: tối đa 85% màn hình, tối thiểu 400×300
        screen = QGuiApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            w = min(self._image.width  + 4,  int(sg.width()  * 0.85))
            h = min(self._image.height + 60, int(sg.height() * 0.85))
        else:
            w, h = 800, 650

        self.resize(max(w, 400), max(h, 350))
        self.setMinimumSize(350, 280)

        # Căn giữa màn hình
        if screen:
            sg = screen.availableGeometry()
            self.move(
                sg.center().x() - self.width() // 2,
                sg.center().y() - self.height() // 2,
            )

    # ── UI layout ─────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("central")
        central.setStyleSheet("""
            #central {
                background: #1a1a2e;
                border: 1px solid #3a3a5c;
                border-radius: 8px;
            }
        """)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Titlebar (draggable) ───────────────────────────────────────────
        titlebar = self._build_titlebar()
        root_layout.addWidget(titlebar)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #3a3a5c; max-height: 1px;")
        root_layout.addWidget(sep)

        # ── WebEngine view ─────────────────────────────────────────────────
        self._web = QWebEngineView()
        self._web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._web.page().setBackgroundColor(Qt.GlobalColor.transparent)
        root_layout.addWidget(self._web, stretch=1)

        # ── Status bar ─────────────────────────────────────────────────────
        self._lbl_status = QLabel(
            f"  📊 {len(ocr_result.word_boxes)} dòng | "
            f"{len(ocr_result.plain_text)} ký tự  "
            if (ocr_result := self._ocr_result) else "  Sẵn sàng  "
        )
        self._lbl_status.setStyleSheet(
            "color: #8888aa; font-size: 11px; padding: 3px 8px; background: #12122a;"
        )
        root_layout.addWidget(self._lbl_status)

        # ── Shortcuts ──────────────────────────────────────────────────────
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Ctrl+Plus"),  self).activated.connect(self._zoom_in)
        QShortcut(QKeySequence("Ctrl+Minus"), self).activated.connect(self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"),     self).activated.connect(self._zoom_reset)

    def _build_titlebar(self) -> QWidget:
        """Thanh tiêu đề có thể kéo được."""
        bar = QWidget()
        bar.setFixedHeight(42)
        bar.setObjectName("titlebar")
        bar.setStyleSheet("""
            #titlebar {
                background: #16213e;
                border-radius: 8px 8px 0 0;
            }
            QPushButton {
                background: transparent;
                border: 1px solid #3a3a6e;
                border-radius: 5px;
                color: #ccccee;
                font-size: 13px;
                padding: 3px 10px;
                min-width: 28px;
            }
            QPushButton:hover  { background: #2a2a5e; }
            QPushButton:pressed { background: #1a1a4e; }
            #btn-close:hover   { background: #a02020; border-color: #cc3030; }
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(6)

        # Icon + title
        lbl_title = QLabel("📄  OCR Overlay Viewer")
        lbl_title.setStyleSheet("color: #ccccee; font-size: 13px; font-weight: 600;")
        layout.addWidget(lbl_title)
        layout.addStretch()

        # Zoom controls
        btn_zoom_out = QPushButton("🔍−")
        btn_zoom_out.setToolTip("Thu nhỏ (Ctrl+−)")
        btn_zoom_out.clicked.connect(self._zoom_out)
        layout.addWidget(btn_zoom_out)

        btn_zoom_in = QPushButton("🔍+")
        btn_zoom_in.setToolTip("Phóng to (Ctrl++)")
        btn_zoom_in.clicked.connect(self._zoom_in)
        layout.addWidget(btn_zoom_in)

        btn_zoom_reset = QPushButton("1:1")
        btn_zoom_reset.setToolTip("Kích thước gốc (Ctrl+0)")
        btn_zoom_reset.clicked.connect(self._zoom_reset)
        layout.addWidget(btn_zoom_reset)

        # Copy all
        btn_copy = QPushButton("📋 Copy tất cả")
        btn_copy.setToolTip("Copy toàn bộ text nhận dạng được")
        btn_copy.clicked.connect(self._copy_all)
        layout.addWidget(btn_copy)

        # Close
        btn_close = QPushButton("✕")
        btn_close.setObjectName("btn-close")
        btn_close.setToolTip("Đóng (Ctrl+W / Esc)")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

        # Cho phép kéo cửa sổ qua titlebar
        bar.mousePressEvent   = self._on_drag_start
        bar.mouseMoveEvent    = self._on_drag_move
        bar.mouseReleaseEvent = self._on_drag_end

        return bar

    # ── HTML generation ────────────────────────────────────────────────────────

    def _load_html(self) -> None:
        """Sinh HTML và load vào QWebEngineView."""
        ocr  = self._ocr_result
        img  = self._image

        img_b64   = _image_to_base64(img)
        text_spans = _build_text_spans(ocr.word_boxes, img.width, img.height)

        html = _HTML_TEMPLATE.format(
            img_width  = img.width,
            img_height = img.height,
            img_b64    = img_b64,
            text_spans = text_spans,
        )
        self._web.setHtml(html, QUrl("about:blank"))

    # ── Actions ────────────────────────────────────────────────────────────────

    def _zoom_in(self) -> None:
        self._zoom = min(self._zoom + 0.25, 4.0)
        self._web.setZoomFactor(self._zoom)

    def _zoom_out(self) -> None:
        self._zoom = max(self._zoom - 0.25, 0.25)
        self._web.setZoomFactor(self._zoom)

    def _zoom_reset(self) -> None:
        self._zoom = 1.0
        self._web.setZoomFactor(1.0)

    def _copy_all(self) -> None:
        """Copy toàn bộ text nhận dạng vào clipboard."""
        text = self._ocr_result.plain_text
        if text:
            QGuiApplication.clipboard().setText(text)
            self._lbl_status.setText(
                f"  ✅ Đã copy {len(text)} ký tự vào clipboard!  "
            )

    # ── Draggable window via titlebar ─────────────────────────────────────────

    def _on_drag_start(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def _on_drag_move(self, event) -> None:
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def _on_drag_end(self, event) -> None:
        self._drag_pos = None
