import sys
sys.path.insert(0, '.')
from PyQt6.QtWidgets import QApplication
from src.capture_engine import CaptureResult
from PIL import Image
import os

def run_test():
    app = QApplication(sys.argv)
    
    # Tạo một ảnh dummy 100x100
    img = Image.new('RGB', (100, 100), color = 'red')
    class DummyResult:
        def __init__(self, image):
            self.image = image
            self.mode = "Rectangle"
            
    res = DummyResult(img)
    
    try:
        from src.ui.editor_window import EditorWindow
        win = EditorWindow(res)
        
        # Test phase 1: Engine refresh
        win._refresh_engine_status()
        
        # Get labels
        print("Mã trạng thái trả về (OCR Status):", win._lbl_engine_status.text())
        print("Tesseract enabled:", win._rb_tess.isEnabled())
        print("Umi-OCR enabled:", win._rb_umi.isEnabled())
        
        print("Phase 1 test passed: UI logic initialized correctly without crashing.")
    except Exception as e:
        print("Test failed with exception:", e)
        sys.exit(1)

if __name__ == "__main__":
    run_test()
