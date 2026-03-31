"""
editor_window.py  (Giai đoạn 2 — full rewrite)
------------------------------------------------
Cửa sổ chỉnh sửa ảnh với đầy đủ công cụ vẽ + OCR panel tích hợp.

Wave 3 — Wiring OCROverlayWindow:
  - Thêm engine VietOCR vào radio buttons
  - Thêm nút "📄 Xem Overlay" (chỉ hiện sau khi VietOCR xong)
  - Kết nối overlay_ready signal → OCROverlayWindow

Layout:
  ┌─────────────────────────────────────────────────────┐
  │  [Action bar: Capture mới | Undo | Redo | Save | Copy] │
  ├──────┬──────────────────────────────────┬────────────┤
  │ Tool │                                  │  OCR Panel  │
  │ Pal- │       Canvas (vùng vẽ)           │  (ẩn/hiện) │
  │ ette │                                  │            │
  └──────┴──────────────────────────────────┴────────────┘

Công cụ (Giai đoạn 2):
  - Select / Pan
  - Highlight Pen (vàng, alpha 40%)
  - Pen tự do (màu + nét tuỳ chọn)
  - Eraser
  - Redact (blackout vùng chữ nhật)
  - Crop

Undo / Redo:
  Lưu QPixmap snapshot sau mỗi stroke, tối đa 30 bước.

OCR Panel (phải):
  - Combobox chọn chế độ (Markdown / Free / Standard)
  - Nút "Trích xuất văn bản"
  - Text edit hiển thị kết quả stream
  - Nút "Copy kết quả"
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from src.capture_engine import CaptureResult
from src.config import APP_NAME, OCR_LANGUAGES, OCR_DEFAULT_LANG_INDEX
from src.ocr_engine import EnginePreference, OcrEngine
from src.umi_ocr_manager import UmiOcrManager

# OCROverlayWindow — import lazy để tránh import PyQtWebEngine khi không cần
_overlay_window_cls = None

def _get_overlay_cls():
    global _overlay_window_cls
    if _overlay_window_cls is None:
        from src.ui.ocr_overlay_window import OCROverlayWindow
        _overlay_window_cls = OCROverlayWindow
    return _overlay_window_cls

# ─── Hằng số ─────────────────────────────────────────────────────────────────

MAX_UNDO = 30        # Tối đa bao nhiêu bước undo
CANVAS_PADDING = 24  # Khoảng đệm xung quanh ảnh trong canvas

# ─── StyleSheet ──────────────────────────────────────────────────────────────

_STYLE = """
QDialog {
    background-color: #1A1A1E;
}

/* ── Action bar ── */
QWidget#action_bar {
    background-color: #252529;
    border-bottom: 1px solid #38383D;
}
QPushButton.action_btn {
    background-color: transparent;
    color: #D0D0D0;
    border: 1px solid #444;
    border-radius: 5px;
    padding: 5px 12px;
    font-size: 12px;
}
QPushButton.action_btn:hover {
    background-color: rgba(255,255,255,14);
    color: #FFFFFF;
    border-color: #666;
}
QPushButton.action_btn:disabled {
    color: #555;
    border-color: #333;
}
QPushButton#btn_save {
    background-color: #0078D4;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 5px 16px;
    font-size: 12px;
    font-weight: bold;
}
QPushButton#btn_save:hover { background-color: #1888E0; }

/* ── Tool palette ── */
QWidget#tool_palette {
    background-color: #1E1E22;
    border-right: 1px solid #38383D;
    min-width: 52px;
    max-width: 52px;
}
QToolButton#tool_btn {
    background: transparent;
    color: #C0C0C0;
    border: none;
    border-radius: 7px;
    font-size: 18px;
    padding: 4px;
    margin: 2px 4px;
    min-width: 38px;
    min-height: 38px;
}
QToolButton#tool_btn:hover {
    background-color: rgba(255,255,255,14);
    color: #FFFFFF;
}
QToolButton#tool_btn:checked {
    background-color: #0078D4;
    color: #FFFFFF;
}

/* ── Color swatch ── */
QPushButton#color_btn {
    border: 2px solid #555;
    border-radius: 5px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    margin: 2px 11px;
}
QPushButton#color_btn:hover { border-color: #AAA; }

/* ── Canvas area ── */
QScrollArea#canvas_scroll {
    background-color: #111114;
    border: none;
}

