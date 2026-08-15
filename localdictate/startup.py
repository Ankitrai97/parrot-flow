from __future__ import annotations

from pathlib import Path
import sys
import winreg

APP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VALUE = "LocalDictate"


def _launch_command() -> str:
    """Return a no-console launch command for development and packaged builds."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" -m localdictate'


def enable_at_login() -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_VALUE, 0, winreg.REG_SZ, _launch_command())


def disable_at_login() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_VALUE)
    except FileNotFoundError:
        pass
