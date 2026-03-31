"""
ocr_engine.py  (Dual-Engine: Umi-OCR + Tesseract)
--------------------------------------------------
Thay thế hoàn toàn Ollama/DeepSeek bằng 2 engine nhẹ hơn:

  ┌─────────────────────────────────────────────────────┐
  │                  OcrEngine (facade)                 │
  │   ┌────────────────┐   ┌──────────────────────────┐ │
  │   │ UmiOcrBackend  │   │  TesseractBackend        │ │
  │   │ POST /api/ocr  │   │  pytesseract (in-process)│ │
  │   └────────────────┘   └──────────────────────────┘ │
  │   OcrWorker(QThread) chạy backend trong thread nền  │
  └─────────────────────────────────────────────────────┘

Engine preference:
  AUTO      → thử Umi-OCR, fallback Tesseract nếu Umi không có/lỗi
  UMI_ONLY  → chỉ Umi-OCR (lỗi nếu không có)
  TESS_ONLY → chỉ Tesseract (bảo mật tối đa, không cần server)

Ngôn ngữ hỗ trợ: vie, eng, chi_sim, chi_tra, jpn (và tổ hợp)
"""

from __future__ import annotations

import base64
import os
import re
from enum import Enum, auto
from io import BytesIO
from typing import Optional

import requests
from PIL import Image
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from src.config import (
    OCR_ENGINE_PREFERENCE,
    OCR_LANGUAGES,
    TESSERACT_DATA_DIR,
    TESSERACT_EXE_PATH,
    UMI_OCR_CONNECT_TIMEOUT,
    UMI_OCR_HOST,
    UMI_OCR_READ_TIMEOUT,
)
from src.umi_ocr_manager import UmiOcrManager


def remove_vietnamese_accents(s: str) -> str:
    """Loại bỏ dấu của Tiếng Việt."""
    s = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', s)
    s = re.sub(r'[ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴ]', 'A', s)
    s = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', s)
    s = re.sub(r'[ÈÉẸẺẼÊỀẾỆỂỄ]', 'E', s)
    s = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', s)
    s = re.sub(r'[ÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠ]', 'O', s)
    s = re.sub(r'[ìíịỉĩ]', 'i', s)
    s = re.sub(r'[ÌÍỊỈĨ]', 'I', s)
    s = re.sub(r'[ùúụủũưừứựửữ]', 'u', s)
    s = re.sub(r'[ÙÚỤỦŨƯỪỨỰỬỮ]', 'U', s)
    s = re.sub(r'[ỳýỵỷỹ]', 'y', s)
    s = re.sub(r'[ỲÝỴỶỸ]', 'Y', s)
    s = re.sub(r'[đ]', 'd', s)
    s = re.sub(r'[Đ]', 'D', s)
    # Loại bỏ một số dấu thanh độc lập nếu có
    s = re.sub(r'[\u0300\u0301\u0303\u0309\u0323]', '', s) 
    s = re.sub(r'[\u02C6\u0306\u031B]', '', s)
    return s

# ─── Engine Preference ────────────────────────────────────────────────────────

class EnginePreference(Enum):
    AUTO        = "auto"        # Umi-OCR → fallback Tesseract
    UMI_ONLY    = "umi_only"   # Chỉ Umi-OCR
    TESS_ONLY   = "tess_only"  # Chỉ Tesseract
    VIETOCR     = "vietocr"    # VietOCR (Tiếng Việt chính xác + overlay)

    @classmethod
    def from_str(cls, s: str) -> "EnginePreference":
        try:
            return cls(s.lower())
        except ValueError:
            return cls.AUTO


# ─── Umi-OCR Backend ────────────────────────────────────────────────────────

