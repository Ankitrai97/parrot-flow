from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from threading import Event, Lock, Thread

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
SW_RESTORE = 9


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    # Included because INPUT's Windows ABI is sized by its largest union member.
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


class WindowsTextInjector:
    """Type Unicode directly into the focused control without touching the clipboard."""

    def __init__(self, typing_delay: float = 0.01) -> None:
        self._typing_delay = max(0.005, typing_delay)
        self._logger = logging.getLogger("localdictate")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._send_input = self._user32.SendInput
        self._send_input.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self._send_input.restype = wintypes.UINT
        self._get_key_state = self._user32.GetAsyncKeyState
        self._get_key_state.argtypes = (ctypes.c_int,)
        self._get_key_state.restype = ctypes.c_short
        self._get_foreground = self._user32.GetForegroundWindow
        self._get_foreground.restype = wintypes.HWND
        self._set_foreground = self._user32.SetForegroundWindow
        self._set_foreground.argtypes = (wintypes.HWND,)
        self._set_foreground.restype = wintypes.BOOL
        self._bring_to_top = self._user32.BringWindowToTop
        self._bring_to_top.argtypes = (wintypes.HWND,)
        self._bring_to_top.restype = wintypes.BOOL
        self._show_window = self._user32.ShowWindow
        self._show_window.argtypes = (wintypes.HWND, ctypes.c_int)
        self._show_window.restype = wintypes.BOOL
        self._is_iconic = self._user32.IsIconic
        self._is_iconic.argtypes = (wintypes.HWND,)
        self._is_iconic.restype = wintypes.BOOL
        self._get_window_thread = self._user32.GetWindowThreadProcessId
        self._get_window_thread.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        self._get_window_thread.restype = wintypes.DWORD
        self._attach_thread_input = self._user32.AttachThreadInput
        self._attach_thread_input.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
        self._attach_thread_input.restype = wintypes.BOOL
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._get_process_id = self._kernel32.GetCurrentProcessId
        self._get_process_id.restype = wintypes.DWORD
        self._own_process_id = int(self._get_process_id())
        self._target_window: wintypes.HWND | None = None
        self._dictation_target: wintypes.HWND | None = None
        self._target_lock = Lock()
        self._tracker_stop = Event()
        self._tracker = Thread(target=self._track_last_external_window, daemon=True, name="focus-tracker")
        self._tracker.start()

    def capture_focus(self) -> None:
        """Remember the last non-Parrot Flow window for final text injection."""
        self._remember_foreground()
        with self._target_lock:
            target = self._target_window
            self._dictation_target = target
        self._logger.info("Dictation target captured: hwnd=%s", target)

    def close(self) -> None:
        self._tracker_stop.set()

    def _track_last_external_window(self) -> None:
        """Do not let a click on the HUD overwrite the app the user was typing in."""
        while not self._tracker_stop.wait(0.08):
            self._remember_foreground()

    def _remember_foreground(self) -> None:
        window = self._get_foreground()
        if not window or self._window_process_id(window) == self._own_process_id:
            return
        with self._target_lock:
            self._target_window = window

    def _window_thread_id(self, window: wintypes.HWND) -> int:
        process_id = wintypes.DWORD()
        return int(self._get_window_thread(window, ctypes.byref(process_id)))

    def _window_process_id(self, window: wintypes.HWND) -> int:
        process_id = wintypes.DWORD()
        self._get_window_thread(window, ctypes.byref(process_id))
        return int(process_id.value)

    def _activate_target(self, target: wintypes.HWND) -> bool:
        """Restore the target window even if Windows foreground rules intervened."""
        # SW_RESTORE also turns a maximized window back into a normal-sized
        # one. Restore only a genuinely minimized target.
        if self._is_iconic(target):
            self._show_window(target, SW_RESTORE)
        if self._set_foreground(target):
            return True

        foreground = self._get_foreground()
        foreground_thread = self._window_thread_id(foreground) if foreground else 0
        target_thread = self._window_thread_id(target)
        attached = bool(foreground_thread and target_thread and foreground_thread != target_thread
                        and self._attach_thread_input(foreground_thread, target_thread, True))
        try:
            self._bring_to_top(target)
            return bool(self._set_foreground(target))
        finally:
            if attached:
                self._attach_thread_input(foreground_thread, target_thread, False)

    def inject(self, text: str) -> None:
        if not text:
            return
        # SendInput preserves the current keyboard state. The shortcut may
        # still be held when fast GPU inference finishes.
        self._wait_for_modifiers()
        with self._target_lock:
            target = self._dictation_target
        if target:
            activated = self._activate_target(target)
            self._logger.info("Restored dictation target hwnd=%s: %s", target, activated)
            if not activated:
                raise RuntimeError("Unable to activate the dictation target")
            # Let Windows finish foreground activation before the first key event.
            time.sleep(0.12)
        else:
            self._logger.warning("No external dictation target was available; typing into current focus")
        count = 0
        for character in text:
            if target and self._get_foreground() != target:
                raise RuntimeError("Dictation target lost focus during text insertion")
            events: list[INPUT] = []
            if character == "\n":
                events.extend(self._key_events(VK_RETURN, 0))
            else:
                codepoint = ord(character)
                if codepoint > 0xFFFF:
                    codepoint -= 0x10000
                    units = [0xD800 + (codepoint >> 10), 0xDC00 + (codepoint & 0x3FF)]
                else:
                    units = [codepoint]
                for unit in units:
                    events.extend(self._key_events(0, unit, KEYEVENTF_UNICODE))
            array_type = INPUT * len(events)
            sent = self._send_input(len(events), array_type(*events), ctypes.sizeof(INPUT))
            if sent != len(events):
                raise RuntimeError(f"Text insertion interrupted after {count} of {len(text)} characters")
            count += 1
            # Controlled editors can discard updates when hundreds of Unicode
            # events arrive in a single burst. Give each character a frame.
            time.sleep(self._typing_delay)
        self._logger.info("Text insertion completed: %s of %s characters", count, len(text))

    def _wait_for_modifiers(self) -> None:
        deadline = time.monotonic() + 3.0
        while any(self._get_key_state(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
            if time.monotonic() >= deadline:
                raise RuntimeError("Release the shortcut keys before inserting dictation")
            time.sleep(0.02)

    @staticmethod
    def _key_events(virtual_key: int, scan_code: int, flags: int = 0) -> list[INPUT]:
        down = INPUT_UNION(ki=KEYBDINPUT(virtual_key, scan_code, flags, 0, 0))
        up = INPUT_UNION(ki=KEYBDINPUT(virtual_key, scan_code, flags | KEYEVENTF_KEYUP, 0, 0))
        return [INPUT(INPUT_KEYBOARD, down), INPUT(INPUT_KEYBOARD, up)]
