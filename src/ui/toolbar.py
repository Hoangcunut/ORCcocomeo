"""
toolbar.py
----------
Toolbar nổi Fluent-style cho Custom Snipping Tool.
Hiển thị khi ứng dụng khởi động hoặc sau khi chụp xong.

Nút chức năng Giai đoạn 1:
  - Chế độ chụp: Rectangle | Fullscreen | Window | Freeform
  - Delay: 0s | 3s | 5s | 10s
  - Nút "Capture" (hoặc bấm phím tắt)
  - Nút thu vào khay hệ thống (minimise to tray)

Thiết kế:
  - Nền glassmorphism tối/sáng tuỳ theme
  - Bo góc mượt, shadow nhẹ
  - Responsive với hover animation (QPalette + StyleSheet)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from src.config import (
    CAPTURE_DELAYS,
    CAPTURE_MODES,
    TOOLBAR_HEIGHT,
)
from src.capture_engine import CaptureMode

# ─── Ánh xạ tên hiển thị → CaptureMode ──────────────────────────────────────
_MODE_MAP: dict[str, CaptureMode] = {
    "Rectangle": CaptureMode.RECTANGLE,
    "Fullscreen": CaptureMode.FULLSCREEN,
    "Window":     CaptureMode.WINDOW,
    "Freeform":   CaptureMode.FREEFORM,
}

# ─── StyleSheet Toolbar ───────────────────────────────────────────────────────
_TOOLBAR_STYLE = """
QWidget#toolbar_root {
    background-color: rgba(22, 22, 26, 235);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 30);
}

/* ── Nút chế độ chụp ── */
QToolButton {
    background: transparent;
    color: #F0F0F0;
    border: none;
    border-radius: 6px;
    padding: 5px 11px;
    font-size: 13px;
    font-weight: 500;
}
QToolButton:hover {
    background-color: rgba(255, 255, 255, 22);
    color: #FFFFFF;
}
QToolButton:checked {
    background-color: #0078D4;
    color: #FFFFFF;
    font-weight: bold;
}

/* ── Nút thu tray (—) ── */
QToolButton#btn_tray {
    color: #CCCCCC;
    font-size: 16px;
    padding: 2px 10px;
    border-radius: 6px;
}
QToolButton#btn_tray:hover {
    background-color: rgba(255,255,255,18);
    color: #FFFFFF;
}

/* ── Nút tắt (X) ── */
QToolButton#btn_close {
    color: #FF6B6B;
    font-size: 15px;
    font-weight: bold;
    padding: 2px 10px;
    border-radius: 6px;
}
QToolButton#btn_close:hover {
    background-color: #C0392B;
    color: #FFFFFF;
}

/* ── ComboBox delay ── */
QComboBox {
    background-color: rgba(255, 255, 255, 12);
    color: #F0F0F0;
    border: 1px solid rgba(255, 255, 255, 35);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
    min-width: 72px;
}
QComboBox QAbstractItemView {
    background-color: #2D2D2D;
    color: #F0F0F0;
    selection-background-color: #0078D4;
    border-radius: 4px;
    padding: 2px;
}
QComboBox::drop-down { border: none; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #CCCCCC;
    margin-right: 6px;
}

/* ── Nút Capture ── */
QPushButton#btn_capture {
    background-color: #0078D4;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 20px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#btn_capture:hover {
    background-color: #1888E0;
}
QPushButton#btn_capture:pressed {
    background-color: #005FA3;
}
QPushButton#btn_capture:disabled {
    background-color: #3A3A3A;
    color: #888888;
}