class UmiOcrBackend:
    """
    Backend gọi Umi-OCR HTTP API.
    
    API endpoint: POST http://127.0.0.1:1224/api/ocr
    Request: {"base64": "<base64_png>", "options": {...}}
    Response: {"code": 100, "data": [{"text": "...", "score": 0.99, "box": ...}]}
    
    code 100 = thành công, khác = lỗi.
    """

    def run(
        self,
        image: Image.Image,
        lang_hint: str = "models/config_chinese.txt",
        progress_cb=None,
    ) -> str:
        """
        Thực thi OCR bằng Umi-OCR.
        
        Args:
            image:      PIL Image cần nhận diện.
            lang_hint:  Giá trị "ocr.language" truyền vào Umi-OCR API.
                        Phải khớp với path model trong configs.txt của plugin
                        (vd: "models/config_chinese.txt", "models/config_en.txt").
            progress_cb: Callback(str) để báo tiến trình.
        
        Returns:
            Chuỗi văn bản đã nhận diện.
        
        Raises:
            ConnectionError, RuntimeError nếu có lỗi.
        """
        if progress_cb:
            progress_cb("🔄 Đang mã hoá ảnh cho Umi-OCR...")

        img_b64 = self._encode(image)

        if progress_cb:
            progress_cb("📡 Đang gọi Umi-OCR API...")

        url = f"http://{UMI_OCR_HOST}/api/ocr"

        # Truyền đúng ocr.language để Umi-OCR dùng model phù hợp với ngôn ngữ mục tiêu.
        # Nếu không truyền, Umi-OCR dùng model mặc định (thường là tiếng Trung/Anh)
        # khiến dấu Tiếng Việt bị nhận nhầm hoặc bỏ qua.
        # data.format="text" → nhận plain text thay vì phải tự parse list dict.
        payload: dict = {
            "base64": img_b64,
            "options": {
                "ocr.language": lang_hint,
                "data.format": "text",
            },
        }

        resp = requests.post(
            url,
            json=payload,
            timeout=(UMI_OCR_CONNECT_TIMEOUT, UMI_OCR_READ_TIMEOUT),
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Umi-OCR trả HTTP {resp.status_code}:\n{resp.content[:300].decode('utf-8', errors='replace')}"
            )

        data = resp.json()
        code = data.get("code", -1)

        # code 804 = options không hợp lệ (thường do model chưa cài)
        # → fallback: retry không có options để vẫn nhận được kết quả (dù có thể không đúng ngôn ngữ)
        if code == 804:
            if progress_cb:
                progress_cb(f"⚠️ Model '{lang_hint}' chưa cài — dùng model mặc định (dấu có thể bị mất)...")
            payload_fallback: dict = {
                "base64": img_b64,
                "options": {"data.format": "text"},
            }
            resp = requests.post(
                url,
                json=payload_fallback,
                timeout=(UMI_OCR_CONNECT_TIMEOUT, UMI_OCR_READ_TIMEOUT),
            )
            data = resp.json()
            code = data.get("code", -1)

        if code != 100:
            msg = data.get("data", "Lỗi không rõ")
            raise RuntimeError(f"Umi-OCR lỗi code {code}: {msg}")

        # data.format="text" → data là string thuần
        result = data.get("data", "")
        if isinstance(result, str):
            return result
        # Nếu vẫn là list dict (engine cũ không hỗ trợ data.format)
        if isinstance(result, list):
            lines = [item.get("text", "") for item in result if isinstance(item, dict)]
            return "\n".join(filter(None, lines))
        return ""

    @staticmethod
    def _encode(image: Image.Image) -> str:
        """Resize nếu quá lớn rồi encode base64."""
        buf = BytesIO()
        img = image.copy()
        if img.width > 4096 or img.height > 4096:
            img.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
        img.save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


# ─── Tesseract Backend ────────────────────────────────────────────────────────

class TesseractBackend:
    """
    Backend OCR dùng Tesseract (pytesseract).
    Chạy hoàn toàn in-process, không cần server, bảo mật tối đa.
    """

    def is_available(self) -> bool:
        """Kiểm tra Tesseract có thể dùng được không."""
        try:
            import pytesseract
            if TESSERACT_EXE_PATH:
                pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE_PATH
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def run(
        self,
        image: Image.Image,
        lang: str = "vie+eng",
        progress_cb=None,
    ) -> str:
        """
        Thực thi OCR bằng Tesseract.
        
        Args:
            image:       PIL Image cần nhận diện.
            lang:        Mã ngôn ngữ Tesseract (vd: "vie+eng", "chi_sim+eng").
            progress_cb: Callback(str) để báo tiến trình.
        
        Returns:
            Chuỗi văn bản đã nhận diện.
        
        Raises:
            RuntimeError nếu Tesseract không cài hoặc lỗi.
        """
        import pytesseract

        # Cấu hình đường dẫn exe và tessdata
        if TESSERACT_EXE_PATH:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE_PATH

        if progress_cb:
            progress_cb(f"⚙️ Tesseract OCR đang xử lý ({lang})...")

        # Config tessdata dir nếu dùng bundled data
        config = ""
        if TESSERACT_DATA_DIR:
            config = f'--tessdata-dir "{TESSERACT_DATA_DIR}"'

        # Chuyển về grayscale + tăng kích thước để tăng độ chính xác
        pil_gray = image.convert("L")
        # Upscale 2x nếu ảnh nhỏ (< 800px) giúp Tesseract nhận chữ tốt hơn
        if pil_gray.width < 800:
            new_w = pil_gray.width * 2
            new_h = pil_gray.height * 2
            pil_gray = pil_gray.resize((new_w, new_h), Image.Resampling.LANCZOS)

        try:
            result: str = pytesseract.image_to_string(
                pil_gray,
                lang=lang,
                config=config,
            )
            return result.strip()
        except pytesseract.TesseractError as exc:
            raise RuntimeError(f"Tesseract lỗi: {exc}") from exc
        except Exception as exc:
            if "not installed" in str(exc).lower() or "not found" in str(exc).lower():
                raise RuntimeError(
                    "Tesseract chưa được cài.\n\n"
                    "Cài tại: https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "Hoặc đặt tesseract.exe vào thư mục: custom-snipping-tool/tesseract/"
                ) from exc
            raise RuntimeError(str(exc)) from exc


