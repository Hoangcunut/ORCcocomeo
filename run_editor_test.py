from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
import sys

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(True)

from PIL import Image
from src.capture_engine import CaptureResult
from src.ui.editor_window import EditorWindow

img = Image.new("RGB", (800, 600), "white")
result = CaptureResult(image=img, mode='Rectangle', filepath='test.png', timestamp='2026')
editor = EditorWindow(result)
editor.show()
sys.exit(app.exec())
