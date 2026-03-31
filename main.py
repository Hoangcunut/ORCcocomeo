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

import os
import sys
import io
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# [CRITICAL HOTFIX] PyTorch c10.dll WinError 1114 — Giải pháp toàn diện
# ═══════════════════════════════════════════════════════════════════════════════

# Bước 1: Mock stdout/stderr cho PyInstaller --windowed mode
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# Bước 2: Inject tất cả thư mục DLL cần thiết cho PyTorch
def _fix_torch_dll_path():
    """
    c10.dll phụ thuộc vcruntime140.dll (ở _internal root)
    và các DLL torch khác (ở torch/lib). Inject CẢ HAI.
    """
    if getattr(sys, 'frozen', False):
        internal = Path(sys.executable).parent / "_internal"
    else:
        internal = Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"

    dll_dirs = [
        internal,                    # vcruntime140.dll, msvcp140.dll
        internal / "torch" / "lib",  # c10.dll, torch_cpu.dll
    ]

    for dll_dir in dll_dirs:
        if not dll_dir.exists():
            continue
        dll_dir_str = str(dll_dir)
        current_path = os.environ.get("PATH", "")
        if dll_dir_str not in current_path:
            os.environ["PATH"] = dll_dir_str + os.pathsep + current_path
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(dll_dir_str)
            except OSError:
                pass

    # Fallback: Windows API trực tiếp
    torch_lib = internal / "torch" / "lib"
    if torch_lib.exists():
        try:
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(str(torch_lib))
        except Exception:
            pass

_fix_torch_dll_path()

# Bước 3: Import torch — TÙY CHỌN (app chạy bình thường nếu thiếu)
_TORCH_AVAILABLE = False
try:
    import torch
    _TORCH_AVAILABLE = True
except Exception:
    pass

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
    QSystemTrayIcon,
    QMenu,
)

from src.capture_engine import CaptureEngine, CaptureMode, CaptureResult
from src.config import APP_NAME, APP_VERSION, ASSETS_DIR
from src.hotkey_manager import HotkeyManager
from src.ui.editor_window import EditorWindow
from src.ui.overlay import ScreenOverlay
from src.ui.home_window import HomeWindow
from src.umi_ocr_manager import UmiOcrManager
from src.utils.settings import AppSettings


