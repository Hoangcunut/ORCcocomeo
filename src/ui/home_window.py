"""
home_window.py
--------------
Màn hình Chính (Dashboard) của ứng dụng giống trải nghiệm Windows Snipping Tool.
Chứa các tùy chọn chụp và phím bấm nhanh.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QComboBox, QMenu, QToolButton, QFrame
)

from src.capture_engine import CaptureMode
from src.config import CAPTURE_DELAYS
from src.utils.settings import AppSettings
from src.ui.settings_dialog import SettingsDialog

class HomeWindow(QWidget):
    """Màn hình chính chứa các nút New, Cài đặt và Hiển thị phím tắt."""
    
    # Phát sự kiện chụp
    capture_requested = pyqtSignal(object, int) # CaptureMode, delay_seconds
    # Phát sự kiện phím tắt thay đổi
    hotkey_changed_signal = pyqtSignal(list, str) # modifiers, key
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Snipping Tool")
        self.setFixedSize(600, 350)
        self.setStyleSheet("""
            QWidget {
                background-color: #F3F3F3;
                color: #202020;
                font-family: "Segoe UI";
            }
            QFrame#top_bar {
                background-color: #F8F8F8;
                border-bottom: 1px solid #E0E0E0;
            }
            QPushButton#btn_new {
                background-color: #0078D4; 
                color: white; 
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }
            QPushButton#btn_new:hover {
                background-color: #1888E0;
            }
            QComboBox {
                background-color: white;
                border: 1px solid #CCC;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 13px;
                color: #202020;
            }
            QComboBox::drop-down {
                border-left: 1px solid #CCC;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #666;
            }
            QToolButton#btn_settings {
                background: transparent;
                color: #333;
                font-size: 18px;
                border: none;
                font-weight: bold;
                padding: 0px 8px;
            }
            QToolButton#btn_settings:hover {
                background-color: #E0E0E0;
                border-radius: 4px;
            }
            QLabel#main_text {
                font-size: 18px;
                color: #404040;
            }
            QLabel#bold_key {
                font-size: 18px;
                font-weight: bold;
                color: #202020;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ─── Top Bar ───
        top_bar = QFrame(self)
        top_bar.setObjectName("top_bar")
        top_bar.setFixedHeight(56)
        
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 0, 16, 0)
        top_layout.setSpacing(12)
        
        # Nút + New
        self.btn_new = QPushButton("＋ New")
        self.btn_new.setObjectName("btn_new")
        self.btn_new.clicked.connect(self._on_new_clicked)
        top_layout.addWidget(self.btn_new)
        
        # Chế độ
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("▭ Kéo chữ nhật", CaptureMode.RECTANGLE)
        self.combo_mode.addItem("🪟 Cửa sổ", CaptureMode.WINDOW)
        self.combo_mode.addItem("🖥 Toàn màn hình", CaptureMode.FULLSCREEN)
        self.combo_mode.addItem("✏ Tự do", CaptureMode.FREEFORM)
        top_layout.addWidget(self.combo_mode)
        
        # Delay
        self.combo_delay = QComboBox()
        self.combo_delay.addItem("⏱ Không chậm trễ", 0)
        self.combo_delay.addItem("⏱ 3 giây", 3)
        self.combo_delay.addItem("⏱ 5 giây", 5)
        self.combo_delay.addItem("⏱ 10 giây", 10)
        top_layout.addWidget(self.combo_delay)
        
        top_layout.addStretch()
        
        # Nút Settings
        self.btn_settings = QToolButton()
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.setText("⋯")
        self.btn_settings.setToolTip("Cài đặt phím tắt")
        self.btn_settings.clicked.connect(self._open_settings)
        top_layout.addWidget(self.btn_settings)
        
        main_layout.addWidget(top_bar)
        
        # ─── Body Center ───
        body = QWidget()
        body.setStyleSheet("background-color: #F8F8F8;")
        body_layout = QVBoxLayout(body)
        body_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_instruction = QLabel()
        self.lbl_instruction.setObjectName("main_text")
        self.lbl_instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_instruction_text()
        
        body_layout.addWidget(self.lbl_instruction)
        main_layout.addWidget(body)

    def _update_instruction_text(self):
        """Cập nhật Label text theo hotkey hiện tại đang được lưu."""
        mods = AppSettings.get("hotkey_modifiers", [])
        key = AppSettings.get("hotkey_key", "")
        display_mods = [m.strip("<>") for m in mods]
        hk_str = " + ".join(display_mods + [key]).upper()
        
        # Format HTML để in đậm hotkey
        self.lbl_instruction.setText(f"Nhấn <span style='font-weight:bold; color: #000;'>{hk_str}</span> để bắt đầu chụp")
        
    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.hotkey_changed.connect(self._on_hotkey_changed)
        dlg.exec()

    def _on_hotkey_changed(self, modifiers, key):
        self._update_instruction_text()
        self.hotkey_changed_signal.emit(modifiers, key)

    def _on_new_clicked(self):
        mode = self.combo_mode.currentData()
        delay = self.combo_delay.currentData()
        self.capture_requested.emit(mode, delay)

    def closeEvent(self, event):
        """Override closeEvent: thay vì thoát App, chỉ ẩn (Hide) cửa sổ để chạy ngầm."""
        event.ignore()
        self.hide()
