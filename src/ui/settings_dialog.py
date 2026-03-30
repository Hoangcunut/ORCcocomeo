"""
settings_dialog.py
------------------
Hộp thoại Cài đặt (đổi phím tắt chụp màn hình).
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QMessageBox
)

from src.utils.settings import AppSettings

class HotkeyInput(QLineEdit):
    """Widget tùy chỉnh để bắt sự kiện người dùng gõ phím."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.modifiers = []
        self.key = ""
        self.setStyleSheet("""
            QLineEdit {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QLineEdit:focus {
                border-color: #0078D4;
            }
        """)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        # Bỏ qua nếu chỉ bấm phím bổ trợ
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return super().keyPressEvent(event)

        # Trích xuất modifiers
        mods = event.modifiers()
        self.modifiers = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            self.modifiers.append("<ctrl>")
        if mods & Qt.KeyboardModifier.AltModifier:
            self.modifiers.append("<alt>")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            self.modifiers.append("<shift>")
        # Pynput dùng <cmd> cho Win key
        if mods & Qt.KeyboardModifier.MetaModifier:
            self.modifiers.append("<cmd>")

        # Xử lý phím chính
        key_str = ""
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            key_str = chr(key).lower()
        elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            key_str = chr(key)
        # Các phím đặc biệt mapping
        else:
            special_keys = {
                Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
                Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
                Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
                Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
                Qt.Key.Key_Print: "print_screen",
                Qt.Key.Key_Home: "home",
                Qt.Key.Key_End: "end",
                Qt.Key.Key_Insert: "insert",
            }
            if key in special_keys:
                key_str = special_keys[key]

        if key_str:
            self.key = key_str
            display_mods = [m.strip("<>") for m in self.modifiers]
            display_str = " + ".join(display_mods + [self.key]).upper()
            self.setText(display_str)


class SettingsDialog(QDialog):
    """Cửa sổ cài đặt."""
    
    hotkey_changed = pyqtSignal(list, str) # modifiers, key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cài đặt")
        self.setFixedSize(320, 160)
        self.setStyleSheet("background-color: #202020; color: white;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QLabel("Nhấn tổ hợp phím tắt mới để đổi:")
        lbl.setStyleSheet("font-size: 13px; color: #E0E0E0;")
        layout.addWidget(lbl)
        
        self.hotkey_input = HotkeyInput()
        
        # Load giá trị hiện tại
        current_mods = AppSettings.get("hotkey_modifiers")
        current_key = AppSettings.get("hotkey_key")
        self.hotkey_input.modifiers = list(current_mods)
        self.hotkey_input.key = current_key
        
        display_mods = [m.strip("<>") for m in current_mods]
        display_str = " + ".join(display_mods + [current_key]).upper()
        self.hotkey_input.setText(display_str)
        
        layout.addWidget(self.hotkey_input)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        
        btn_save = QPushButton("Lưu")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0078D4; 
                border-radius: 4px; 
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1888E0; }
        """)
        btn_save.clicked.connect(self.save)
        
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,20); }
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)

    def save(self):
        if not self.hotkey_input.key:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập một phím tắt hợp lệ (Ví dụ: Alt+Shift+S).")
            return
            
        AppSettings.set("hotkey_modifiers", self.hotkey_input.modifiers)
        AppSettings.set("hotkey_key", self.hotkey_input.key)
        self.hotkey_changed.emit(self.hotkey_input.modifiers, self.hotkey_input.key)
        self.accept()
