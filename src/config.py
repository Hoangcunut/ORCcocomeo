"""
config.py
---------
Hằng số và cấu hình toàn cục cho Custom Snipping Tool.
Tách riêng để dễ chỉnh sửa sau này mà không ảnh hưởng logic.
"""

from __future__ import annotations

import os
from pathlib import Path

# ─── Thông tin ứng dụng ──────────────────────────────────────────────────────

APP_NAME: str = "Custom Snipping Tool"
APP_VERSION: str = "0.1.0"
APP_AUTHOR: str = "Custom"

# ─── Đường dẫn ───────────────────────────────────────────────────────────────

import sys

# Thư mục gốc dự án
if getattr(sys, 'frozen', False):
    # Khi chạy dạng PyInstaller compiled
    PROJECT_ROOT: Path = Path(sys.executable).parent
else:
    # Khi chạy dev mode
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# Thư mục lưu ảnh tạm thời
TEMP_DIR: Path = PROJECT_ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# Đường dẫn file ảnh tạm sau mỗi lần chụp
TEMP_SCREENSHOT: Path = TEMP_DIR / "last_screenshot.png"

# Thư mục assets (icon, ...)
ASSETS_DIR: Path = PROJECT_ROOT / "assets"

# Thiết lập biến môi trường TORCH_HOME để lưu tải trọng VietOCR vào engines/vietocr/.cache
os.environ["TORCH_HOME"] = str(PROJECT_ROOT / "engines" / "vietocr" / ".cache")

# ─── OCR Engine Configuration ────────────────────────────────────────────────

# ── Umi-OCR ──────────────────────────────────────────────────────────────────
# Port HTTP API mặc định của Umi-OCR
UMI_OCR_HOST: str = os.environ.get("UMI_OCR_HOST", "127.0.0.1:1224")

# Đường dẫn tới Umi-OCR.exe (tìm trong engines/, sau đó fallback dev mode)
_UMI_OCR_BUNDLE: Path = PROJECT_ROOT / "engines" / "umi-ocr" / "Umi-OCR.exe"
_UMI_OCR_DEV: Path = PROJECT_ROOT / "umi-ocr" / "Umi-OCR.exe"

if _UMI_OCR_BUNDLE.exists():
    UMI_OCR_EXE_PATH: Path | None = _UMI_OCR_BUNDLE
elif _UMI_OCR_DEV.exists():
    UMI_OCR_EXE_PATH = _UMI_OCR_DEV
else:
    UMI_OCR_EXE_PATH = None

# Timeout khi gọi API (giây)
UMI_OCR_CONNECT_TIMEOUT: float = 5.0
UMI_OCR_READ_TIMEOUT: float    = 60.0

# ── Tesseract ─────────────────────────────────────────────────────────────────
# Tìm tesseract.exe trong engines/tesseract/, fallback dev/, fallback system
_TESS_BUNDLE: Path = PROJECT_ROOT / "engines" / "tesseract" / "tesseract.exe"
_TESS_DEV: Path = PROJECT_ROOT / "tesseract" / "tesseract.exe"
_TESS_PROGFILE: Path = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")

if _TESS_BUNDLE.exists():
    TESSERACT_EXE_PATH: str | None = str(_TESS_BUNDLE)
elif _TESS_DEV.exists():
    TESSERACT_EXE_PATH = str(_TESS_DEV)
elif _TESS_PROGFILE.exists():
    TESSERACT_EXE_PATH = str(_TESS_PROGFILE)
else:
    TESSERACT_EXE_PATH = None

# Thư mục tessdata chứa file .traineddata
_TESS_DATA_BUNDLE: Path = PROJECT_ROOT / "engines" / "tesseract" / "tessdata"
_TESS_DATA_DEV: Path = PROJECT_ROOT / "tesseract" / "tessdata"

if _TESS_DATA_BUNDLE.exists():
    TESSERACT_DATA_DIR: str | None = str(_TESS_DATA_BUNDLE)
elif _TESS_DATA_DEV.exists():
    TESSERACT_DATA_DIR = str(_TESS_DATA_DEV)
else:
    TESSERACT_DATA_DIR = None

