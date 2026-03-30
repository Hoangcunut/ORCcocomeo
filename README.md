# OCR Image Viewer — Custom Snipping Tool

> Bộ công cụ chụp màn hình + OCR Tiếng Việt cho Windows, tích hợp lớp text overlay có thể bôi đen và copy trực tiếp trên ảnh như trình duyệt web.

---

## Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 📸 **Chụp màn hình** | Hotkey `Alt+Shift+S`, chọn vùng, fullscreen |
| ✏️ **Editor ảnh** | Highlight, bút vẽ, tẩy, redact (che chữ), crop |
| 🔍 **OCR đa engine** | Umi-OCR (PaddleOCR), Tesseract, VietOCR — tự động fallback |
| 🇻🇳 **VietOCR Overlay** | Text layer trong suốt → bôi đen → Ctrl+C copy đúng dấu |
| 🖼️ **Standalone Viewer** | Mở ảnh → OCR → overlay — không cần chụp màn hình |
| 📦 **Offline, portable** | Không cần internet sau lần cài model đầu tiên |

---

## Cấu trúc dự án

```
custom-snipping-tool/
│
├── main.py                        # Entry point: Snipping Tool (System Tray + Hotkey)
├── requirements.txt               # Danh sách thư viện
├── build_installer.py             # Script build .exe (PyInstaller)
├── build.bat                      # Build nhanh qua Batch
├── install_vietnamese_model.py    # Tải tessdata Tiếng Việt cho Tesseract
├── .gitignore
│
├── ocr_viewer/                    # ★ Standalone OCR Image Viewer
│   ├── __init__.py
│   ├── main.py                    # Entry point viewer: file dialog / CLI arg
│   └── viewer_app.py              # ViewerApp + SplashWindow (loading + preview)
│
└── src/
    ├── config.py                  # Hằng số, biến môi trường, cấu hình engine
    ├── capture_engine.py          # Engine chụp ảnh (mss + Pillow)
    ├── hotkey_manager.py          # Global hotkey: Alt+Shift+S (pynput)
    ├── ocr_engine.py              # OCR facade: OcrEngine + OcrWorker (QThread)
    ├── vietocr_engine.py          # VietOCR engine: detect (Tesseract) + recognize (VietOCR)
    ├── umi_ocr_manager.py         # Quản lý tiến trình Umi-OCR
    └── ui/
        ├── overlay.py             # Overlay mờ toàn màn hình khi chọn vùng
        ├── toolbar.py             # Toolbar Fluent-style nổi trên màn hình
        ├── editor_window.py       # Cửa sổ chỉnh sửa ảnh + OCR panel
        └── ocr_overlay_window.py  # Cửa sổ xem ảnh + text overlay (QWebEngineView)
```

---

## Cài đặt & Chạy

### Yêu cầu hệ thống
- Windows 10 / 11
- Python 3.10+

### Bước 1 — Tạo môi trường ảo

```bash
cd custom-snipping-tool
python -m venv .venv
.venv\Scripts\activate
```

### Bước 2 — Cài thư viện

```bash
pip install -r requirements.txt
```

> ⚠️ **VietOCR cần PyTorch.** Cài CPU-only (nhẹ hơn ~500MB so với GPU):
> ```bash
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
> pip install vietocr
> ```

### Bước 3 — Cài Tesseract (engine phát hiện vùng chữ)

1. Tải tại: https://github.com/UB-Mannheim/tesseract/wiki
2. Cài và thêm vào PATH, hoặc đặt `tesseract.exe` vào thư mục `tesseract/`
3. Cài tessdata Tiếng Việt:
   ```bash
   python install_vietnamese_model.py
   ```

### Bước 4 — Chạy ứng dụng

**Snipping Tool (System Tray):**
```bash
python main.py
```

**Standalone OCR Viewer:**
```bash
# Mở file dialog chọn ảnh
python ocr_viewer/main.py

# Mở trực tiếp một file ảnh
python ocr_viewer/main.py path/to/image.png
```

---

## Hướng dẫn sử dụng

### Chụp màn hình & OCR

1. Nhấn `Alt+Shift+S` (toàn hệ thống) → overlay xuất hiện
2. Kéo chuột chọn vùng → Editor mở ra
3. Trong Editor, mở **OCR Panel** (góc trên phải)
4. Chọn engine:
   - `⚡ Auto` — Tự động thử Umi-OCR trước, fallback Tesseract
   - `🔒 Tesseract` — Offline, bảo mật tối đa
   - `🇻🇳 VietOCR` — Tiếng Việt chính xác đầy đủ dấu, có overlay
5. Bấm **Trích xuất văn bản**
6. Nếu chọn VietOCR → nút **📄 Xem Overlay** hiện ra → bấm để mở

### Sử dụng OCR Overlay

Trong cửa sổ **OCR Overlay Viewer**:

| Thao tác | Kết quả |
|----------|---------|
| Kéo chuột trên text | Bôi đen từng đoạn |
| `Ctrl+A` | Chọn toàn bộ text |
| `Ctrl+C` | Copy text đã chọn |
| Nút **📋 Copy All** | Copy toàn bộ kết quả nhận dạng |
| `Ctrl++` / `Ctrl+-` | Zoom in / out |
| `Ctrl+0` | Về kích thước gốc |
| Kéo thanh tiêu đề | Di chuyển cửa sổ tự do |
| `Escape` / `Ctrl+W` | Đóng overlay |

