"""
main.py
-------
Entry point cho Custom Snipping Tool.

Luồng chính:
  1. Khởi tạo QApplication
  2. Tạo System Tray Icon (khay thông báo Windows)
  3. Khởi động HotkeyManager (lắng nghe Alt+Shift+S toàn hệ thống)
  4. Khởi tạo Toolbar và ScreenOverlay (ẩn)
  5. Khi hotkey hoặc nút Capture bấm → hiện overlay (Rectangle) hoặc chụp ngay
  6. Sau khi chụp xong → mở EditorWindow hiển thị kết quả
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
    QSystemTrayIcon,
    QMenu,
)

from src.capture_engine import CaptureEngine, CaptureMode, CaptureResult
from src.config import APP_NAME, APP_VERSION, ASSETS_DIR, DEFAULT_HOTKEY_KEY, DEFAULT_HOTKEY_MODIFIERS
from src.hotkey_manager import HotkeyManager
from src.ui.editor_window import EditorWindow
from src.ui.overlay import ScreenOverlay
from src.ui.toolbar import SnippingToolbar


def _make_tray_icon() -> QPixmap:
    """
    Tạo icon tray đơn giản bằng code (không cần file ảnh).
    Giai đoạn 5 sẽ dùng file icon thật từ assets/.
    """
    from PyQt6.QtGui import QPainter, QPen
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Nền tròn xanh
    painter.setBrush(QColor("#0078D4"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, 30, 30)
    # Ký tự kéo góc
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "✂")
    painter.end()
    return pixmap


class SnippingApp:
    """
    Controller chính của ứng dụng.
    Quản lý vòng đời: Tray → Hotkey → Overlay → Capture → Editor.
    """

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._current_mode: CaptureMode = CaptureMode.RECTANGLE
        self._current_delay: int = 0
        self._editor: EditorWindow | None = None

        # ── Khởi tạo các thành phần ──────────────────────────────────────────
        self._engine = CaptureEngine()
        self._overlay = ScreenOverlay()
        self._toolbar = SnippingToolbar()
        self._hotkey = HotkeyManager(
            modifiers=DEFAULT_HOTKEY_MODIFIERS,
            key=DEFAULT_HOTKEY_KEY,
        )

        # ── Kết nối signals ───────────────────────────────────────────────────
        self._engine.capture_done.connect(self._on_capture_done)
        self._engine.capture_failed.connect(self._on_capture_failed)

        self._overlay.region_selected.connect(self._on_region_selected)
        self._overlay.cancelled.connect(self._on_capture_cancelled)

        self._toolbar.capture_requested.connect(self._on_capture_requested)
        self._toolbar.hide_to_tray.connect(self._hide_toolbar)
        self._toolbar.quit_requested.connect(self._quit)  # Nút X thoát app

        self._hotkey.activated.connect(self._on_hotkey_activated)

        # ── System Tray ───────────────────────────────────────────────────────
        self._tray = self._setup_tray()

        # ── Khởi động ─────────────────────────────────────────────────────────
        self._hotkey.start()
        self._toolbar.show()

    # ─── System Tray ─────────────────────────────────────────────────────────

    def _setup_tray(self) -> QSystemTrayIcon:
        """Thiết lập icon khay hệ thống với menu chuột phải."""
        icon = QIcon(_make_tray_icon())
        tray = QSystemTrayIcon(icon, self._app)
        tray.setToolTip(f"{APP_NAME} v{APP_VERSION}\nAlt+Shift+S để chụp")

        menu = QMenu()

        act_show = QAction("Hiện Toolbar", menu)
        act_show.triggered.connect(self._show_toolbar)
        menu.addAction(act_show)

        act_capture = QAction("Chụp ngay (Alt+Shift+S)", menu)
        act_capture.triggered.connect(self._on_hotkey_activated)
        menu.addAction(act_capture)

        menu.addSeparator()

        act_quit = QAction("Thoát", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        tray.setContextMenu(menu)
        # Double-click vào tray icon → hiện lại toolbar
        tray.activated.connect(
            lambda reason: self._show_toolbar()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
        tray.show()
        return tray

    # ─── Hiện / ẩn toolbar ───────────────────────────────────────────────────

    def _show_toolbar(self) -> None:
        self._toolbar.show()
        self._toolbar.raise_()
        self._toolbar.activateWindow()

    def _hide_toolbar(self) -> None:
        self._toolbar.hide()
        self._tray.showMessage(
            APP_NAME,
            "Thu nhỏ xuống khay. Double-click để mở lại.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    # ─── Xử lý hotkey / capture flow ─────────────────────────────────────────

    def _on_hotkey_activated(self) -> None:
        """Hotkey toàn hệ thống được kích hoạt → bắt đầu flow chụp mặc định (Rectangle)."""
        # Ẩn toolbar trước khi overlay xuất hiện
        self._toolbar.hide()
        # Một chút delay để toolbar kịp ẩn trước khi overlay render
        QTimer.singleShot(80, self._show_overlay)

    def _show_overlay(self) -> None:
        """Hiện overlay chọn vùng."""
        self._overlay.activate()

    def _on_capture_requested(self, mode: CaptureMode, delay: int) -> None:
        """Người dùng bấm nút Capture trên toolbar."""
        self._current_mode = mode
        self._current_delay = delay
        self._toolbar.set_capture_enabled(False)

        if mode == CaptureMode.RECTANGLE or mode == CaptureMode.FREEFORM:
            # Ẩn toolbar → hiện overlay
            self._toolbar.hide()
            QTimer.singleShot(80, self._show_overlay)
        elif mode == CaptureMode.FULLSCREEN:
            # Ẩn toolbar → chụp sau delay
            self._toolbar.hide()
            QTimer.singleShot(100 + delay * 1000, self._capture_fullscreen)
        elif mode == CaptureMode.WINDOW:
            # Placeholder: chụp fullscreen
            self._toolbar.hide()
            QTimer.singleShot(100 + delay * 1000, self._capture_fullscreen)

    def _capture_fullscreen(self) -> None:
        """Chụp toàn màn hình (không cần overlay)."""
        self._engine.capture_fullscreen(delay=0)  # delay đã xử lý ở QTimer

    def _on_region_selected(self, region: QRect) -> None:
        """Người dùng đã chọn xong vùng trên overlay."""
        # Chụp vùng sau delay (đã được người dùng đặt trên toolbar)
        QTimer.singleShot(
            self._current_delay * 1000,
            lambda: self._engine.capture_rectangle(region, delay=0),
        )

    def _on_capture_done(self, result: CaptureResult) -> None:
        """Ảnh đã chụp xong → mở cửa sổ chỉnh sửa."""
        self._toolbar.set_capture_enabled(True)
        self._toolbar.show()

        # Đóng editor cũ nếu đang mở
        if self._editor and self._editor.isVisible():
            self._editor.close()

        self._editor = EditorWindow(result)
        self._editor.show()
        self._editor.raise_()

    def _on_capture_failed(self, error_msg: str) -> None:
        """Chụp thất bại → hiện thông báo lỗi."""
        self._toolbar.set_capture_enabled(True)
        self._toolbar.show()
        QMessageBox.critical(
            None,
            f"{APP_NAME} — Lỗi",
            f"Không thể chụp ảnh:\n{error_msg}",
        )

    def _on_capture_cancelled(self) -> None:
        """Người dùng nhấn Escape trên overlay."""
        self._toolbar.set_capture_enabled(True)
        self._toolbar.show()

    # ─── Thoát ───────────────────────────────────────────────────────────────

    def _quit(self) -> None:
        """Dừng tất cả và thoát ứng dụng."""
        self._hotkey.stop()
        self._tray.hide()
        self._app.quit()


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main() -> None:
    """Hàm khởi động chính."""
    # Bật High DPI scaling cho màn hình 2K/4K
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Không thoát khi đóng cửa sổ cuối cùng (vẫn còn tray)
    app.setQuitOnLastWindowClosed(False)

    # Kiểm tra hệ thống hỗ trợ System Tray
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None,
            APP_NAME,
            "Hệ thống không hỗ trợ System Tray Icon. Ứng dụng không thể chạy.",
        )
        sys.exit(1)

    # Khởi chạy controller
    _app_instance = SnippingApp(app)

    # Thông báo khởi động
    _app_instance._tray.showMessage(
        APP_NAME,
        f"Đã khởi động!\nBấm Alt+Shift+S để chụp màn hình.",
        QSystemTrayIcon.MessageIcon.Information,
        3000,
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
