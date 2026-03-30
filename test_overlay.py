import sys
from PyQt6.QtWidgets import QApplication
from src.ui.overlay import ScreenOverlay
app = QApplication(sys.argv)
ov = ScreenOverlay()
print("Thử khởi tạo thành công Overlay mới!")
