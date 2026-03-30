"""
settings.py
-----------
Quản lý cài đặt cấu hình App (Phím tắt, Chế độ mặc định...)
Dữ liệu lưu tại AppData để duy trì giữa các lần bật tắt và cập nhật.
"""

import json
import os
from pathlib import Path
from src.config import APP_NAME

def get_settings_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata) / APP_NAME
    else:
        # Fallback for non-windows
        base = Path.home() / f".{APP_NAME.replace(' ', '_').lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base

SETTINGS_FILE = get_settings_dir() / "settings.json"

DEFAULT_SETTINGS = {
    "hotkey_modifiers": ["<alt>", "<shift>"],
    "hotkey_key": "s"
}

class AppSettings:
    """Class wrapper quản lý việc lưu và đọc cài đặt."""
    
    _data = None
    
    @classmethod
    def load(cls):
        if cls._data is None:
            if SETTINGS_FILE.exists():
                try:
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        cls._data = json.load(f)
                except Exception:
                    cls._data = DEFAULT_SETTINGS.copy()
            else:
                cls._data = DEFAULT_SETTINGS.copy()
                cls.save()
                
        # Fill missing keys
        for k, v in DEFAULT_SETTINGS.items():
            if k not in cls._data:
                cls._data[k] = v

    @classmethod
    def save(cls):
        if cls._data is not None:
            try:
                with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(cls._data, f, indent=4)
            except Exception as e:
                print(f"Failed to save settings: {e}")

    @classmethod
    def get(cls, key: str, default=None):
        cls.load()
        return cls._data.get(key, default)

    @classmethod
    def set(cls, key: str, value):
        cls.load()
        cls._data[key] = value
        cls.save()