/* ── OCR Panel ── */
QWidget#ocr_panel {
    background-color: #1E1E22;
    border-left: 1px solid #38383D;
    min-width: 280px;
    max-width: 360px;
}
QLabel#ocr_title {
    color: #E0E0E0;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 12px 6px 12px;
}
QComboBox#ocr_mode_combo {
    background: rgba(255,255,255,10);
    color: #E0E0E0;
    border: 1px solid #555;
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 12px;
    margin: 0 10px;
}
QComboBox#ocr_mode_combo QAbstractItemView {
    background: #2A2A2E;
    color: #E0E0E0;
    selection-background-color: #0078D4;
}
QPushButton#btn_ocr {
    background-color: #0078D4;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 7px 0;
    font-size: 12px;
    font-weight: bold;
    margin: 8px 10px 4px 10px;
}
QPushButton#btn_ocr:hover { background-color: #1888E0; }
QPushButton#btn_ocr:disabled {
    background-color: #333;
    color: #666;
}
QPushButton#btn_cancel_ocr {
    background-color: #6B2D2D;
    color: #FFAAAA;
    border: none;
    border-radius: 5px;
    padding: 6px 0;
    font-size: 12px;
    margin: 0 10px 6px 10px;
}
QPushButton#btn_cancel_ocr:hover { background-color: #8B3D3D; }
QTextEdit#ocr_result {
    background-color: #141418;
    color: #E0E0E0;
    border: 1px solid #333;
    border-radius: 5px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 6px;
    margin: 0 10px;
}
QLabel#ocr_status {
    color: #888;
    font-size: 11px;
    padding: 4px 12px;
}
QPushButton#btn_copy_ocr {
    background: rgba(255,255,255,8);
    color: #C0C0C0;
    border: 1px solid #444;
    border-radius: 5px;
    padding: 5px 0;
    font-size: 11px;
    margin: 4px 10px;
}
QPushButton#btn_copy_ocr:hover {
    background: rgba(255,255,255,15);
    color: #FFFFFF;
}

/* ── Status bar ── */
QStatusBar {
    background-color: #1E1E22;
    color: #888;
    font-size: 11px;
    border-top: 1px solid #333;
}

