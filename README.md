# Custom Snipping Tool

Công cụ chụp màn hình cho Windows 10 với giao diện Fluent Design, OCR offline và quay video.

## Giai đoạn hiện tại: 1 — MVP Capture ✅

### Tính năng Giai đoạn 1
- ✅ Overlay mờ toàn màn hình khi chọn vùng
- ✅ Toolbar nổi Fluent-style (dark mode)
- ✅ Chế độ: Rectangle, Fullscreen, Window*, Freeform* (*placeholder)
- ✅ Delay: 0s / 3s / 5s / 10s
- ✅ Auto copy vào Clipboard sau khi chụp
- ✅ Lưu PNG tạm (temp/last_screenshot.png)
- ✅ Cửa sổ Editor xem ảnh (zoom, lưu As, copy)
- ✅ System Tray icon
- ✅ Global Hotkey: **Alt+Shift+S**

> ⚠️ Windows 10 chiếm Win+Shift+S cho Snipping Tool gốc,  
> nên ta dùng **Alt+Shift+S** mặc định.

## Cài đặt

```bash
# 1. Tạo môi trường ảo
python -m venv .venv
.venv\Scripts\activate

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Chạy
python main.py
```

## Cấu trúc thư mục

```
custom-snipping-tool/
├── main.py               # Entry point
├── requirements.txt
├── build.bat             # Script build .exe (Giai đoạn 5)
├── README.md
├── temp/                 # Ảnh tạm sau khi chụp
├── assets/               # Icon, ảnh
└── src/
    ├── config.py         # Hằng số, cấu hình
    ├── capture_engine.py # Engine chụp ảnh (mss + Pillow)
    ├── hotkey_manager.py # Global hotkey (pynput)
    └── ui/
        ├── overlay.py        # Overlay mờ chọn vùng
        ├── toolbar.py        # Toolbar Fluent-style
        └── editor_window.py  # Cửa sổ xem/chỉnh sửa ảnh
```

## Lộ trình phát triển

| Giai đoạn | Tính năng | Trạng thái |
|-----------|-----------|------------|
| 1 | MVP Capture + UI Overlay | ✅ Hoàn thành |
| 2 | OCR (DeepSeek via Ollama) + Basic Edit | ⬜ Chưa làm |
| 3 | Advanced Edit + Shapes | ⬜ Chưa làm |
| 4 | Video Recording | ⬜ Chưa làm |
| 5 | Polish + Build .exe | ⬜ Chưa làm |

## OCR Backend (Giai đoạn 2)

Tích hợp [local_ai_ocr](https://github.com/th1nhhdk/local_ai_ocr) qua Ollama API:
- Cài và chạy Ollama với model `deepseek-ocr:3b`
- Tool gọi `POST http://127.0.0.1:11435/api/chat` để OCR ảnh
- Hoàn toàn offline sau lần cài đầu tiên

## Phím tắt

| Phím | Hành động |
|------|-----------|
| Alt+Shift+S | Kích hoạt chụp vùng (toàn hệ thống) |
| Escape | Hủy chọn vùng |
| Ctrl+S | Lưu ảnh (trong Editor) |
| Ctrl+C | Copy ảnh (trong Editor) |
| Ctrl+Scroll | Zoom ảnh (trong Editor) |
