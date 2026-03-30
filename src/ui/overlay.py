"""
overlay.py
----------
Overlay mờ che phủ toàn màn hình — giao diện giống Snipping Tool Windows 11.

Khi kích hoạt:
  1. Phủ màu tối-mờ lên toàn bộ màn hình.
  2. Người dùng kéo chuột để chọn vùng chụp.
  3. Vùng được chọn hiện sáng lên (xoá overlay tại vùng đó).
  4. Thả chuột → phát signal `region_selected` với QRect đã chọn.
  5. Nhấn Escape → phát signal `cancelled`.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget

from src.config import (
    OVERLAY_COLOR,
    SELECTION_BORDER_COLOR,
    SELECTION_FILL_COLOR,
)


class ScreenOverlay(QWidget):
    """
    Widget phủ toàn màn hình để chọn vùng chụp.
    
    Signals:
        region_selected (QRect): Vùng đã chọn (pixel tuyệt đối).
        cancelled ():            Người dùng nhấn Escape.
    """

    region_selected = pyqtSignal(QRect)
    cancelled = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        # ── Tính toán vùng bao phủ tất cả màn hình ──────────────────────────
        total_geometry = QRect()
        for screen in QGuiApplication.screens():
            total_geometry = total_geometry.united(screen.geometry())

        self.setGeometry(total_geometry)

        # ── Cờ cửa sổ: không viền, luôn trên cùng, toàn màn hình ────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setMouseTracking(True)

        # ── Trạng thái kéo chuột ─────────────────────────────────────────────
        self._start: QPoint | None = None    # Điểm bắt đầu kéo
        self._current: QPoint | None = None  # Điểm hiện tại chuột
        self._dragging: bool = False

        # ── Chụp màn hình nền để hiển thị dưới overlay ───────────────────────
        self._background: QPixmap | None = None

    # ─── Public API ───────────────────────────────────────────────────────────

    def activate(self) -> None:
        """Hiện overlay và chuẩn bị nhận input chuột."""
        # Chụp màn hình nền trước khi overlay hiện ra
        self._capture_background()
        self._start = None
        self._current = None
        self._dragging = False
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    # ─── Sự kiện vẽ ─────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Vẽ ảnh nền (screenshot đã chụp trước) làm backdrop
        if self._background:
            painter.drawPixmap(0, 0, self._background)

        # Lớp phủ mờ toàn màn hình
        overlay_color = QColor(*OVERLAY_COLOR)
        painter.fillRect(self.rect(), overlay_color)

        # Nếu đang kéo → vẽ vùng chọn
        if self._dragging and self._start and self._current:
            sel_rect = self._selection_rect()

            # Xoá overlay trong vùng chọn (hiện sáng rõ vùng đó)
            if self._background:
                painter.drawPixmap(sel_rect, self._background, sel_rect)

            # Viền vùng chọn
            pen = QPen(QColor(SELECTION_BORDER_COLOR), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 0, 0, 0))  # Không fill (đã fill bằng nền)
            painter.drawRect(sel_rect)

            # Hiển thị kích thước
            info_text = f"{sel_rect.width()} × {sel_rect.height()}"
            painter.setPen(QColor("white"))
            # Vẽ ở góc trên trái vùng chọn (cách viền 4px)
            text_x = sel_rect.left() + 4
            text_y = sel_rect.top() - 6
            if text_y < 20:
                text_y = sel_rect.bottom() + 16
            painter.drawText(text_x, text_y, info_text)

    # ─── Sự kiện chuột ──────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.pos()
            self._current = event.pos()
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._current = event.pos()
            sel_rect = self._selection_rect()

            self.hide()

            # Chỉ phát signal nếu vùng chọn đủ lớn (tránh click nhầm)
            if sel_rect.width() > 4 and sel_rect.height() > 4:
                # Chuyển từ toạ độ widget → toạ độ màn hình tuyệt đối
                screen_rect = QRect(
                    self.mapToGlobal(sel_rect.topLeft()),
                    sel_rect.size(),
                )
                self.region_selected.emit(screen_rect)
            else:
                self.cancelled.emit()

    # ─── Sự kiện bàn phím ───────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._dragging = False
            self.hide()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)

    # ─── Helper ─────────────────────────────────────────────────────────────

    def _selection_rect(self) -> QRect:
        """Trả về QRect chuẩn hoá từ điểm bắt đầu và hiện tại."""
        if self._start is None or self._current is None:
            return QRect()
        return QRect(self._start, self._current).normalized()

    def _capture_background(self) -> None:
        """
        Chụp toàn bộ các màn hình làm nền hiển thị dưới overlay.
        Dùng QScreen.grabWindow thay vì mss để tránh conflict thread.
        """
        total_rect = self.geometry()
        pixmap = QPixmap(total_rect.size())
        pixmap.fill(QColor(0, 0, 0))  # Màu fallback

        painter = QPainter(pixmap)
        for screen in QGuiApplication.screens():
            screen_geo = screen.geometry()
            screen_pixmap = screen.grabWindow(0)
            # Tính offset trong pixmap tổng
            offset_x = screen_geo.left() - total_rect.left()
            offset_y = screen_geo.top() - total_rect.top()
            painter.drawPixmap(offset_x, offset_y, screen_pixmap)
        painter.end()

        self._background = pixmap
