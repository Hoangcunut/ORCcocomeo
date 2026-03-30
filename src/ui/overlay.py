"""
overlay.py
----------
Overlay che phủ toàn màn hình, cung cấp trải nghiệm chụp như Windows 11 Snipping Tool.
- Có Toolbar chọn chế độ (Rectangle, Freeform, Window, Fullscreen) nổi lên trên cùng.
- Khi người dùng chọn và nhả chuột, sẽ tính toán vùng chọn, cắt QPixmap, áp Mask (nếu có vẽ tự do)
  và trả về PIL Image thông qua event `capture_taken`.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Optional

from PIL import Image
from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QImage
)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QToolButton,
    QWidget,
)

from src.capture_engine import CaptureMode
from src.config import OVERLAY_COLOR, SELECTION_BORDER_COLOR

# ─── Hàm lấy danh sách cửa sổ (Tương thích Windows) ──────────────────────────────────
def get_window_rects() -> list[QRect]:
    rects = []
    try:
        user32 = ctypes.windll.user32
        def callback(hwnd, extra):
            if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                # Bỏ qua các cửa sổ rác (không tên hoặc quá bé)
                # Chú ý: Một số app (Spotify, Slack) có thể giấu tên cửa sổ, nhưng ta cứ lọc trước cho sạch
                if length > 0 or user32.GetWindowLongW(hwnd, -20) & 0x40000: # WS_EX_APPWINDOW
                    rect = ctypes.wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    # Nếu kích cỡ đáng kể thì thêm vào list
                    if w > 50 and h > 50:
                        rects.append(QRect(rect.left, rect.top, w, h))
            return True
        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        user32.EnumWindows(CMPFUNC(callback), 0)
    except Exception:
        pass
    return rects

# ─── OverlayToolbar ────────────────────────────────────────────────────────
class OverlayToolbar(QWidget):
    """Toolbar chọn Mode Chụp."""
    mode_changed = pyqtSignal(object) # CaptureMode
    cancelled = pyqtSignal()
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(45)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(32, 32, 32, 240);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 50);
            }
            QToolButton {
                background: transparent;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 15px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 40);
            }
            QToolButton:checked {
                background-color: #0078D4;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)
        
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        
        modes = [
            ("▭", "Chụp Vùng Chữ Nhật", CaptureMode.RECTANGLE),
            ("✏", "Chụp Vẽ Tự Do", CaptureMode.FREEFORM),
            ("🪟", "Chụp Cửa Sổ Hover", CaptureMode.WINDOW),
            ("🖥️", "Chụp Toàn Màn Hình", CaptureMode.FULLSCREEN),
        ]
        
        self.mode_map = {}
        for icon, tooltip, mode in modes:
            btn = QToolButton()
            btn.setText(icon)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            self.btn_group.addButton(btn)
            layout.addWidget(btn)
            self.mode_map[btn] = mode
            btn.clicked.connect(lambda _, b=btn: self.mode_changed.emit(self.mode_map[b]))
            
        # Nút đóng
        btn_close = QToolButton()
        btn_close.setText("✕")
        btn_close.setToolTip("Huỷ chụp (Nhấn phím Esc)")
        btn_close.clicked.connect(self.cancelled.emit)
        btn_close.setStyleSheet("QToolButton:hover { background-color: #C62828; }")
        layout.addWidget(btn_close)
        
        # Mặc định chọn Rectangle
        self.btn_group.buttons()[0].setChecked(True)

# ─── ScreenOverlay ──────────────────────────────────────────────────────────
class ScreenOverlay(QWidget):
    """Màn hình Overlay khổng lồ bao phủ tất cả các màn hình ghép lại."""
    
    capture_taken = pyqtSignal(object, object) # (PIL.Image, CaptureMode)
    cancelled = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        
        # Georect tổng của tất cả màn hình ghép lại
        total_geometry = QRect()
        for screen in QGuiApplication.screens():
            total_geometry = total_geometry.united(screen.geometry())
        self.setGeometry(total_geometry)
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setMouseTracking(True)
        
        # Trạng thái
        self.mode = CaptureMode.RECTANGLE
        self._dragging = False
        self._start_pos: QPoint | None = None
        self._curr_pos: QPoint | None = None
        self._freeform_path = QPainterPath()
        
        self._background: QPixmap | None = None
        self._window_rects: list[QRect] = []
        self._hover_rect: QRect | None = None
        
        # Khởi tạo Toolbar
        self.toolbar = OverlayToolbar(self)
        self.toolbar.mode_changed.connect(self.set_mode)
        self.toolbar.cancelled.connect(self.cancel_capture)

    # ─── Public API ───
    def activate(self) -> None:
        """Kéo ScreenOverlay lên và chụp ảnh nền tĩnh, hiển thị UI."""
        self._capture_background()
        self._window_rects = get_window_rects()
        self._dragging = False
        self._start_pos = None
        self._curr_pos = None
        self._hover_rect = None
        self._freeform_path.clear()
        
        # Căn chỉnh Toolbar giữa đỉnh màn hình chính
        screen = QGuiApplication.primaryScreen()
        tb_w = 320
        tb_h = 45
        if screen:
            sc_geo = screen.geometry()
            x = sc_geo.left() - self.geometry().left() + (sc_geo.width() - tb_w) // 2
            y = sc_geo.top() - self.geometry().top() + 20
            self.toolbar.setGeometry(x, y, tb_w, tb_h)
            
        self.toolbar.show()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def set_mode(self, mode: CaptureMode) -> None:
        self.mode = mode
        self._dragging = False
        self._hover_rect = None
        self._freeform_path.clear()
        if mode == CaptureMode.FULLSCREEN:
            self._capture_fullscreen()
        self.update()
        
    def cancel_capture(self) -> None:
        self.hide()
        self.cancelled.emit()

    # ─── Capture Generators ───
    def _emit_result(self, pixmap: QPixmap, mode: CaptureMode) -> None:
        self.hide()
        # Chuyển đổi sang PIL Image định dạng RGBA (Có trong suốt)
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        # Bắt buộc phải sao chép bộ nhớ ra Python
        ptr = image.bits()
        ptr.setsize(image.sizeInBytes())
        pil_img = Image.frombytes("RGBA", (image.width(), image.height()), ptr)
        self.capture_taken.emit(pil_img, mode)

    def _capture_rect(self) -> None:
        if self._start_pos and self._curr_pos:
            rect = QRect(self._start_pos, self._curr_pos).normalized()
            if rect.width() > 10 and rect.height() > 10:
                cropped = self._background.copy(rect)
                self._emit_result(cropped, CaptureMode.RECTANGLE)
            else:
                self.cancel_capture()

    def _capture_window(self) -> None:
        if self._hover_rect:
            cropped = self._background.copy(self._hover_rect)
            self._emit_result(cropped, CaptureMode.WINDOW)

    def _capture_fullscreen(self) -> None:
        self._emit_result(self._background, CaptureMode.FULLSCREEN)

    def _capture_freeform(self) -> None:
        rect = self._freeform_path.boundingRect().toRect()
        if rect.width() < 10 or rect.height() < 10:
            return self.cancel_capture()
            
        cropped_bg = self._background.copy(rect)
        
        # Mask trắng/Alpha cắt viền
        mask = QPixmap(rect.size())
        mask.fill(Qt.GlobalColor.transparent)
        
        mpaint = QPainter(mask)
        mpaint.setRenderHint(QPainter.RenderHint.Antialiasing)
        path_trans = self._freeform_path.translated(-rect.topLeft())
        mpaint.fillPath(path_trans, QColor(255, 255, 255))
        mpaint.end()
        
        result = QPixmap(rect.size())
        result.fill(Qt.GlobalColor.transparent)
        
        rpaint = QPainter(result)
        rpaint.setRenderHint(QPainter.RenderHint.Antialiasing)
        rpaint.drawPixmap(0, 0, cropped_bg)
        rpaint.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        rpaint.drawPixmap(0, 0, mask)
        rpaint.end()
        
        self._emit_result(result, CaptureMode.FREEFORM)

    # ─── Event Vẽ ───
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self._background:
            painter.drawPixmap(0, 0, self._background)

        # Lớp overlay đen mờ
        painter.fillRect(self.rect(), QColor(*OVERLAY_COLOR))

        # Hiển thị các vùng chui khỏi bóng mờ
        if self.mode == CaptureMode.RECTANGLE and self._dragging and self._start_pos and self._curr_pos:
            rect = QRect(self._start_pos, self._curr_pos).normalized()
            if self._background:
                painter.drawPixmap(rect, self._background, rect)
            pen = QPen(QColor(SELECTION_BORDER_COLOR), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            self._draw_hint(painter, rect)

        elif self.mode == CaptureMode.WINDOW and self._hover_rect:
            if self._background:
                painter.drawPixmap(self._hover_rect, self._background, self._hover_rect)
            painter.setPen(QPen(QColor("#00A0FF"), 3, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._hover_rect)
            self._draw_hint(painter, self._hover_rect)

        elif self.mode == CaptureMode.FREEFORM and self._dragging:
            # Xoá vùng bóng mờ bên trong đa giác lasso
            painter.save()
            painter.setClipPath(self._freeform_path)
            if self._background:
                painter.drawPixmap(0, 0, self._background)
            painter.restore()

            # Vẽ đường viền kẻ đứt quanh Lasso
            painter.setPen(QPen(QColor(SELECTION_BORDER_COLOR), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._freeform_path)

    def _draw_hint(self, painter: QPainter, rect: QRect) -> None:
        info_text = f"{rect.width()} × {rect.height()}"
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        text_x = rect.left() + 4
        text_y = rect.top() - 6
        if text_y < 20: text_y = rect.bottom() + 16
        painter.drawText(text_x, text_y, info_text)

    # ─── Event Tương Tác ───
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.pos()
            self._curr_pos = event.pos()
            self._dragging = True
            
            if self.mode == CaptureMode.WINDOW:
                if self._hover_rect:
                    self._capture_window()
            elif self.mode == CaptureMode.FREEFORM:
                self._freeform_path.clear()
                self._freeform_path.moveTo(event.pos())
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.mode == CaptureMode.WINDOW and not self._dragging:
            global_pos = self.mapToGlobal(event.pos())
            self._hover_rect = None
            # Quét ngược từ trên xuống (Z-order)
            for rect in self._window_rects:
                if rect.contains(global_pos):
                    # Dịch toạ độ Absolute Global -> toạ độ Local widget Overlay
                    offset = self.geometry().topLeft()
                    self._hover_rect = QRect(rect.left() - offset.x(), rect.top() - offset.y(), rect.width(), rect.height())
                    break
            self.update()
        elif self._dragging:
            self._curr_pos = event.pos()
            if self.mode == CaptureMode.FREEFORM:
                self._freeform_path.lineTo(event.pos())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            if self.mode == CaptureMode.RECTANGLE:
                self._capture_rect()
            elif self.mode == CaptureMode.FREEFORM:
                self._freeform_path.lineTo(self._start_pos) # Đóng kín hình
                self._capture_freeform()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_capture()
            
    # ─── Core Screenshot ───
    def _capture_background(self) -> None:
        total_rect = self.geometry()
        pixmap = QPixmap(total_rect.size())
        pixmap.fill(QColor(0, 0, 0))
        painter = QPainter(pixmap)
        
        # Ghép ảnh từ các màn hình QGuiApplication.screens()
        for screen in QGuiApplication.screens():
            # GrabWindow(0) lấy cả màn hình kể cả taskbar
            screen_pixmap = screen.grabWindow(0)
            screen_geo = screen.geometry()
            offset_x = screen_geo.left() - total_rect.left()
            offset_y = screen_geo.top() - total_rect.top()
            painter.drawPixmap(offset_x, offset_y, screen_pixmap)
        painter.end()
        self._background = pixmap
