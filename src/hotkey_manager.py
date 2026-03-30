"""
hotkey_manager.py
-----------------
Quản lý global hotkey (bắt phím tắt toàn hệ thống bằng pynput).
Chạy trên thread riêng, phát Qt signal khi phím được kích hoạt.
"""

from __future__ import annotations

import threading
from typing import Callable

from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal

from src.config import DEFAULT_HOTKEY_MODIFIERS, DEFAULT_HOTKEY_KEY


class HotkeyManager(QObject):
    """
    Quản lý global hotkey bằng pynput.
    
    Phát signal `activated` khi tổ hợp phím được nhấn.
    Chạy listener trên daemon thread để không chặn main thread.
    """

    # Signal phát ra khi hotkey được kích hoạt
    activated = pyqtSignal()

    def __init__(
        self,
        modifiers: tuple[str, ...] = DEFAULT_HOTKEY_MODIFIERS,
        key: str = DEFAULT_HOTKEY_KEY,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._modifiers = modifiers
        self._key = key
        self._listener: keyboard.GlobalHotKeys | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def _build_hotkey_string(self) -> str:
        """Xây dựng chuỗi hotkey theo định dạng pynput (vd: '<alt>+<shift>+s')."""
        parts = list(self._modifiers) + [self._key]
        return "+".join(parts)

    def _on_activate(self) -> None:
        """Callback nội bộ khi pynput phát hiện hotkey được nhấn."""
        self.activated.emit()

    def start(self) -> None:
        """Bắt đầu lắng nghe hotkey trên daemon thread."""
        if self._running:
            return

        hotkey_str = self._build_hotkey_string()
        self._listener = keyboard.GlobalHotKeys({hotkey_str: self._on_activate})
        self._listener.daemon = True
        self._listener.start()
        self._running = True

    def stop(self) -> None:
        """Dừng lắng nghe hotkey."""
        if self._listener and self._running:
            self._listener.stop()
            self._listener = None
            self._running = False

    def update_hotkey(
        self,
        modifiers: tuple[str, ...],
        key: str,
    ) -> None:
        """Cập nhật tổ hợp phím (dùng ở Giai đoạn 5 - Settings)."""
        self.stop()
        self._modifiers = modifiers
        self._key = key
        self.start()
