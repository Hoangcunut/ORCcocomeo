"""
vietocr_engine.py
-----------------
VietOCR integration — nhận dạng Tiếng Việt chính xác với dấu đầy đủ.

Pipeline:
  1. Tesseract image_to_data() → word-level bounding boxes
  2. Crop từng dòng text → VietOCR predict → text chính xác
  3. Trả về List[WordBox] gồm text + tọa độ để render overlay

VietOCR auto-download model lần đầu (~100MB), cache tại ~/.cache/vietocr/
Sau lần đầu: hoạt động hoàn toàn offline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from PIL import Image

logger = logging.getLogger(__name__)

# ─── Data Model ───────────────────────────────────────────────────────────────

@dataclass
class WordBox:
    """Một khối text được nhận diện, kèm vị trí tuyệt đối trên ảnh gốc."""
    text:       str
    x:          int   # pixel từ trái
    y:          int   # pixel từ trên
    width:      int
    height:     int
    confidence: float = 1.0  # 0.0 – 1.0

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass
class OcrOverlayResult:
    """Kết quả đầy đủ gồm text thuần + danh sách WordBox để render overlay."""
    plain_text: str                    = ""
    word_boxes: List[WordBox]          = field(default_factory=list)
    image_width:  int                  = 0
    image_height: int                  = 0
    engine:       str                  = "vietocr"


# ─── VietOCR Engine ───────────────────────────────────────────────────────────

class VietOCREngine:
    """
    Engine kết hợp Tesseract (detection) + VietOCR (recognition).

    Tesseract cung cấp bounding boxes chính xác.
    VietOCR cung cấp text Tiếng Việt chính xác có dấu đầy đủ.

    Usage:
        engine = VietOCREngine()
        result = engine.recognize(pil_image, lang="vie")
    """

    def __init__(self, model_name: str = "vgg_seq2seq", device: str = "cpu") -> None:
        """
        Args:
            model_name: "vgg_seq2seq" (nhanh, đủ dùng) hoặc "vgg_transformer" (chính xác hơn)
            device:     "cpu" hoặc "cuda" nếu có GPU
        """
        self._model_name  = model_name
        self._device      = device
        self._predictor   = None   # lazy load
        self._tess_config = "--psm 11"   # detect từng word riêng biệt

    # ── Public API ────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Kiểm tra VietOCR và Tesseract có thể import không."""
        try:
            import pytesseract   # noqa: F401
            import vietocr       # noqa: F401
            return True
        except ImportError:
            return False

    def recognize(
        self,
        image: Image.Image,
        progress_cb=None,
    ) -> OcrOverlayResult:
        """
        Nhận dạng ảnh → trả về OcrOverlayResult gồm WordBox + text thuần.

        Args:
            image:       PIL Image RGB.
            progress_cb: Callback(str) để báo trạng thái.

        Returns:
            OcrOverlayResult

        Raises:
            RuntimeError nếu thiếu dependency.
        """
        self._emit(progress_cb, "🔄 Khởi tạo VietOCR engine...")

        # Lazy-load predictor lần đầu
        predictor = self._get_predictor(progress_cb)

        self._emit(progress_cb, "🔍 Tesseract đang tìm vùng text...")
        line_boxes = self._detect_lines(image)

        if not line_boxes:
            return OcrOverlayResult(
                plain_text="",
                word_boxes=[],
                image_width=image.width,
                image_height=image.height,
            )

        self._emit(progress_cb, f"✍️ VietOCR đang nhận dạng {len(line_boxes)} dòng text...")
        word_boxes: List[WordBox] = []
        all_lines: List[str] = []

        for i, (x, y, w, h) in enumerate(line_boxes):
            if w < 5 or h < 5:
                continue

            # Crop dòng text với padding nhỏ để tăng độ chính xác
            pad = 4
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(image.width,  x + w + pad)
            y2 = min(image.height, y + h + pad)
            crop = image.crop((x1, y1, x2, y2))

            # VietOCR nhận dạng dòng crop
            try:
                text = predictor.predict(crop)
            except Exception as exc:
                logger.warning("VietOCR lỗi dòng %d: %s", i, exc)
                text = ""

            if text.strip():
                all_lines.append(text.strip())
                word_boxes.append(WordBox(
                    text=text.strip(),
                    x=x, y=y, width=w, height=h,
                    confidence=1.0,
                ))

        plain_text = "\n".join(all_lines)
        self._emit(progress_cb, f"✅ Nhận dạng xong — {len(word_boxes)} dòng, {len(plain_text)} ký tự")

        return OcrOverlayResult(
            plain_text=plain_text,
            word_boxes=word_boxes,
            image_width=image.width,
            image_height=image.height,
            engine="vietocr",
        )

    # ── Private: Tesseract Detection ─────────────────────────────────────────

    def _detect_lines(self, image: Image.Image) -> List[tuple]:
        """
        Dùng Tesseract image_to_data() để lấy bounding boxes từng dòng text.
        Returns list of (x, y, w, h).
        """
        import pytesseract
        from src.config import TESSERACT_EXE_PATH, TESSERACT_DATA_DIR

        if TESSERACT_EXE_PATH:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE_PATH

        # Lấy data dạng dict từ Tesseract
        tsv_config = r"--oem 3 --psm 3"
        tessdata_cfg = f"--tessdata-dir \"{TESSERACT_DATA_DIR}\"" if TESSERACT_DATA_DIR else ""

        try:
            data = pytesseract.image_to_data(
                image,
                lang="vie+eng",
                config=f"{tsv_config} {tessdata_cfg}".strip(),
                output_type=pytesseract.Output.DICT,
            )
        except Exception as exc:
            logger.error("Tesseract detection lỗi: %s", exc)
            return []

        # Nhóm theo line_num để lấy bounding box từng dòng
        line_boxes: dict[tuple, dict] = {}
        n = len(data["level"])
        for i in range(n):
            if int(data["conf"][i]) < 10:   # bỏ detection độ tin thấp
                continue
            text = str(data["text"][i]).strip()
            if not text:
                continue
            block_num = data["block_num"][i]
            line_num  = data["line_num"][i]
            key = (block_num, line_num)
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]
            if key not in line_boxes:
                line_boxes[key] = {"x": x, "y": y, "x2": x+w, "y2": y+h}
            else:
                lb = line_boxes[key]
                lb["x"]  = min(lb["x"],  x)
                lb["y"]  = min(lb["y"],  y)
                lb["x2"] = max(lb["x2"], x + w)
                lb["y2"] = max(lb["y2"], y + h)

        result = []
        for lb in line_boxes.values():
            x  = lb["x"]
            y  = lb["y"]
            w  = lb["x2"] - x
            h  = lb["y2"] - y
            if w > 10 and h > 5:
                result.append((x, y, w, h))

        return result

    # ── Private: VietOCR Predictor ────────────────────────────────────────────

    def _get_predictor(self, progress_cb=None):
        """Lazy-load VietOCR predictor. Download model lần đầu (~100MB)."""
        if self._predictor is not None:
            return self._predictor

        try:
            from vietocr.tool.predictor import Predictor
            from vietocr.tool.config import Cfg
        except ImportError as exc:
            raise RuntimeError(
                "VietOCR chưa được cài.\n"
                "Chạy: pip install vietocr\n"
                f"Chi tiết: {exc}"
            ) from exc

        self._emit(progress_cb, "⬇️ Đang tải VietOCR model (~100MB lần đầu)...")

        config = Cfg.load_config_from_name(self._model_name)
        config["device"] = self._device
        config["predictor"]["beamsearch"] = False   # nhanh hơn, ít RAM hơn

        self._predictor = Predictor(config)
        self._emit(progress_cb, "✅ VietOCR model sẵn sàng!")
        return self._predictor

    @staticmethod
    def _emit(cb, msg: str) -> None:
        if cb is not None:
            try:
                cb(msg)
            except Exception:
                pass
