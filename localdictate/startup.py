from __future__ import annotations

import os
import subprocess
import sys
import winreg
from pathlib import Path

from . import __version__

APP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ParrotFlow"
APP_NAME = "Parrot Flow"
APP_VALUE = "ParrotFlow"
LEGACY_APP_VALUE = "LocalDictate"


def _launch_command() -> str:
    """Return a no-console launch command for development and packaged builds."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" -m localdictate'


def _start_menu_directory() -> Path:
    app_data = Path(os.environ["APPDATA"])
    return app_data / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def _shortcut_path() -> Path:
    return _start_menu_directory() / f"{APP_NAME}.lnk"


def _launcher_parts() -> tuple[Path, str, Path]:
    """Return target, arguments, and working directory for a Start Menu shortcut."""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable)
        return executable, "", executable.parent
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return pythonw, "-m localdictate", Path(__file__).resolve().parent.parent


def _console_python() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return Path(sys.executable).with_name("python.exe")


def _uninstall_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --remove-app'
    return f'"{_console_python()}" -m localdictate --remove-app'


def enable_at_login() -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_VALUE, 0, winreg.REG_SZ, _launch_command())
        try:
            winreg.DeleteValue(key, LEGACY_APP_VALUE)
        except FileNotFoundError:
            pass


def disable_at_login() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_VALUE)
            try:
                winreg.DeleteValue(key, LEGACY_APP_VALUE)
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        pass


def install_start_menu_shortcut() -> Path:
    """Create a Windows Start Menu shortcut so the app appears in Windows search."""
    shortcut_path = _shortcut_path()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    target, arguments, working_directory = _launcher_parts()
    script = "\n".join(
        [
            "$shell = New-Object -ComObject WScript.Shell",
            f"$shortcut = $shell.CreateShortcut({_ps_quote(str(shortcut_path))})",
            f"$shortcut.TargetPath = {_ps_quote(str(target))}",
            f"$shortcut.Arguments = {_ps_quote(arguments)}",
            f"$shortcut.WorkingDirectory = {_ps_quote(str(working_directory))}",
            "$shortcut.Description = 'Parrot Flow local voice-to-text'",
            f"$shortcut.IconLocation = {_ps_quote(str(target))}",
            "$shortcut.Save()",
        ]
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
    )
    install_windows_app_entry()
    return shortcut_path


def remove_start_menu_shortcut() -> None:
    try:
        _shortcut_path().unlink()
    except FileNotFoundError:
        pass
    remove_windows_app_entry()


def install_windows_app_entry() -> None:
    """Add an HKCU uninstall entry so Windows Settings lists Parrot Flow."""
    target, _, working_directory = _launcher_parts()
    uninstall_command = _uninstall_command()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, __version__)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Parrot Flow")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(working_directory))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(target))
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, uninstall_command)
        winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, uninstall_command)


def remove_windows_app_entry() -> None:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except FileNotFoundError:
        pass


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
