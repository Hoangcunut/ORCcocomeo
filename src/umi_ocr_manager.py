"""
umi_ocr_manager.py
------------------
Quản lý vòng đời Umi-OCR.exe.

CHIẾN LƯỢC KHỞI ĐỘNG:
- Dùng os.startfile() — giống như user double-click exe.
- Windows tự cấp môi trường sạch, hoàn toàn độc lập với Python env của app.
- Không inherit env bẩn (PYTHONUTF8, PYTHONPATH, DLL paths) gây crash Umi-OCR.

Thiết kế:
  - Singleton — chỉ một instance trong toàn app.
  - is_ready() probe HTTP /api/ocr/get_options — nhẹ, nhanh.
  - Nếu user đã tự mở Umi-OCR → detect được, không start lại.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import requests

from src.config import (
    UMI_OCR_CONNECT_TIMEOUT,
    UMI_OCR_EXE_PATH,
    UMI_OCR_HOST,
)


class UmiOcrManager:
    """Singleton quản lý tiến trình Umi-OCR.exe."""

    _instance: "UmiOcrManager | None" = None

    @classmethod
    def instance(cls) -> "UmiOcrManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._pid: Optional[int] = None  # PID của process ta đã start
        self._we_started_it: bool = False

    # ─── Public API ───────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Kiểm tra Umi-OCR.exe có trên máy không."""
        return UMI_OCR_EXE_PATH is not None and Path(UMI_OCR_EXE_PATH).exists()

    def is_ready(self) -> bool:
        """Kiểm tra Umi-OCR HTTP server đang phản hồi không (timeout 2s)."""
        try:
            resp = requests.get(
                f"http://{UMI_OCR_HOST}/api/ocr/get_options",
                timeout=2.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def start(self) -> bool:
        """
        Khởi động Umi-OCR.exe (không block).
        Dùng os.startfile() — Windows tạo process hoàn toàn độc lập,
        không inherit env Python, không xung đột DLL.
        """
        if not self.is_available():
            return False
        if self.is_ready():
            return True  # Đã chạy rồi

        exe_path = str(UMI_OCR_EXE_PATH)
        exe_dir  = str(Path(exe_path).parent)

        # ── Phương án 1: os.startfile() ─────────────────────────────────────
        # Giống user double-click — sạch nhất, không inherit bất kỳ env nào.
        try:
            os.startfile(exe_path)
            self._we_started_it = True
            return True
        except Exception:
            pass

        # ── Phương án 2: subprocess env sạch, KHÔNG dùng CREATE_NO_WINDOW ──
        # Umi-OCR là GUI app — CREATE_NO_WINDOW block nó khởi động!
        try:
            minimal_env = {
                k: os.environ[k]
                for k in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP",
                           "USERNAME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                           "PROGRAMFILES", "PROGRAMDATA", "COMPUTERNAME")
                if k in os.environ
            }
            proc = subprocess.Popen(
                [exe_path],
                cwd=exe_dir,
                env=minimal_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # KHÔNG dùng CREATE_NO_WINDOW — Umi-OCR là GUI app!
            )
            self._pid = proc.pid
            self._we_started_it = True
            return True
        except Exception:
            pass

        # ── Phương án 3: ShellExecute qua PowerShell ────────────────────────
        try:
            subprocess.Popen(
                ["powershell", "-Command",
                 f"Start-Process '{exe_path}' -WorkingDirectory '{exe_dir}'"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._we_started_it = True
            return True
        except Exception:
            return False

    def wait_ready(self, timeout: float = 40.0, interval: float = 0.5) -> bool:
        """Chờ HTTP server của Umi-OCR phản hồi (tối đa timeout giây)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_ready():
                return True
            time.sleep(interval)
        return False

    def stop(self) -> None:
        """Dừng Umi-OCR — chỉ nếu chính app đã start nó, dùng taskkill."""
        if not self._we_started_it:
            return
        try:
            # Dùng taskkill thay vì terminate() vì ta không giữ process handle
            subprocess.run(
                ["taskkill", "/F", "/IM", "Umi-OCR.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception:
            pass
        self._pid = None
        self._we_started_it = False

    def status_text(self) -> str:
        """Trả về chuỗi trạng thái ngắn để hiển thị trên UI."""
        if not self.is_available():
            return "❌ Umi-OCR chưa cài"
        if self.is_ready():
            return "✅ Umi-OCR sẵn sàng"
        return "⏳ Umi-OCR đang khởi động..."
