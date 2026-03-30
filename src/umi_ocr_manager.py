"""
umi_ocr_manager.py
------------------
Quản lý vòng đời (lifecycle) của tiến trình Umi-OCR.exe.

Chức năng:
  - Kiểm tra Umi-OCR đã được cài (exe tồn tại) hay chưa.
  - Kiểm tra Umi-OCR đang chạy (HTTP server sẵn sàng) hay chưa.
  - Khởi động Umi-OCR.exe ở nền nếu chưa chạy.
  - Dừng Umi-OCR.exe khi đóng app (nếu chính app này khởi động nó).

Thiết kế:
  - Singleton — chỉ một instance trong toàn app.
  - Không block main thread (dùng threading.Thread để start/wait).
  - Nếu user đã tự mở Umi-OCR trước → detect được, không start lại.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from threading import Thread
from typing import Optional

import requests

from src.config import (
    UMI_OCR_CONNECT_TIMEOUT,
    UMI_OCR_EXE_PATH,
    UMI_OCR_HOST,
)


class UmiOcrManager:
    """
    Singleton quản lý tiến trình Umi-OCR.exe.
    
    Usage:
        mgr = UmiOcrManager.instance()
        if mgr.is_available():        # exe đã có
            if not mgr.is_ready():    # server chưa chạy
                mgr.start()           # khởi động không block
                mgr.wait_ready(15)    # chờ tối đa 15 giây
    """

    _instance: "UmiOcrManager | None" = None

    @classmethod
    def instance(cls) -> "UmiOcrManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._we_started_it: bool = False   # Chỉ True nếu chính app này đã start

    # ─── Public API ───────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Kiểm tra Umi-OCR.exe có trên máy không (đã cài / bundle sẵn)."""
        return UMI_OCR_EXE_PATH is not None and Path(UMI_OCR_EXE_PATH).exists()

    def is_ready(self) -> bool:
        """
        Kiểm tra Umi-OCR HTTP server đang phản hồi không.
        Gọi nhanh (timeout 2s), không block lâu.
        """
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
        Khởi động Umi-OCR.exe ở nền (không block).
        
        Returns:
            True nếu đã spawn process thành công.
            False nếu exe không tồn tại hoặc đã chạy rồi.
        """
        if not self.is_available():
            return False
        if self.is_ready():
            return True   # Đã chạy rồi (do user mở hoặc lần trước)

        if self._process and self._process.poll() is None:
            return True   # Process chúng ta spawn còn sống

        try:
            exe = str(UMI_OCR_EXE_PATH)
            # Khởi động Umi-OCR ẩn. Ép encoding UTF-8 để khắc phục lỗi Umi-OCR bị crash
            # (UnicodeEncodeError) khi print log tiếng Trung lúc không hiện Console window.
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            self._process = subprocess.Popen(
                [exe],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # Không tạo console window mới trên Windows
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._we_started_it = True
            return True
        except Exception:
            return False

    def wait_ready(self, timeout: float = 20.0, interval: float = 0.5) -> bool:
        """
        Chờ cho đến khi HTTP server của Umi-OCR phản hồi.
        
        Args:
            timeout:  Tổng thời gian chờ tối đa (giây).
            interval: Khoảng giữa các lần probe (giây).
        
        Returns:
            True nếu server sẵn sàng trong timeout.
            False nếu hết timeout mà vẫn chưa.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_ready():
                return True
            time.sleep(interval)
        return False

    def stop(self) -> None:
        """
        Dừng Umi-OCR.exe — chỉ dừng nếu chính app này đã khởi động nó.
        Nếu user tự mở → không can thiệp.
        """
        if self._we_started_it and self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._process = None
        self._we_started_it = False

    def status_text(self) -> str:
        """Trả về chuỗi trạng thái ngắn để hiển thị trên UI."""
        if not self.is_available():
            return "❌ Umi-OCR chưa cài"
        if self.is_ready():
            return "✅ Umi-OCR sẵn sàng"
        return "⏳ Umi-OCR đang khởi động..."