# ─── OCR Worker Thread ────────────────────────────────────────────────────────

class OcrWorker(QThread):
    """
    Thread nền chạy OCR — tránh block UI.
    
    Signals:
        finished (str):               Kết quả text khi xong.
        error_occurred (str):         Thông báo lỗi.
        progress_update (str):        Cập nhật trạng thái.
        engine_used (str):            Engine đã dùng ("umi"/"tess"/"vietocr").
        overlay_ready (object):       OcrOverlayResult — chỉ phát khi dùng VietOCR.
    """

    finished       = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_update = pyqtSignal(str)
    engine_used    = pyqtSignal(str)
    overlay_ready  = pyqtSignal(object)   # OcrOverlayResult

    def __init__(
        self,
        image: Image.Image,
        preference: EnginePreference,
        tess_lang: str,
        umi_lang: str,
        remove_accent: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._image = image
        self._preference = preference
        self._tess_lang = tess_lang
        self._umi_lang  = umi_lang
        self._remove_accent = remove_accent
        self._stop_flag = False

    def stop(self) -> None:
        self._stop_flag = True

    def run(self) -> None:
        try:
            result = self._dispatch()
            if getattr(self, "_remove_accent", False):
                result = remove_vietnamese_accents(result)
            if not self._stop_flag:
                self.finished.emit(result)
        except Exception as exc:
            if not self._stop_flag:
                self.error_occurred.emit(str(exc))

    def _dispatch(self) -> str:
        """Chọn engine theo preference và chạy."""
        pref = self._preference
        umi_mgr = UmiOcrManager.instance()
        umi_backend = UmiOcrBackend()
        tess_backend = TesseractBackend()

        def _prog(msg: str) -> None:
            if not self._stop_flag:
                self.progress_update.emit(msg)

        # ── VietOCR (Tiếng Việt chính xác + overlay) ──────────────────────────
        if pref == EnginePreference.VIETOCR:
            from src.vietocr_engine import VietOCREngine
            from src.config import VIETOCR_MODEL, VIETOCR_DEVICE
            _prog("🇻🇳 VietOCR engine đang khởi tạo...")
            engine = VietOCREngine(model_name=VIETOCR_MODEL, device=VIETOCR_DEVICE)
            if not engine.is_available():
                raise RuntimeError(
                    "VietOCR chưa được cài.\n"
                    "Chạy: pip install vietocr torch torchvision"
                )
            result = engine.recognize(self._image, progress_cb=_prog)
            self.engine_used.emit("vietocr")
            if not self._stop_flag:
                self.overlay_ready.emit(result)
            return result.plain_text

        # ── Chỉ Tesseract ─────────────────────────────────────────────────────
        if pref == EnginePreference.TESS_ONLY:
            _prog("🔒 Chế độ bảo mật — dùng Tesseract (offline, không server)")
            if not tess_backend.is_available():
                raise RuntimeError(
                    "Tesseract chưa cài.\n"
                    "Tải tại: https://github.com/UB-Mannheim/tesseract/wiki"
                )
            self.engine_used.emit("tess")
            return tess_backend.run(self._image, self._tess_lang, _prog)

        # ── Chỉ Umi-OCR ───────────────────────────────────────────────────────
        if pref == EnginePreference.UMI_ONLY:
            if not umi_mgr.is_available():
                raise RuntimeError(
                    "Umi-OCR chưa được cài.\n"
                    "Tải portable tại: https://github.com/hiroi-sora/Umi-OCR/releases\n"
                    "Giải nén vào thư mục: custom-snipping-tool/umi-ocr/"
                )
            if not umi_mgr.is_ready():
                _prog("⏳ Đang khởi động Umi-OCR...")
                umi_mgr.start()
                if not umi_mgr.wait_ready(20):
                    raise RuntimeError(
                        "Umi-OCR không khởi động được trong 20 giây.\n"
                        "Hãy mở UmiOCR.exe thủ công rồi thử lại."
                    )
            self.engine_used.emit("umi")
            return umi_backend.run(self._image, self._umi_lang, _prog)

        # ── Auto: Umi-OCR → fallback Tesseract ───────────────────────────────
        # Bước 1: thử Umi-OCR
        if umi_mgr.is_available():
            if not umi_mgr.is_ready():
                _prog("⏳ Đang khởi động Umi-OCR...")
                umi_mgr.start()
                ready = umi_mgr.wait_ready(15)
            else:
                ready = True

            if ready:
                try:
                    _prog("🎯 Umi-OCR đang nhận diện...")
                    result = umi_backend.run(self._image, self._umi_lang, _prog)
                    self.engine_used.emit("umi")
                    return result
                except requests.exceptions.ConnectionError:
                    _prog("⚠️ Umi-OCR mất kết nối, chuyển sang Tesseract...")
                except RuntimeError as exc:
                    _prog(f"⚠️ Umi-OCR lỗi: {exc!s:.60} — chuyển sang Tesseract...")
            else:
                _prog("⚠️ Umi-OCR không khởi động được, dùng Tesseract...")
        else:
            _prog("ℹ️ Umi-OCR chưa cài — dùng Tesseract...")

        # Bước 2: fallback Tesseract
        if not tess_backend.is_available():
            raise RuntimeError(
                "Không có engine OCR nào khả dụng!\n\n"
                "• Umi-OCR: Tải tại https://github.com/hiroi-sora/Umi-OCR/releases\n"
                "• Tesseract: Tải tại https://github.com/UB-Mannheim/tesseract/wiki"
            )

        self.engine_used.emit("tess")
        return tess_backend.run(self._image, self._tess_lang, _prog)


# ─── OcrEngine Facade ─────────────────────────────────────────────────────────

class OcrEngine(QObject):
    """
    Facade dễ dùng từ UI code. Quản lý OcrWorker, phát Qt signal.
    
    Signals:
        ocr_finished (str):   Toàn bộ kết quả OCR.
        ocr_failed (str):     Thông báo lỗi.
        status_changed (str): Cập nhật trạng thái.
        is_running (bool):    Đang chạy hay không.
        engine_used (str):    Engine đã dùng ("umi" hoặc "tess").
    """

    ocr_finished   = pyqtSignal(str)
    ocr_failed     = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    is_running     = pyqtSignal(bool)
    engine_used    = pyqtSignal(str)
    overlay_ready  = pyqtSignal(object)   # OcrOverlayResult (chỉ khi VietOCR)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: OcrWorker | None = None

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start_ocr(
        self,
        image: Image.Image,
        preference: EnginePreference = EnginePreference.AUTO,
        lang_index: int = 0,
        remove_accent: bool = False,
    ) -> None:
        """
        Bắt đầu OCR không đồng bộ.
        
        Args:
            image:         PIL Image cần nhận diện.
            preference:    Engine ưu tiên (AUTO / UMI_ONLY / TESS_ONLY).
            lang_index:    Index vào OCR_LANGUAGES list trong config.
            remove_accent: Tuỳ chọn xóa dấu Tiếng Việt.
        """
        if self.running:
            return

        # Lấy thông tin ngôn ngữ
        from src.config import OCR_LANGUAGES
        lang_cfg = OCR_LANGUAGES[lang_index] if 0 <= lang_index < len(OCR_LANGUAGES) else OCR_LANGUAGES[0]
        tess_lang = lang_cfg["tess"]
        umi_lang  = lang_cfg["umi"]

        # NOTE: Pre-import torch trên main thread để tránh lỗi WinError 1114 (DLL init)
        # khi torch được load lần đầu bên trong QThread.
        if preference in (EnginePreference.AUTO, EnginePreference.VIETOCR):
            self.status_changed.emit("Đang tải thư viện OCR...")
            QApplication.processEvents()
            try:
                import torch
            except (ImportError, OSError):
                pass

        self._worker = OcrWorker(image, preference, tess_lang, umi_lang, remove_accent)
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.progress_update.connect(self.status_changed.emit)
        self._worker.engine_used.connect(self.engine_used.emit)
        self._worker.overlay_ready.connect(self.overlay_ready.emit)

        self.is_running.emit(True)
        self._worker.start()

    def cancel(self) -> None:
        """Huỷ OCR đang chạy."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        self.is_running.emit(False)

    def check_engines(self) -> dict[str, bool | str]:
        """
        Kiểm tra nhanh trạng thái cả 2 engine.
        
        Returns:
            {
                "umi_available": bool,   # exe tồn tại
                "umi_ready":     bool,   # HTTP server đang chạy
                "tess_available": bool,  # pytesseract + exe OK
            }
        """
        umi_mgr = UmiOcrManager.instance()
        tess_ok = TesseractBackend().is_available()
        return {
            "umi_available":  umi_mgr.is_available(),
            "umi_ready":      umi_mgr.is_ready(),
            "tess_available": tess_ok,
        }

    def _on_finished(self, text: str) -> None:
        self.is_running.emit(False)
        self.ocr_finished.emit(text)

    def _on_error(self, msg: str) -> None:
        self.is_running.emit(False)
        self.ocr_failed.emit(msg)
