"""
capture_engine.py
-----------------
Engine chụp ảnh màn hình dùng mss + Pillow.
Hỗ trợ: Rectangle (vùng chọn), Fullscreen, Window (placeholder), Freeform (placeholder).
Kết quả: PIL.Image + tự động copy vào Clipboard (QApplication.clipboard()).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import mss
import mss.tools
from PIL import Image
from PyQt6.QtCore import QObject, QRect, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication

from src.config import TEMP_SCREENSHOT


class CaptureMode(Enum):
    """Các chế độ chụp màn hình."""
    RECTANGLE = auto()
    FULLSCREEN = auto()
    WINDOW = auto()    # Chụp cửa sổ đang focus (hoàn thiện Giai đoạn 2)
    FREEFORM = auto()  # Vùng tự do (hoàn thiện Giai đoạn 2)


@dataclass
class CaptureResult:
    """Kết quả của một lần chụp."""
    image: Image.Image          # Ảnh PIL gốc
    mode: CaptureMode           # Chế độ chụp đã dùng
    filepath: str               # Đường dẫn file tạm đã lưu
    timestamp: float            # Unix timestamp lúc chụp


class CaptureEngine(QObject):
    """
    Engine chụp ảnh màn hình.
    
    Signals:
        capture_done (CaptureResult): Phát ra khi ảnh đã được chụp và xử lý xong.
        capture_failed (str):         Phát ra khi có lỗi, kèm thông báo lỗi.
    """

    capture_done = pyqtSignal(object)   # CaptureResult
    capture_failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    # ─── Public API ───────────────────────────────────────────────────────────

    def capture_fullscreen(self, delay: int = 0) -> None:
        """Chụp toàn bộ màn hình đầu tiên."""
        self._do_capture(mode=CaptureMode.FULLSCREEN, region=None, delay=delay)

    def capture_rectangle(self, region: QRect, delay: int = 0) -> None:
        """Chụp vùng hình chữ nhật đã chọn (pixel tuyệt đối trên màn hình)."""
        self._do_capture(mode=CaptureMode.RECTANGLE, region=region, delay=delay)

    def capture_window(self, delay: int = 0) -> None:
        """
        Placeholder Giai đoạn 2: chụp cửa sổ đang focus.
        Hiện tại chụp fullscreen thay thế.
        """
        self._do_capture(mode=CaptureMode.WINDOW, region=None, delay=delay)

    def capture_freeform(self, delay: int = 0) -> None:
        """
        Placeholder Giai đoạn 2: chụp vùng đa giác tự do.
        Hiện tại chụp fullscreen thay thế.
        """
        self._do_capture(mode=CaptureMode.FREEFORM, region=None, delay=delay)

    # ─── Internal ────────────────────────────────────────────────────────────

    def _do_capture(
        self,
        mode: CaptureMode,
        region: Optional[QRect],
        delay: int,
    ) -> None:
        """Thực hiện chụp, lưu file tạm, copy clipboard."""
        try:
            # Chờ nếu có delay (sleep trước khi chụp)
            if delay > 0:
                time.sleep(delay)

            pil_image = self._grab(region)

            # Lưu file tạm PNG
            filepath = str(TEMP_SCREENSHOT)
            pil_image.save(filepath, format="PNG")

            # Copy ảnh vào clipboard hệ thống
            self._copy_to_clipboard(pil_image)

            result = CaptureResult(
                image=pil_image,
                mode=mode,
                filepath=filepath,
                timestamp=time.time(),
            )
            self.capture_done.emit(result)

        except Exception as exc:
            self.capture_failed.emit(str(exc))

    def _grab(self, region: Optional[QRect]) -> Image.Image:
        """
        Chụp màn hình bằng mss.
        
        Args:
            region: Vùng cần chụp (pixel tuyệt đối). None → chụp toàn màn hình.
        
        Returns:
            PIL.Image.Image ở định dạng RGB.
        """
        with mss.mss() as sct:
            if region is None:
                # Toàn bộ màn hình đầu tiên
                monitor = sct.monitors[1]
            else:
                monitor = {
                    "left":   region.left(),
                    "top":    region.top(),
                    "width":  max(region.width(), 1),
                    "height": max(region.height(), 1),
                }

            screenshot = sct.grab(monitor)
            # mss trả về BGRA → chuyển sang RGB bằng Pillow
            pil_img = Image.frombytes(
                "RGB",
                screenshot.size,
                screenshot.bgra,
                "raw",
                "BGRX",
            )
        return pil_img

    def _copy_to_clipboard(self, pil_image: Image.Image) -> None:
        """Chuyển PIL Image sang QPixmap rồi copy vào QClipboard."""
        # Chuyển PIL → QImage
        pil_rgb = pil_image.convert("RGB")
        data = pil_rgb.tobytes("raw", "RGB")
        qimage = QImage(
            data,
            pil_rgb.width,
            pil_rgb.height,
            pil_rgb.width * 3,
            QImage.Format.Format_RGB888,
        )
        pixmap = QPixmap.fromImage(qimage)

        clipboard = QApplication.clipboard()
        clipboard.setPixmap(pixmap)