# ── Ngôn ngữ OCR ─────────────────────────────────────────────────────────────
# Ánh xạ: tên hiển thị → (tesseract_lang_code, umi_ocr_language_path)
# tesseract_lang: dùng dấu + để ghép nhiều ngôn ngữ (vd: "vie+eng")
# umi_ocr_language: giá trị "ocr.language" gửi đến Umi-OCR API,
#   phải khớp với path model trong file configs.txt của plugin PaddleOCR.
#   Bundle hiện tại hỗ trợ: config_chinese.txt, config_en.txt,
#     config_chinese_cht.txt, config_japan.txt, config_korean.txt, config_cyrillic.txt
#
#   ⚠️  Tiếng Việt ("models/config_vietnamese.txt") chưa có trong bundle này.
#   Để OCR Tiếng Việt có dấu chính xác, cần thực hiện 1 trong 2 cách:
#     A. Trong Umi-OCR: vào Settings → Plugin → Download thêm model Vietnamese
#        (file sẽ là config_vietnamese.txt trong thư mục models của plugin)
#     B. Dùng Tesseract (chọn chế độ "Chỉ Tesseract" trong OCR panel)
#        với cài đặt việt nếu có (vie.traineddata)
OCR_LANGUAGES: list[dict] = [
    {
        "label": "Tiếng Việt + Anh",
        "tess": "vie+eng",
        "umi": "models/config_vietnamese.txt",  # Cần cài model Vietnamese trong Umi-OCR
    },
    {
        "label": "Tiếng Anh",
        "tess": "eng",
        "umi": "models/config_en.txt",
    },
    {
        "label": "Tiếng Việt",
        "tess": "vie",
        "umi": "models/config_vietnamese.txt",  # Cần cài model Vietnamese trong Umi-OCR
    },
    {
        "label": "Tiếng Trung (Giản)",
        "tess": "chi_sim+eng",
        "umi": "models/config_chinese.txt",
    },
    {
        "label": "Tiếng Trung (Phồn)",
        "tess": "chi_tra+eng",
        "umi": "models/config_chinese_cht.txt",
    },
    {
        "label": "Tiếng Nhật",
        "tess": "jpn+eng",
        "umi": "models/config_japan.txt",
    },
    {
        "label": "Đa ngôn ngữ (Vi+En+Zh+Ja)",
        "tess": "vie+eng+chi_sim+jpn",
        "umi": "models/config_vietnamese.txt",  # Cần cài model Vietnamese trong Umi-OCR
    },
]

# Ngôn ngữ mặc định khi mở app (index vào OCR_LANGUAGES)
OCR_DEFAULT_LANG_INDEX: int = 0

# ── Engine preference ─────────────────────────────────────────────────────────
# "auto"      → thử Umi-OCR trước, fallback Tesseract
# "umi_only"  → chỉ Umi-OCR
# "tess_only" → chỉ Tesseract (bảo mật tối đa, không cần server)
# "vietocr"   → VietOCR (Tiếng Việt chính xác + overlay)
OCR_ENGINE_PREFERENCE: str = os.environ.get("OCR_ENGINE", "auto")

# ── VietOCR ───────────────────────────────────────────────────────────────────
# Model name: "vgg_seq2seq" (nhanh, nhẹ) hoặc "vgg_transformer" (chính xác hơn)
VIETOCR_MODEL: str = os.environ.get("VIETOCR_MODEL", "vgg_transformer")
# Device: "cpu" (portable, không cần GPU) hoặc "cuda" (nhanh hơn nếu có NVIDIA GPU)
VIETOCR_DEVICE: str = os.environ.get("VIETOCR_DEVICE", "cpu")

# ─── Phím tắt hệ thống ───────────────────────────────────────────────────────

# Lưu ý: Win+Shift+S bị Windows chiếm, ta dùng Alt+Shift+S mặc định.
# Người dùng có thể đổi ở Settings (Giai đoạn 5).
DEFAULT_HOTKEY_MODIFIERS: tuple[str, ...] = ("<alt>", "<shift>")
DEFAULT_HOTKEY_KEY: str = "s"

# ─── Tuỳ chọn chụp ───────────────────────────────────────────────────────────

# Các chế độ chụp
CAPTURE_MODES: list[str] = [
    "Rectangle",   # Vùng chữ nhật kéo chuột
    "Fullscreen",  # Toàn màn hình
    "Window",      # Cửa sổ đang focus (Giai đoạn 2 hoàn thiện)
    "Freeform",    # Vẽ tự do (Giai đoạn 2 hoàn thiện)
]

# Thời gian trễ (giây) trước khi chụp
CAPTURE_DELAYS: list[int] = [0, 3, 5, 10]

# ─── UI / Giao diện ──────────────────────────────────────────────────────────

# Màu overlay mờ phủ màn hình (RGBA)
OVERLAY_COLOR: tuple[int, int, int, int] = (0, 0, 0, 120)

# Màu viền vùng chọn
SELECTION_BORDER_COLOR: str = "#0078D4"   # Windows Blue
SELECTION_FILL_COLOR: str = "rgba(0, 120, 212, 30)"

# Chiều cao toolbar nổi
TOOLBAR_HEIGHT: int = 52

# ─── Theme ───────────────────────────────────────────────────────────────────

# "auto" → theo system, "dark" / "light" → ép buộc
THEME: str = "auto"