/* ── Nhãn chữ (Delay, separator...) ── */
QLabel {
    color: #C8C8C8;
    font-size: 12px;
}
QLabel#lbl_sep {
    color: rgba(255, 255, 255, 55);
    font-size: 20px;
    padding: 0 2px;
}
"""


class SnippingToolbar(QWidget):
    """
    Toolbar nổi trên màn hình (Qt.WindowStaysOnTopHint).
    
    Signals:
        capture_requested (CaptureMode, int):
            Phát khi người dùng nhấn Capture. Truyền mode và thời gian delay.
        hide_to_tray: Phát khi người dùng muốn thu về khay.
    """

    capture_requested = pyqtSignal(object, int)  # (CaptureMode, delay_seconds)
    hide_to_tray = pyqtSignal()
    quit_requested = pyqtSignal()  # Phát khi nhấn nút X

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("toolbar_root")
        self.setFixedHeight(TOOLBAR_HEIGHT)
        self.setStyleSheet(_TOOLBAR_STYLE)

        # Cửa sổ không viền, luôn trên cùng, không có taskbar entry
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._build_ui()
        self._position_top_center()

    # ─── Xây dựng UI ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 10, 6)
        layout.setSpacing(5)

        # ── Logo + tên app ────────────────────────────────────────────────────
        lbl_logo = QLabel("✂")
        lbl_logo.setFont(QFont("Segoe UI", 16))
        lbl_logo.setStyleSheet("color: #3BA5FF; font-size: 18px; padding-right: 2px;")
        layout.addWidget(lbl_logo)

        lbl_name = QLabel("Snipping")
        lbl_name.setStyleSheet("color: #E8E8E8; font-size: 12px; font-weight: 600;")
        layout.addWidget(lbl_name)

        # ── Separator ─────────────────────────────────────────────────────────
        sep1 = QLabel("|")
        sep1.setObjectName("lbl_sep")
        layout.addWidget(sep1)

        # ── Nhóm nút chọn chế độ ─────────────────────────────────────────────
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)

        mode_icons = {
            "Rectangle": ("▭", "Chụp vùng chữ nhật"),
            "Fullscreen": ("⛶", "Chụp toàn màn hình"),
            "Window":     ("◻", "Chụp cửa sổ"),
            "Freeform":   ("✏", "Vẽ vùng tự do"),
        }

        self._mode_buttons: dict[str, QToolButton] = {}
        for mode_name, (icon, tooltip) in mode_icons.items():
            btn = QToolButton()
            btn.setText(f"{icon}  {mode_name}")
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self._mode_group.addButton(btn)
            self._mode_buttons[mode_name] = btn
            layout.addWidget(btn)

        # Mặc định chọn Rectangle
        self._mode_buttons["Rectangle"].setChecked(True)

        # ── Separator ─────────────────────────────────────────────────────────
        sep2 = QLabel("|")
        sep2.setObjectName("lbl_sep")
        layout.addWidget(sep2)

        # ── Combobox delay ────────────────────────────────────────────────────
        lbl_delay = QLabel("⏱ Delay:")
        lbl_delay.setStyleSheet("color: #C8C8C8; font-size: 12px;")
        layout.addWidget(lbl_delay)

        self._combo_delay = QComboBox()
        for d in CAPTURE_DELAYS:
            label = "Ngay" if d == 0 else f"{d}s"
            self._combo_delay.addItem(label, userData=d)
        self._combo_delay.setCurrentIndex(0)
        layout.addWidget(self._combo_delay)

        layout.addSpacing(6)

        # ── Nút Capture ───────────────────────────────────────────────────────
        self._btn_capture = QPushButton("📷  Capture")
        self._btn_capture.setObjectName("btn_capture")
        self._btn_capture.setFixedHeight(34)
        self._btn_capture.clicked.connect(self._on_capture_clicked)
        layout.addWidget(self._btn_capture)

        layout.addStretch()

        # ── Separator trước nút điều khiển ────────────────────────────────────
        sep3 = QLabel("|")
        sep3.setObjectName("lbl_sep")
        layout.addWidget(sep3)

        # ── Nút thu về tray (—) ───────────────────────────────────────────────
        btn_tray = QToolButton()
        btn_tray.setObjectName("btn_tray")
        btn_tray.setText("—")
        btn_tray.setToolTip("Thu về khay hệ thống")
        btn_tray.setFixedSize(30, 30)
        btn_tray.clicked.connect(self.hide_to_tray.emit)
        layout.addWidget(btn_tray)

        # ── Nút tắt (X) ──────────────────────────────────────────────────────
        btn_close = QToolButton()
        btn_close.setObjectName("btn_close")
        btn_close.setText("✕")
        btn_close.setToolTip("Thoát ứng dụng")
        btn_close.setFixedSize(30, 30)
        btn_close.clicked.connect(self.quit_requested.emit)
        layout.addWidget(btn_close)

    # ─── Logic ───────────────────────────────────────────────────────────────

    def _on_capture_clicked(self) -> None:
        """Đọc mode và delay rồi phát signal."""
        # Tìm mode đang được chọn
        selected_mode_name = "Rectangle"
        for name, btn in self._mode_buttons.items():
            if btn.isChecked():
                selected_mode_name = name
                break

        mode = _MODE_MAP[selected_mode_name]
        delay: int = self._combo_delay.currentData()  # type: ignore[assignment]
        self.capture_requested.emit(mode, delay)

    def _position_top_center(self) -> None:
        """Đặt toolbar ở giữa trên cùng màn hình chính."""
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        screen_geo = screen.geometry()
        toolbar_w = 760  # Chiều rộng tăng thêm để chứa nút X
        x = screen_geo.left() + (screen_geo.width() - toolbar_w) // 2
        y = screen_geo.top() + 20  # Cách mép trên 20px
        self.setGeometry(x, y, toolbar_w, TOOLBAR_HEIGHT)

    def set_capture_enabled(self, enabled: bool) -> None:
        """Bật/tắt nút Capture (khi đang delay hoặc đang chụp)."""
        self._btn_capture.setEnabled(enabled)
        if enabled:
            self._btn_capture.setText("📷  Capture")
        else:
            self._btn_capture.setText("⏳  Chờ...")