def _make_tray_icon() -> QPixmap:
    """
    Tạo icon tray đơn giản bằng code (không cần file ảnh).
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
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "\u2702")
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
        self._home = HomeWindow()

        # Load phím tắt từ settings.json
        mods = tuple(AppSettings.get("hotkey_modifiers"))
        key = AppSettings.get("hotkey_key")

        self._hotkey = HotkeyManager(modifiers=mods, key=key)

        # ── Kết nối signals ───────────────────────────────────────────────────
        self._engine.capture_done.connect(self._on_capture_done)
        self._engine.capture_failed.connect(self._on_capture_failed)

        self._overlay.capture_taken.connect(self._engine.process_capture)
        self._overlay.cancelled.connect(self._on_capture_cancelled)

        self._hotkey.activated.connect(self._on_hotkey_activated)

        # Nối chức năng từ HomeWindow
        self._home.capture_requested.connect(self._on_capture_requested)
        self._home.hotkey_changed_signal.connect(self._on_hotkey_changed)

        # ── System Tray ───────────────────────────────────────────────────────
        self._tray = self._setup_tray()

        # ── Khởi động ─────────────────────────────────────────────────────────
        self._hotkey.start()

        # Khởi động Umi-OCR ngầm (background) nếu đã cài sẵn
        self._umi_mgr = UmiOcrManager.instance()
        if self._umi_mgr.is_available() and not self._umi_mgr.is_ready():
            self._umi_mgr.start()

        # Hiển thị luôn Cửa sổ Home khi khởi động
        self._home.show()
        self._home.raise_()
        self._home.activateWindow()

    # ─── System Tray ─────────────────────────────────────────────────────────

    def _setup_tray(self) -> QSystemTrayIcon:
        """Thiết lập icon khay hệ thống với menu chuột phải."""
        icon = QIcon(_make_tray_icon())
        tray = QSystemTrayIcon(icon, self._app)

        hk_str = " + ".join([m.strip("<>") for m in AppSettings.get("hotkey_modifiers")] + [AppSettings.get("hotkey_key")]).upper()
        tray.setToolTip(f"{APP_NAME} v{APP_VERSION}\n{hk_str} để chụp")

        menu = QMenu()

        act_home = QAction("Mở Cửa Sổ Chính", menu)
        act_home.triggered.connect(self._show_home)
        menu.addAction(act_home)

        act_capture = QAction(f"Chụp ngay ({hk_str})", menu)
        act_capture.triggered.connect(self._on_hotkey_activated)
        menu.addAction(act_capture)

        menu.addSeparator()

        act_quit = QAction("Thoát", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        tray.setContextMenu(menu)
        # Double-click vào tray icon → Mở Home
        tray.activated.connect(
            lambda reason: self._show_home()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
        tray.show()
        return tray

    def _show_home(self):
        """Hiện lại cửa sổ Home từ Taskbar tray."""
        self._home.show()
        self._home.raise_()
        self._home.activateWindow()

    def _on_hotkey_changed(self, modifiers: list, key: str) -> None:
        """Cập nhật Hotkey cho ứng dụng và hiển thị Tray tooltip."""
        # Update listener ngầm
        self._hotkey.update_hotkey(tuple(modifiers), key)
        # Sửa Tooltip tray
        hk_str = " + ".join([m.strip("<>") for m in modifiers] + [key]).upper()
        self._tray.setToolTip(f"{APP_NAME} v{APP_VERSION}\n{hk_str} để chụp")
        # Đổi title nút trong context menu
        for act in self._tray.contextMenu().actions():
            if "Chụp ngay" in act.text():
                act.setText(f"Chụp ngay ({hk_str})")

    # ─── Xử lý hotkey / capture flow ─────────────────────────────────────────

    def _on_hotkey_activated(self) -> None:
        """Hotkey toàn hệ thống được kích hoạt → bắt đầu flow Win11."""
        self._home.hide()
        QTimer.singleShot(80, self._show_overlay)

    def _show_overlay(self) -> None:
        """Hiện overlay chọn vùng (bao gồm cả toolbar tự sinh)."""
        self._overlay.activate()

    def _on_capture_requested(self, mode: CaptureMode, delay: int) -> None:
        """Người dùng bấm nút + New trên cửa sổ chính."""
        self._home.hide()  # Giấu cửa sổ Home

        # Chuyển mode cho overlay
        self._overlay.set_mode(mode)

        if mode in (CaptureMode.RECTANGLE, CaptureMode.FREEFORM, CaptureMode.WINDOW):
            QTimer.singleShot(delay * 1000, self._show_overlay)
        elif mode == CaptureMode.FULLSCREEN:
            QTimer.singleShot(delay * 1000, self._show_overlay)

    def _on_capture_done(self, result: CaptureResult) -> None:
        """Ảnh đã chụp xong → mở cửa sổ chỉnh sửa."""
        # Đóng editor cũ nếu đang mở
        if self._editor and self._editor.isVisible():
            self._editor.close()

        self._editor = EditorWindow(result)
        self._editor.show()
        self._editor.raise_()

    def _on_capture_failed(self, error_msg: str) -> None:
        """Chụp thất bại → hiện thông báo lỗi."""
        QMessageBox.critical(
            None,
            f"{APP_NAME} — Lỗi",
            f"Không thể chụp ảnh:\n{error_msg}",
        )

    def _on_capture_cancelled(self) -> None:
        """Người dùng nhấn Escape trên overlay."""
        pass

    # ─── Thoát ───────────────────────────────────────────────────────────────

    def _quit(self) -> None:
        """Dừng tất cả và thoát ứng dụng."""
        self._hotkey.stop()
        # Dừng Umi-OCR nếu chính app đã khởi động nó
        try:
            self._umi_mgr.stop()
        except Exception:
            pass
        self._tray.hide()
        self._app.quit()


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main() -> None:
    """Hàm khởi động chính."""
    # Bật High DPI scaling cho màn hình 2K/4K
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
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
