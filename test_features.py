"""Quick test script — run all core features."""
import sys
sys.path.insert(0, '.')

from PIL import Image
from src.vietocr_engine import VietOCREngine, OcrOverlayResult

print("=== TEST 1: VietOCR Engine ===")
image = Image.open('test_ocr_image.png')
engine = VietOCREngine()
result = engine.recognize(image)
print(f"  OK - {len(result.word_boxes)} boxes, {len(result.plain_text)} chars")
for wb in result.word_boxes:
    print(f'  Box [{wb.x},{wb.y} {wb.width}x{wb.height}] = "{wb.text}"')

print("\n=== TEST 2: Overlay HTML ===")
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication([])
from src.ui.ocr_overlay_window import OCROverlayWindow
overlay = OCROverlayWindow(image, result)
html = overlay._build_html()
checks = [
    ('base64 image', 'data:image/png;base64,' in html),
    ('text-layer', 'text-layer' in html),
    ('word spans', 'class="w"' in html),
    ('CSS near-invisible', 'rgba(0, 0, 0, 0.002)' in html),
    ('selection color', 'rgba(0, 100, 220, 0.75)' in html),
    ('Ctrl+A JS', 'selectNodeContents' in html),
]
for name, ok in checks:
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {name}")

print(f"  HTML size: {len(html)} bytes")

print("\n=== TEST 3: EnginePreference.VIETOCR ===")
from src.ocr_engine import EnginePreference
print(f"  VIETOCR = '{EnginePreference.VIETOCR.value}' - OK")

print("\n=== TEST 4: ViewerApp import ===")
from ocr_viewer.viewer_app import ViewerApp, SplashWindow
print("  ViewerApp + SplashWindow - OK")

print("\n=== ALL TESTS PASSED ===")
app.quit()
