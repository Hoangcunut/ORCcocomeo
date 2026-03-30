import sys
from PyQt6.QtWidgets import QApplication
from src.ui.home_window import HomeWindow
app = QApplication(sys.argv)
hw = HomeWindow()
print("Thử khởi tạo thành công Cửa sổ Dashboard mới!")
