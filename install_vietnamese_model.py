"""
install_vietnamese_model.py
---------------------------
Tai va cai dat model OCR Tieng Viet (Latin PP-OCRv3) cho Umi-OCR.

Chay: python install_vietnamese_model.py
"""

import io
import os
import sys

# Fix encoding cho Windows console (cp1252 khong support Unicode day du)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import shutil
import tarfile
import urllib.request
from pathlib import Path

# ── Cấu hình ──────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).resolve().parent
MODELS_DIR     = SCRIPT_DIR / "umi-ocr" / "UmiOCR-data" / "plugins" / "win7_x64_PaddleOCR-json" / "models"
CONFIGS_TXT    = MODELS_DIR / "configs.txt"

# Model rec Tiếng Việt / Latin từ PaddleOCR official
REC_MODEL_URL  = "https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/latin_PP-OCRv3_rec_infer.tar"
REC_MODEL_NAME = "latin_PP-OCRv3_rec_infer"

DICT_FILENAME  = "dict_vietnamese.txt"
CONFIG_FILENAME = "config_vietnamese.txt"
CONFIG_LABEL   = "Tiếng Việt"

# ── Dict Tiếng Việt đầy đủ ────────────────────────────────────────────────────
# Bao gồm toàn bộ ký tự Tiếng Việt + ASCII cơ bản + dấu câu
VIETNAMESE_DICT = """ !"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]_`abcdefghijklmnopqrstuvwxyz{|}
ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđƠơƯư
ẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặ
ẸẹẺẻẼẽẾếỀềỂểỄễỆệ
ỈỉỊị
ỌọỎỏỐốỒồổỔỖỗỘộỚớỜờỞởỠỡỢợ
ỤụỦủỨứỪừỬửỮữỰự
ỲỳỴỵỶỷỸỹ
"""

def download_with_progress(url: str, dest: Path) -> None:
    """Tải file với thanh tiến trình."""
    print(f"  Đang tải: {url}")
    print(f"  Lưu vào:  {dest}")
    
    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded / total_size * 100, 100)
            bar = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
            mb_done = downloaded / 1_048_576
            mb_total = total_size / 1_048_576
            print(f"\r  [{bar}] {pct:.1f}% ({mb_done:.1f}/{mb_total:.1f} MB)", end="", flush=True)
    
    urllib.request.urlretrieve(url, dest, reporthook)
    print()  # Newline sau thanh tiến trình


def main():
    print("=" * 60)
    print("  Cài đặt model OCR Tiếng Việt cho Umi-OCR")
    print("=" * 60)
    print()
    
    # Kiểm tra thư mục models tồn tại
    if not MODELS_DIR.exists():
        print(f"[LỖI] Không tìm thấy thư mục models:")
        print(f"      {MODELS_DIR}")
        print("  Hãy chắc chắn script này nằm trong thư mục custom-snipping-tool/")
        sys.exit(1)
    
    print(f"Thư mục models: {MODELS_DIR}")
    print()
    
    # ── Bước 1: Tạo dict Tiếng Việt ───────────────────────────────────────────
    dict_path = MODELS_DIR / DICT_FILENAME
    if dict_path.exists():
        print(f"[OK] Dict đã tồn tại: {DICT_FILENAME}")
    else:
        print(f"[1/4] Tạo file dict Tiếng Việt...")
        chars = set()
        for line in VIETNAMESE_DICT.strip().splitlines():
            for ch in line:
                if ch and ch.strip():
                    chars.add(ch)
        
        # Sắp xếp: ASCII trước, Unicode sau
        sorted_chars = sorted(chars, key=lambda c: (ord(c) > 127, ord(c)))
        dict_path.write_text("\n".join(sorted_chars) + "\n", encoding="utf-8")
        print(f"  → Đã tạo {DICT_FILENAME} ({len(sorted_chars)} ký tự)")
    
    print()
    
    # ── Bước 2: Tải model rec Tiếng Việt (Latin) ──────────────────────────────
    rec_dir = MODELS_DIR / REC_MODEL_NAME
    if rec_dir.exists():
        print(f"[OK] Model rec đã tồn tại: {REC_MODEL_NAME}/")
    else:
        print(f"[2/4] Tải model nhận dạng Latin/Việt từ PaddleOCR...")
        tar_path = MODELS_DIR / f"{REC_MODEL_NAME}.tar"
        
        try:
            download_with_progress(REC_MODEL_URL, tar_path)
        except Exception as e:
            print(f"\n  [LỖI] Không tải được: {e}")
            print("  Kiểm tra kết nối Internet và thử lại.")
            if tar_path.exists():
                tar_path.unlink()
            sys.exit(1)
        
        print(f"  Giải nén...")
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(MODELS_DIR)
        tar_path.unlink()
        print(f"  → Đã giải nén vào: {REC_MODEL_NAME}/")
    
    print()
    
    # ── Bước 3: Tạo config_vietnamese.txt ─────────────────────────────────────
    config_path = MODELS_DIR / CONFIG_FILENAME
    if config_path.exists():
        print(f"[OK] Config đã tồn tại: {CONFIG_FILENAME}")
    else:
        print(f"[3/4] Tạo file cấu hình config_vietnamese.txt...")
        config_content = (
            f"# Tiếng Việt — Latin PP-OCR v3\n\n"
            f"# det 检测模型库\n"
            f"det_model_dir models/ch_PP-OCRv3_det_infer\n\n"
            f"# cls 方向分类器库\n"
            f"cls_model_dir models/ch_ppocr_mobile_v2.0_cls_infer\n\n"
            f"# rec 识别模型库\n"
            f"rec_model_dir models/{REC_MODEL_NAME}\n\n"
            f"# 字典路径\n"
            f"rec_char_dict_path models/{DICT_FILENAME}\n"
        )
        config_path.write_text(config_content, encoding="utf-8")
        print(f"  → Đã tạo {CONFIG_FILENAME}")
    
    print()
    
    # ── Bước 4: Thêm vào configs.txt ──────────────────────────────────────────
    print(f"[4/4] Cập nhật danh sách model (configs.txt)...")
    configs_content = CONFIGS_TXT.read_text(encoding="utf-8")
    
    entry_line = f"{CONFIG_FILENAME} {CONFIG_LABEL}"
    if CONFIG_FILENAME in configs_content:
        print(f"  [OK] '{CONFIG_FILENAME}' đã có trong configs.txt")
    else:
        # Thêm vào đầu danh sách (trước config_chinese.txt)
        new_content = entry_line + "\n" + configs_content
        CONFIGS_TXT.write_text(new_content, encoding="utf-8")
        print(f"  → Đã thêm: {entry_line}")
    
    print()
    print("=" * 60)
    print("  ✅ Cài đặt hoàn tất!")
    print()
    print("  Bước tiếp theo:")
    print("  1. Khởi động lại Umi-OCR nếu đang chạy")
    print("  2. Mở tool chụp hình → OCR Panel → chọn 'Tiếng Việt + Anh'")
    print("  3. Bấm 'Trích xuất văn bản' — dấu Tiếng Việt sẽ được nhận dạng đúng!")
    print("=" * 60)


if __name__ == "__main__":
    main()