/* ── Slider nét vẽ ── */
QSlider::groove:horizontal {
    background: #333;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #0078D4;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}
QLabel { color: #AAAAAA; font-size: 11px; }
"""


# ─── DrawingCanvas ────────────────────────────────────────────────────────────

class DrawingCanvas(QWidget):
    """
    Widget vẽ — hiển thị ảnh + layer vẽ đè lên trên.
    
    Hỗ trợ các tool: HIGHLIGHT, PEN, ERASER, REDACT, CROP, SELECT.
    Undo/Redo bằng QPixmap snapshot stack.
    """

    # Signal phát khi canvas thay đổi (để enable nút Undo)
    history_changed = pyqtSignal(int, int)  # (undo_count, redo_count)
    status_update = pyqtSignal(str)

    # Tên các công cụ
    TOOL_SELECT    = "select"
    TOOL_HIGHLIGHT = "highlight"
    TOOL_PEN       = "pen"
    TOOL_ERASER    = "eraser"
    TOOL_REDACT    = "redact"
    TOOL_CROP      = "crop"

    def __init__(self, base_image: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # ── Ảnh gốc + layer vẽ ───────────────────────────────────────────────
        self._base: QPixmap = base_image.copy()         # Ảnh gốc, không thay đổi
        self._drawing_layer: QPixmap = QPixmap(base_image.size())
        self._drawing_layer.fill(QColor(0, 0, 0, 0))   # Trong suốt

        # ── Composite (base + drawing_layer) cho undo stack ──────────────────
        self._undo_stack: list[QPixmap] = []   # Trạng thái trước khi vẽ
        self._redo_stack: list[QPixmap] = []

        # ── Trạng thái công cụ ───────────────────────────────────────────────
        self._tool: str = self.TOOL_SELECT
        self._pen_color: QColor = QColor("#FF5252")
        self._pen_width: int = 3
        self._highlight_alpha: int = 80   # 0-255

        # ── Trạng thái kéo chuột ─────────────────────────────────────────────
        self._drawing: bool = False
        self._last_pos: Optional[QPoint] = None
        self._rect_start: Optional[QPoint] = None  # Cho REDACT và CROP
        self._rect_current: Optional[QPoint] = None

        # Thiết lập kích thước widget = kích thước ảnh + padding
        img_w = base_image.width()
        img_h = base_image.height()
        self.setMinimumSize(img_w + CANVAS_PADDING * 2, img_h + CANVAS_PADDING * 2)
        self.setMouseTracking(True)

    # ─── Getter / Setter công cụ ──────────────────────────────────────────────

    def set_tool(self, tool: str) -> None:
        self._tool = tool
        cursor_map = {
            self.TOOL_SELECT:    Qt.CursorShape.ArrowCursor,
            self.TOOL_HIGHLIGHT: Qt.CursorShape.CrossCursor,
            self.TOOL_PEN:       Qt.CursorShape.CrossCursor,
            self.TOOL_ERASER:    Qt.CursorShape.CrossCursor,
            self.TOOL_REDACT:    Qt.CursorShape.CrossCursor,
            self.TOOL_CROP:      Qt.CursorShape.CrossCursor,
        }
        self.setCursor(QCursor(cursor_map.get(tool, Qt.CursorShape.ArrowCursor)))

    def set_pen_color(self, color: QColor) -> None:
        self._pen_color = color

    def set_pen_width(self, width: int) -> None:
        self._pen_width = width

    def get_result_pixmap(self) -> QPixmap:
        """Trả về pixmap composite (base + drawing layer)."""
        return self._composite()

    # ─── Undo / Redo ─────────────────────────────────────────────────────────

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._drawing_layer.copy())
        self._drawing_layer = self._undo_stack.pop()
        self._emit_history()
        self.update()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._drawing_layer.copy())
        self._drawing_layer = self._redo_stack.pop()
        self._emit_history()
        self.update()

    def _push_undo(self) -> None:
        """Lưu trạng thái hiện tại vào undo stack trước khi vẽ."""
        self._undo_stack.append(self._drawing_layer.copy())
        self._redo_stack.clear()
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.pop(0)
        self._emit_history()

    def _emit_history(self) -> None:
        self.history_changed.emit(len(self._undo_stack), len(self._redo_stack))

    # ─── Paint ───────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Nền canvas tối
        painter.fillRect(self.rect(), QColor("#111114"))

        # Vùng ảnh (căn giữa với padding)
        img_rect = self._image_rect()

        # Vẽ ảnh gốc
        painter.drawPixmap(img_rect.topLeft(), self._base)

        # Vẽ drawing layer đè lên
        painter.drawPixmap(img_rect.topLeft(), self._drawing_layer)

        # Nếu đang kéo Redact / Crop → vẽ preview hình chữ nhật
        if (self._drawing
                and self._tool in (self.TOOL_REDACT, self.TOOL_CROP)
                and self._rect_start and self._rect_current):
            sel = QRect(
                self._rect_start - img_rect.topLeft(),
                self._rect_current - img_rect.topLeft(),
            ).normalized()
            # Chuyển về toạ độ widget
            sel = QRect(
                sel.topLeft() + img_rect.topLeft(),
                sel.size(),
            )
            if self._tool == self.TOOL_REDACT:
                painter.fillRect(sel, QColor(0, 0, 0, 160))
                pen = QPen(QColor("#FF5252"), 2, Qt.PenStyle.DashLine)
            else:  # CROP
                painter.fillRect(sel, QColor(0, 0, 0, 80))
                pen = QPen(QColor("#FFFFFF"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(sel)

        painter.end()

    # ─── Sự kiện chuột ───────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._to_image_coords(event.pos())
            if pos is None:
                return

            self._drawing = True
            self._push_undo()

            if self._tool in (self.TOOL_REDACT, self.TOOL_CROP):
                self._rect_start = event.pos()
                self._rect_current = event.pos()
            else:
                self._last_pos = pos
                # Chấm đầu tiên
                if self._tool not in (self.TOOL_SELECT,):
                    self._draw_stroke(pos, pos)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        pos = self._to_image_coords(event.pos())
        # Cập nhật status bar toạ độ
        if pos:
            self.status_update.emit(f"X: {pos.x()}  Y: {pos.y()}")

        if not self._drawing or pos is None:
            return

        if self._tool in (self.TOOL_REDACT, self.TOOL_CROP):
            self._rect_current = event.pos()
            self.update()
        elif self._last_pos is not None and self._tool != self.TOOL_SELECT:
            self._draw_stroke(self._last_pos, pos)
            self._last_pos = pos
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False

            if self._tool == self.TOOL_REDACT and self._rect_start:
                img_rect = self._image_rect()
                start_img = self._rect_start - img_rect.topLeft()
                end_img = (self._rect_current or self._rect_start) - img_rect.topLeft()
                sel = QRect(start_img, end_img).normalized()
                self._apply_redact(sel)

            elif self._tool == self.TOOL_CROP and self._rect_start:
                img_rect = self._image_rect()
                start_img = self._rect_start - img_rect.topLeft()
                end_img = (self._rect_current or self._rect_start) - img_rect.topLeft()
                crop_rect = QRect(start_img, end_img).normalized()
                self._apply_crop(crop_rect)

            self._rect_start = None
            self._rect_current = None
            self._last_pos = None
            self.update()

    # ─── Logic vẽ ────────────────────────────────────────────────────────────

    def _draw_stroke(self, p1: QPoint, p2: QPoint) -> None:
        """Vẽ một đường từ p1 đến p2 lên drawing layer."""
        painter = QPainter(self._drawing_layer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._tool == self.TOOL_HIGHLIGHT:
            color = QColor(255, 230, 0, self._highlight_alpha)
            pen = QPen(color, max(self._pen_width * 4, 16), Qt.PenStyle.SolidLine)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(pen)

        elif self._tool == self.TOOL_PEN:
            pen = QPen(self._pen_color, self._pen_width, Qt.PenStyle.SolidLine)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

        elif self._tool == self.TOOL_ERASER:
            # Xóa bằng cách vẽ transparent
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            pen = QPen(QColor(0, 0, 0, 255), max(self._pen_width * 5, 20))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

        else:
            painter.end()
            return

        painter.drawLine(p1, p2)
        painter.end()

    def _apply_redact(self, rect: QRect) -> None:
        """Tô đen vùng chọn (redact — che thông tin nhạy cảm)."""
        if rect.width() < 2 or rect.height() < 2:
            return
        painter = QPainter(self._drawing_layer)
        painter.fillRect(rect, QColor(0, 0, 0, 255))
        painter.end()
        self.update()

    def _apply_crop(self, rect: QRect) -> None:
        """Crop ảnh theo vùng chọn — thay thế base image."""
        if rect.width() < 4 or rect.height() < 4:
            return
        # Clamp vào trong ảnh
        rect = rect.intersected(QRect(0, 0, self._base.width(), self._base.height()))
        cropped_base = self._base.copy(rect)
        cropped_layer = self._drawing_layer.copy(rect)

        self._base = cropped_base
        self._drawing_layer = QPixmap(cropped_base.size())
        self._drawing_layer.fill(QColor(0, 0, 0, 0))
        # Vẽ lại drawing layer đã crop
        painter = QPainter(self._drawing_layer)
        painter.drawPixmap(0, 0, cropped_layer)
        painter.end()

        # Cập nhật kích thước widget
        self.setMinimumSize(
            self._base.width() + CANVAS_PADDING * 2,
            self._base.height() + CANVAS_PADDING * 2,
        )
        self.update()

    # ─── Helper vị trí ───────────────────────────────────────────────────────

    def _image_rect(self) -> QRect:
        """Tính QRect vị trí ảnh trong widget (căn giữa với padding)."""
        return QRect(
            CANVAS_PADDING,
            CANVAS_PADDING,
            self._base.width(),
            self._base.height(),
        )

    def _to_image_coords(self, widget_pos: QPoint) -> Optional[QPoint]:
        """Chuyển toạ độ widget → toạ độ ảnh. None nếu ngoài vùng ảnh."""
        img_rect = self._image_rect()
        x = widget_pos.x() - img_rect.left()
        y = widget_pos.y() - img_rect.top()
        if 0 <= x <= self._base.width() and 0 <= y <= self._base.height():
            return QPoint(x, y)
        return None

    def _composite(self) -> QPixmap:
        """Gộp base + drawing layer thành một pixmap kết quả."""
        result = self._base.copy()
        painter = QPainter(result)
        painter.drawPixmap(0, 0, self._drawing_layer)
        painter.end()
        return result


# ─── EditorWindow ─────────────────────────────────────────────────────────────

class EditorWindow(QDialog):
    """
    Cửa sổ chỉnh sửa ảnh đầy đủ tính năng (Giai đoạn 2).
    """

    def __init__(self, result: CaptureResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._result = result
        self._pixmap = self._pil_to_pixmap(result)
        self._ocr_engine = OcrEngine(self)
        self._last_pil_image = None          # Lưu PIL image dùng cho overlay
        self._overlay_win = None             # Giữ reference tránh GC

        self.setWindowTitle(f"{APP_NAME} — Chỉnh sửa")
        self.setMinimumSize(1000, 620)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        self._build_ui()
        self._setup_shortcuts()
        self._connect_ocr_signals()

    # ─── Build UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_action_bar())

        # Khởi tạo status bar SỚM để _build_canvas_area() và _build_ocr_panel()
        # có thể tham chiếu self._status mà không bị AttributeError
        self._status = QStatusBar()

        # Body: tool palette | canvas | ocr panel
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        body.addWidget(self._build_tool_palette())
        body.addWidget(self._build_canvas_area(), stretch=1)
        self._ocr_panel_widget = self._build_ocr_panel()
        body.addWidget(self._ocr_panel_widget)

        body_widget = QWidget()
        body_widget.setLayout(body)
        root.addWidget(body_widget, stretch=1)

        # Thêm status bar vào layout (đã khởi tạo ở trên)
        root.addWidget(self._status)
        self._status.showMessage(
            "Ctrl+Scroll: zoom  |  H: Highlight  |  P: Pen  |  E: Eraser  |  R: Redact  |  C: Crop"
        )

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("action_bar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        def _mk_btn(text: str, tip: str, obj_name: str = "") -> QPushButton:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setProperty("class", "action_btn")
            if obj_name:
                b.setObjectName(obj_name)
            return b

        self._btn_undo = _mk_btn("↩  Undo", "Hoàn tác (Ctrl+Z)")
        self._btn_undo.setEnabled(False)
        self._btn_undo.clicked.connect(self._canvas.undo if hasattr(self, '_canvas') else lambda: None)
        layout.addWidget(self._btn_undo)

        self._btn_redo = _mk_btn("↪  Redo", "Làm lại (Ctrl+Y)")
        self._btn_redo.setEnabled(False)
        self._btn_redo.clicked.connect(self._canvas.redo if hasattr(self, '_canvas') else lambda: None)
        layout.addWidget(self._btn_redo)

        layout.addSpacing(8)

        btn_copy = _mk_btn("📋  Sao chép", "Copy ảnh vào clipboard (Ctrl+C)")
        btn_copy.clicked.connect(self._on_copy)
        layout.addWidget(btn_copy)

        btn_save = _mk_btn("💾  Lưu As...", "Lưu ảnh (Ctrl+S)", "btn_save")
        btn_save.clicked.connect(self._on_save_as)
        layout.addWidget(btn_save)

        layout.addStretch()

        # Nút hiện/ẩn OCR panel
        self._btn_ocr_toggle = _mk_btn("🔍  OCR Panel ▶", "Hiện/ẩn panel OCR")
        self._btn_ocr_toggle.clicked.connect(self._toggle_ocr_panel)
        layout.addWidget(self._btn_ocr_toggle)

        return bar

    def _build_tool_palette(self) -> QWidget:
        palette = QWidget()
        palette.setObjectName("tool_palette")
        layout = QVBoxLayout(palette)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        tools = [
            (DrawingCanvas.TOOL_SELECT,    "⊹",  "Di chuyển / Pan"),
            (DrawingCanvas.TOOL_HIGHLIGHT, "🖊",  "Bút highlight vàng"),
            (DrawingCanvas.TOOL_PEN,       "✏",  "Bút vẽ tự do"),
            (DrawingCanvas.TOOL_ERASER,    "⌫",  "Tẩy"),
            (DrawingCanvas.TOOL_REDACT,    "■",  "Che/redact (hộp đen)"),
            (DrawingCanvas.TOOL_CROP,      "⛶",  "Crop ảnh"),
        ]

        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        self._tool_btns: dict[str, QToolButton] = {}

        for tool_id, icon, tip in tools:
            btn = QToolButton()
            btn.setObjectName("tool_btn")
            btn.setText(icon)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setFixedSize(42, 42)
            btn.clicked.connect(lambda _, t=tool_id: self._canvas.set_tool(t))
            self._tool_group.addButton(btn)
            self._tool_btns[tool_id] = btn
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Mặc định: SELECT
        self._tool_btns[DrawingCanvas.TOOL_SELECT].setChecked(True)

        layout.addSpacing(10)

        # ── Màu bút ──────────────────────────────────────────────────────────
        self._btn_color = QPushButton()
        self._btn_color.setObjectName("color_btn")
        self._btn_color.setToolTip("Chọn màu bút")
        self._btn_color.setStyleSheet(
            "QPushButton#color_btn { background-color: #FF5252; }"
        )
        self._btn_color.clicked.connect(self._pick_color)
        layout.addWidget(self._btn_color, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ── Cỡ nét ───────────────────────────────────────────────────────────
        lbl_w = QLabel("Nét")
        lbl_w.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(lbl_w)

        self._slider_width = QSlider(Qt.Orientation.Vertical)
        self._slider_width.setRange(1, 20)
        self._slider_width.setValue(3)
        self._slider_width.setFixedHeight(60)
        # Lưu ý: kết nối với _canvas được thực hiện trong _build_canvas_area()
        # vì _canvas chưa tồn tại ở thời điểm này
        layout.addWidget(self._slider_width, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()
        return palette

    def _build_canvas_area(self) -> QScrollArea:
        # Khởi tạo canvas
        self._canvas = DrawingCanvas(self._pixmap)
        self._canvas.history_changed.connect(self._on_history_changed)
        self._canvas.status_update.connect(self._status.showMessage)

        # Sau khi canvas được tạo, kết nối lại Undo/Redo buttons
        self._btn_undo.clicked.disconnect()
        self._btn_redo.clicked.disconnect()
        self._btn_undo.clicked.connect(self._canvas.undo)
        self._btn_redo.clicked.connect(self._canvas.redo)

        # Cũng kết nối slider với canvas
        self._slider_width.valueChanged.connect(self._canvas.set_pen_width)

        scroll = QScrollArea()
        scroll.setObjectName("canvas_scroll")
        scroll.setWidget(self._canvas)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return scroll

    def _build_ocr_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ocr_panel")
        panel.hide()  # Ẩn mặc định

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)

        # ── Tiêu đề ────────────────────────────────────────────────────
        lbl_title = QLabel("🔍  Nhận diện văn bản (OCR)")
        lbl_title.setObjectName("ocr_title")
        layout.addWidget(lbl_title)

        # ── Engine status badge ────────────────────────────────────────────
        self._lbl_engine_status = QLabel()
        self._lbl_engine_status.setObjectName("ocr_status")
        self._lbl_engine_status.setWordWrap(True)
        self._lbl_engine_status.setStyleSheet(
            "QLabel { color: #AAAAAA; font-size: 11px; padding: 2px 12px; }"
        )
        layout.addWidget(self._lbl_engine_status)
        QTimer.singleShot(500, self._refresh_engine_status)  # Kiểm tra sau khi UI hiện

        # ── Engine selector ─────────────────────────────────────────────
        from PyQt6.QtWidgets import QRadioButton, QGroupBox
        engine_group = QGroupBox("Engine")
        engine_group.setStyleSheet(
            "QGroupBox { color: #CCCCCC; font-size: 11px; border: 1px solid #444;"
            " border-radius: 5px; margin: 4px 10px; padding-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
            "QRadioButton { color: #D0D0D0; font-size: 12px; padding: 2px 4px; }"
            "QRadioButton::indicator { width: 14px; height: 14px; }"
        )
        eg_layout = QVBoxLayout(engine_group)
        eg_layout.setContentsMargins(8, 4, 8, 6)
        eg_layout.setSpacing(2)

        self._rb_auto    = QRadioButton("⚡  Auto (Umi → Tesseract fallback)")
        self._rb_umi     = QRadioButton("🌐  Chỉ Umi-OCR")
        self._rb_tess    = QRadioButton("🔒  Chỉ Tesseract (bảo mật tối đa)")
        self._rb_vietocr = QRadioButton("🇻🇳  VietOCR (Tiếng Việt, có overlay)")
        self._rb_tess.setChecked(True)  # Mặc định Tesseract

        for rb in (self._rb_auto, self._rb_umi, self._rb_tess, self._rb_vietocr):
            eg_layout.addWidget(rb)

        # Ẩn/hiện nút Overlay theo lựa chọn engine
        self._rb_vietocr.toggled.connect(self._on_vietocr_toggled)

        layout.addWidget(engine_group)

        # ── Ngôn ngữ ────────────────────────────────────────────────────
        lbl_lang = QLabel("🌐 Ngôn ngữ:")
        lbl_lang.setStyleSheet("color: #C8C8C8; font-size: 12px; padding: 0 12px;")
        layout.addWidget(lbl_lang)

        self._combo_lang = QComboBox()
        self._combo_lang.setObjectName("ocr_mode_combo")
        for i, lang_cfg in enumerate(OCR_LANGUAGES):
            self._combo_lang.addItem(lang_cfg["label"], userData=i)
        self._combo_lang.setCurrentIndex(OCR_DEFAULT_LANG_INDEX)
        layout.addWidget(self._combo_lang)

        # ── Tiếng Việt không dấu ──────────────────────────────────────────
        layout.addSpacing(4)
        self._cb_remove_accent = QCheckBox("🔤 Loại bỏ dấu Tiếng Việt")
        self._cb_remove_accent.setStyleSheet(
            "QCheckBox { color: #C8C8C8; font-size: 12px; padding: 0 12px; margin-top: 2px; margin-bottom: 2px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        self._cb_remove_accent.setToolTip("Chuẩn hoá Tiếng Việt sang chữ cái Latin không dấu để lấy ASCII gốc (Ví dụ: Ảo -> Ao)")
        layout.addWidget(self._cb_remove_accent)

        # ── Nút Trích xuất ────────────────────────────────────────────────
        self._btn_ocr = QPushButton("🧠  Trích xuất văn bản")
        self._btn_ocr.setObjectName("btn_ocr")
        self._btn_ocr.clicked.connect(self._start_ocr)
        layout.addWidget(self._btn_ocr)

        # Nút Xem Overlay (chỉ hiện khi VietOCR xong)
        self._btn_overlay = QPushButton("📄  Xem Overlay (bôi đen / copy)")
        self._btn_overlay.setObjectName("btn_overlay")
        self._btn_overlay.setStyleSheet(
            "QPushButton#btn_overlay {"
            "  background-color: #1a5c3a; color: #aaffcc;"
            "  border: 1px solid #2a8a5a; border-radius: 5px;"
            "  padding: 6px 0; font-size: 12px; margin: 0 10px 4px 10px;"
            "}"
            "QPushButton#btn_overlay:hover { background-color: #226644; }"
        )
        self._btn_overlay.clicked.connect(self._open_overlay_window)
        self._btn_overlay.hide()   # Ẩn cho đến khi VietOCR xong
        layout.addWidget(self._btn_overlay)

        # Nút Hủy
        self._btn_cancel_ocr = QPushButton("⏹  Dừng lại")
        self._btn_cancel_ocr.setObjectName("btn_cancel_ocr")
        self._btn_cancel_ocr.clicked.connect(self._ocr_engine.cancel)
        self._btn_cancel_ocr.hide()
        layout.addWidget(self._btn_cancel_ocr)

        # Status OCR
        self._lbl_ocr_status = QLabel("Chưa nhận diện")
        self._lbl_ocr_status.setObjectName("ocr_status")
        self._lbl_ocr_status.setWordWrap(True)
        layout.addWidget(self._lbl_ocr_status)

        # ── Kết quả OCR ────────────────────────────────────────────────
        self._txt_ocr = QTextEdit()
        self._txt_ocr.setObjectName("ocr_result")
        self._txt_ocr.setPlaceholderText(
            "Kết quả OCR sẽ hiện ở đây...\n\n"
            "Có thể chỉnh sửa kết quả trước khi copy."
        )
        self._txt_ocr.setReadOnly(False)
        layout.addWidget(self._txt_ocr, stretch=1)

        # Nút Copy kết quả
        btn_copy_ocr = QPushButton("📋  Copy kết quả")
        btn_copy_ocr.setObjectName("btn_copy_ocr")
        btn_copy_ocr.clicked.connect(self._copy_ocr_result)
        layout.addWidget(btn_copy_ocr)

        return panel

    # ─── Shortcuts ───────────────────────────────────────────────────────────

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._canvas.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self._canvas.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(self._canvas.redo)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self._on_copy)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_as)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)

        # Phím tắt chọn công cụ nhanh
        QShortcut(QKeySequence("H"), self).activated.connect(
            lambda: self._select_tool(DrawingCanvas.TOOL_HIGHLIGHT))
        QShortcut(QKeySequence("P"), self).activated.connect(
            lambda: self._select_tool(DrawingCanvas.TOOL_PEN))
        QShortcut(QKeySequence("E"), self).activated.connect(
            lambda: self._select_tool(DrawingCanvas.TOOL_ERASER))
        QShortcut(QKeySequence("R"), self).activated.connect(
            lambda: self._select_tool(DrawingCanvas.TOOL_REDACT))
        QShortcut(QKeySequence("C"), self).activated.connect(
            lambda: self._select_tool(DrawingCanvas.TOOL_CROP))

    def _select_tool(self, tool: str) -> None:
        self._canvas.set_tool(tool)
        if tool in self._tool_btns:
            self._tool_btns[tool].setChecked(True)

    # ─── OCR Signals ────────────────────────────────────────────────────────

    def _connect_ocr_signals(self) -> None:
        self._ocr_engine.ocr_finished.connect(self._on_ocr_finished)
        self._ocr_engine.ocr_failed.connect(self._on_ocr_failed)
        self._ocr_engine.status_changed.connect(
            lambda s: self._lbl_ocr_status.setText(s)
        )
        self._ocr_engine.is_running.connect(self._on_ocr_running)
        self._ocr_engine.engine_used.connect(self._on_engine_used)
        self._ocr_engine.overlay_ready.connect(self._on_overlay_ready)

    def closeEvent(self, event):
        """Đóng cửa sổ Editor chỉ ẩn, không thoát app."""
        # Hủy OCR đang chạy nếu có
        if self._ocr_engine.running:
            self._ocr_engine.cancel()
        event.ignore()
        self.hide()

    def _refresh_engine_status(self) -> None:
        """Cập nhật badge trạng thái engine khi mở OCR panel."""
        status = self._ocr_engine.check_engines()
        parts = []
        if status["umi_available"]:
            if status["umi_ready"]:
                parts.append("✅ Umi-OCR đang chạy")
            else:
                parts.append("⏳ Umi-OCR chưa chạy (sẽ tự khởi động)")
            self._rb_umi.setEnabled(True)
        else:
            parts.append("⚠️ Umi-OCR chưa cài")
            self._rb_umi.setEnabled(False)

        if status["tess_available"]:
            parts.append("✅ Tesseract sẵn sàng")
            self._rb_tess.setEnabled(True)
        else:
            parts.append("⚠️ Tesseract chưa cài")
            self._rb_tess.setEnabled(False)

        # Nếu thiếu cả 2 thì không cho chạy Auto
        if not status["umi_available"] and not status["tess_available"]:
            self._rb_auto.setEnabled(False)
        else:
            self._rb_auto.setEnabled(True)

        # Chuyển focus nếu engine hiện tại bị disable
        if self._rb_umi.isChecked() and not self._rb_umi.isEnabled():
            self._rb_auto.setChecked(True)
        if self._rb_tess.isChecked() and not self._rb_tess.isEnabled():
            self._rb_auto.setChecked(True)
        if self._rb_auto.isChecked() and not self._rb_auto.isEnabled():
            self._rb_vietocr.setChecked(True)

        self._lbl_engine_status.setText("  |  ".join(parts))

    def _get_preference(self) -> EnginePreference:
        """Lấy engine preference từ radio buttons."""
        if self._rb_umi.isChecked():
            return EnginePreference.UMI_ONLY
        if self._rb_tess.isChecked():
            return EnginePreference.TESS_ONLY
        if self._rb_vietocr.isChecked():
            return EnginePreference.VIETOCR
        return EnginePreference.AUTO

    def _start_ocr(self) -> None:
        pref = self._get_preference()
        lang_index: int = self._combo_lang.currentData()  # type: ignore[assignment]

        from src.umi_ocr_manager import UmiOcrManager
        if pref in (EnginePreference.TESS_ONLY, EnginePreference.VIETOCR):
            UmiOcrManager.instance().stop()

        remove_accent: bool = self._cb_remove_accent.isChecked()
        self._txt_ocr.clear()
        self._btn_overlay.hide()   # Ẩn nút overlay khi bắt đầu OCR mới
        self._lbl_ocr_status.setText("🔄 Đang khởi tạo...")
        result_pixmap = self._canvas.get_result_pixmap()
        pil_image = self._pixmap_to_pil(result_pixmap)
        self._last_pil_image = pil_image   # Lưu lại để truyền vào overlay
        self._ocr_engine.start_ocr(pil_image, pref, lang_index, remove_accent)

    def _on_ocr_finished(self, text: str) -> None:
        self._txt_ocr.setPlainText(text)
        self._lbl_ocr_status.setText(f"✅ Hoàn thành — {len(text)} ký tự")
        self._status.showMessage("OCR hoàn thành!", 4000)

    def _on_engine_used(self, engine: str) -> None:
        names = {"umi": "Umi-OCR (PaddleOCR)", "tess": "Tesseract", "vietocr": "VietOCR"}
        self._status.showMessage(f"Engine sử dụng: {names.get(engine, engine)}", 3000)

    def _on_overlay_ready(self, ocr_result) -> None:
        """Nhận OcrOverlayResult từ VietOCR — hiện nút Xem Overlay."""
        self._pending_ocr_result = ocr_result
        self._btn_overlay.show()
        self._lbl_ocr_status.setText(
            f"✅ VietOCR xong — {len(ocr_result.word_boxes)} dòng | "
            f"Nhấn 📄 để xem overlay"
        )

    def _open_overlay_window(self) -> None:
        """Mở OCROverlayWindow với ảnh + kết quả VietOCR."""
        ocr_result = getattr(self, "_pending_ocr_result", None)
        pil_image  = self._last_pil_image
        if ocr_result is None or pil_image is None:
            return
        try:
            OCROverlayWindow = _get_overlay_cls()
        except Exception as exc:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Lỗi",
                f"Không mở được OCR Overlay:\n{exc}\n\n"
                "Hãy cài: pip install PyQt6-WebEngine"
            )
            return

        # Đóng cửa sổ cũ nếu đang mở
        if self._overlay_win is not None:
            try:
                self._overlay_win.close()
            except Exception:
                pass

        self._overlay_win = OCROverlayWindow(pil_image, ocr_result)
        self._overlay_win.show()

    def _on_vietocr_toggled(self, checked: bool) -> None:
        """Hiện/ẩn nút overlay tương ứng khi chọn VietOCR."""
        # Nếu bỏ chọn VietOCR thì ẩn nút overlay
        if not checked:
            self._btn_overlay.hide()

    def _on_ocr_failed(self, msg: str) -> None:
        self._lbl_ocr_status.setText("❌ Lỗi")
        self._txt_ocr.setPlainText(f"Lỗi OCR:\n\n{msg}")

    def _on_ocr_running(self, running: bool) -> None:
        self._btn_ocr.setEnabled(not running)
        self._btn_cancel_ocr.setVisible(running)

    def _copy_ocr_result(self) -> None:
        text = self._txt_ocr.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)
            self._status.showMessage("✅  Đã copy kết quả OCR!", 3000)

    def _toggle_ocr_panel(self) -> None:
        visible = not self._ocr_panel_widget.isVisible()
        self._ocr_panel_widget.setVisible(visible)
        self._btn_ocr_toggle.setText(
            "🔍  OCR Panel ◀" if visible else "🔍  OCR Panel ▶"
        )

    # ─── Hành động toolbar ───────────────────────────────────────────────────

    def _on_copy(self) -> None:
        QGuiApplication.clipboard().setPixmap(self._canvas.get_result_pixmap())
        self._status.showMessage("✅  Đã sao chép ảnh vào clipboard!", 3000)

    def _on_save_as(self) -> None:
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu ảnh",
            str(Path.home() / "screenshot.png"),
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;All Files (*)",
        )
        if filepath:
            try:
                pil = self._pixmap_to_pil(self._canvas.get_result_pixmap())
                pil.save(filepath)
                self._status.showMessage(f"✅  Đã lưu: {filepath}", 5000)
            except Exception as exc:
                QMessageBox.critical(self, "Lỗi lưu file", str(exc))

    def _pick_color(self) -> None:
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(self._canvas._pen_color, self, "Chọn màu bút")
        if color.isValid():
            self._canvas.set_pen_color(color)
            # Cập nhật màu nút
            self._btn_color.setStyleSheet(
                f"QPushButton#color_btn {{ background-color: {color.name()}; }}"
            )

    def _on_history_changed(self, undo_count: int, redo_count: int) -> None:
        self._btn_undo.setEnabled(undo_count > 0)
        self._btn_redo.setEnabled(redo_count > 0)

    # ─── Wheel event (zoom canvas) ───────────────────────────────────────────

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom canvas (scale widget)
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else 1 / 1.1
            new_w = int(self._canvas.width() * factor)
            new_h = int(self._canvas.height() * factor)
            self._canvas.resize(new_w, new_h)
        else:
            super().wheelEvent(event)

    # ─── Helper ──────────────────────────────────────────────────────────────

    @staticmethod
    def _pil_to_pixmap(result: CaptureResult) -> QPixmap:
        pil_rgb = result.image.convert("RGB")
        data = pil_rgb.tobytes("raw", "RGB")
        qimage = QImage(
            data, pil_rgb.width, pil_rgb.height,
            pil_rgb.width * 3, QImage.Format.Format_RGB888,
        )
        return QPixmap.fromImage(qimage)

    @staticmethod
    def _pixmap_to_pil(pixmap: QPixmap) -> "PIL.Image.Image":
        from PIL import Image
        qimage = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width, height = qimage.width(), qimage.height()
        ptr = qimage.bits()
        ptr.setsize(width * height * 3)
        return Image.frombuffer("RGB", (width, height), bytes(ptr))