### Standalone Viewer

```
OCRViewer.exe                      → Mở File Dialog
OCRViewer.exe C:\path\to\img.png   → Mở thẳng ảnh
```

**Định dạng hỗ trợ:** PNG, JPG, JPEG, BMP, WEBP, TIFF, GIF

Recent files được lưu tại `~/.ocrviewer_recent`.

---

## OCR Engines

| Engine | Ưu điểm | Nhược điểm | Khi nào dùng |
|--------|----------|------------|--------------|
| **Umi-OCR** | Nhanh, PaddleOCR chính xác, UI riêng | Cần cài thêm portable | Hình ảnh đa ngôn ngữ |
| **Tesseract** | Offline, nhẹ, bảo mật tối đa | Tiếng Việt đôi khi sai dấu | Cần bảo mật, không cài Umi |
| **VietOCR** ⭐ | Tiếng Việt chính xác đầy đủ dấu, có overlay | Cần download model ~100MB lần đầu | Tài liệu Tiếng Việt |

### Cài Umi-OCR (optional)

1. Tải portable tại: https://github.com/hiroi-sora/Umi-OCR/releases
2. Giải nén vào thư mục `umi-ocr/`
3. Chạy `UmiOCR.exe` một lần để khởi động server

---

## Build .exe

### Yêu cầu

```bash
pip install pyinstaller
```

### Lệnh build

```bash
# Build OCR Image Viewer standalone (mặc định)
python build_installer.py

# Build Snipping Tool
python build_installer.py --snipping

# Build cả hai
python build_installer.py --all
```

Output: `dist/OCRViewer.exe` và/hoặc `dist/SnippingTool.exe`

> ⚠️ File `.exe` sẽ nặng (~500MB–1.5GB) do bundle PyTorch + VietOCR.
> Distribute qua **GitHub Releases** (hỗ trợ file tới 2GB).

---

## Phím tắt

### Toàn hệ thống

| Phím | Hành động |
|------|-----------|
| `Alt+Shift+S` | Kích hoạt chụp vùng |

### Trong Editor

| Phím | Hành động |
|------|-----------|
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo |
| `Ctrl+C` | Copy ảnh vào clipboard |
| `Ctrl+S` | Lưu ảnh |
| `Ctrl+Scroll` | Zoom canvas |
| `H` | Highlight tool |
| `P` | Bút vẽ |
| `E` | Eraser |
| `R` | Redact (hộp đen) |
| `C` | Crop |
| `Escape` | Đóng Editor |

### Trong OCR Overlay

| Phím | Hành động |
|------|-----------|
| `Ctrl+A` | Chọn tất cả text |
| `Ctrl+C` | Copy text đã chọn |
| `Ctrl+Shift+C` | Copy toàn bộ text |
| `Ctrl++` | Zoom in |
| `Ctrl+-` | Zoom out |
| `Ctrl+0` | Kích thước gốc |
| `Escape` | Đóng overlay |

---

## Lộ trình

| Giai đoạn | Tính năng | Trạng thái |
|-----------|-----------|------------|
| 1 | MVP Capture + UI Overlay | ✅ Hoàn thành |
| 2 | Dual-engine OCR (Umi + Tesseract) | ✅ Hoàn thành |
| 3 | VietOCR Overlay (bôi đen text trên ảnh) | ✅ Hoàn thành |
| 4 | Standalone OCR Viewer | ✅ Hoàn thành |
| 5 | Build .exe + phân phối | ✅ Hoàn thành |

---

## Cấu hình nâng cao (`src/config.py`)

| Biến môi trường | Mặc định | Mô tả |
|----------------|---------|-------|
| `VIETOCR_MODEL` | `vgg_transformer` | Model VietOCR (`vgg_seq2seq` = nhanh hơn) |
| `VIETOCR_DEVICE` | `cpu` | `cpu` hoặc `cuda` nếu có GPU |
| `OCR_ENGINE` | `auto` | Engine mặc định: `auto`, `umi_only`, `tess_only`, `vietocr` |
| `TESSERACT_PATH` | (tự tìm) | Đường dẫn tới `tesseract.exe` |
| `UMI_OCR_HOST` | `127.0.0.1:1224` | Host của Umi-OCR HTTP server |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'PyQt6'`**
```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

**VietOCR lần đầu chậm / timeout**
> Model ~100MB cần tải lần đầu. Cần internet. Sau đó hoàn toàn offline.

**Tesseract không nhận diện đúng dấu Tiếng Việt**
> Dùng engine `VietOCR` thay thế. Hoặc đảm bảo đã cài `tessdata/vie.traineddata`.

**Umi-OCR không kết nối được**
> Mở `umi-ocr/UmiOCR.exe` thủ công trước, hoặc chuyển sang engine `Tesseract`.

**Overlay text lệch so với ảnh**
> Ảnh quá lớn (>4096px) đã được scale down tự động. Đây là trade-off để giảm RAM.

---

## Đóng góp

1. Fork repo: https://github.com/Hoangcunut/ORCcocomeo
2. Tạo branch mới: `git checkout -b feature/ten-tinh-nang`
3. Chạy thử: `python main.py` hoặc `python ocr_viewer/main.py`
4. Commit và Pull Request

---

*Maintained by [@Hoangcunut](https://github.com/Hoangcunut)*
