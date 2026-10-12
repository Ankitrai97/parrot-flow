from __future__ import annotations

import ctypes
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Thread

import keyboard


class _WindowsKeyState:
    """Read current Windows key state, rather than the hook's cached events."""

    def __init__(self, keys: list[str]) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._get_state = user32.GetAsyncKeyState
        self._get_state.argtypes = (ctypes.c_int,)
        self._get_state.restype = ctypes.c_short
        map_key = user32.MapVirtualKeyW
        map_key.argtypes = (ctypes.c_uint, ctypes.c_uint)
        map_key.restype = ctypes.c_uint
        modifiers = {
            "ctrl": (0x11,), "control": (0x11,), "shift": (0x10,), "alt": (0x12,),
            "left ctrl": (0xA2,), "right ctrl": (0xA3,),
            "left shift": (0xA0,), "right shift": (0xA1,),
            "left alt": (0xA4,), "right alt": (0xA5,),
            "windows": (0x5B, 0x5C), "win": (0x5B, 0x5C),
            "left windows": (0x5B,), "left win": (0x5B,),
            "right windows": (0x5C,), "right win": (0x5C,),
        }
        self._codes = {}
        for key in keys:
            codes = modifiers.get(key)
            if codes is None:
                codes = tuple(dict.fromkeys(-scan if scan < 0 else map_key(scan, 3)
                                            for scan in keyboard.key_to_scan_codes(key)))
            codes = tuple(code for code in codes if code)
            if not codes:
                raise ValueError(f"No Windows virtual key for {key!r}")
            self._codes[key] = codes

    def __call__(self, key: str) -> bool:
        return any(self._get_state(code) & 0x8000 for code in self._codes[key])


class PushToTalkHotkey:
    """Observe the physical chord independently of delayed keyboard-hook events."""

    def __init__(self, shortcut: str, on_press: Callable[[], None], on_release: Callable[[], None],
                 logger: logging.Logger, mode: str = "toggle",
                 is_recording: Callable[[], bool] | None = None,
                 key_is_down: Callable[[str], bool] | None = None) -> None:
        tokens = [token.strip().lower() for token in shortcut.split("+") if token.strip()]
        if len(tokens) < 2:
            raise ValueError("Hotkey must include a modifier and key, for example ctrl+space")
        self.modifiers, self.trigger = tokens[:-1], tokens[-1]
        if mode not in {"hold", "toggle"}:
            raise ValueError("Hotkey mode must be 'hold' or 'toggle'")
        self.on_press, self.on_release, self.logger = on_press, on_release, logger
        self.mode, self._active, self._chord_down = mode, False, False
        self._is_recording = is_recording
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hotkey-actions")
        self._trigger_names = self._matching_key_names(self.trigger)
        self._keys = tokens
        self._key_is_down = key_is_down or _WindowsKeyState(tokens)
        self._armed, self._closed = Event(), Event()
        self._poll_thread: Thread | None = None

    @staticmethod
    def _matching_key_names(trigger: str) -> set[str]:
        """Account for the names Windows emits for the physical logo keys."""
        if trigger in {"windows", "win", "left windows", "right windows", "left win", "right win"}:
            return {"windows", "win", "left windows", "right windows", "left win", "right win"}
        return {trigger}

    def start(self) -> None:
        self._poll_thread = Thread(target=self._poll_keys, name="dictation-hotkey", daemon=True)
        self._poll_thread.start()
        self.logger.info("Global %s hotkey enabled: %s+%s", self.mode, "+".join(self.modifiers), self.trigger)

    def _arm_when_released(self) -> None:
        # Ignore the launch gesture. No recording can be requested until all
        # shortcut keys have been released continuously for 200ms.
        released_since = None
        while not self._closed.is_set():
            if any(self._key_is_down(key) for key in self._keys):
                released_since = None
            elif released_since is None:
                released_since = time.monotonic()
            elif time.monotonic() - released_since >= 0.2:
                self._armed.set()
                self.logger.info("Dictation shortcut armed after startup key release")
                return
            self._closed.wait(0.025)

    def _poll_keys(self) -> None:
        self._arm_when_released()
        while not self._closed.is_set():
            self._observe_chord(all(self._key_is_down(key) for key in self._keys))
            self._closed.wait(0.01)

    def _observe_chord(self, down: bool) -> None:
        if self._closed.is_set() or not self._armed.is_set() or down == self._chord_down:
            return
        self._chord_down = down
        if down:
            self.logger.info("Dictation shortcut pressed")
            # Capture the gesture now. The callback must still run if the user
            # has released the keys by the time this executor gets to it.
            self._executor.submit(self._press)
        elif self.mode == "hold":
            self._executor.submit(self._release)

    def _press(self) -> None:
        if self._closed.is_set():
            return
        active = self._is_recording() if self._is_recording else self._active
        try:
            if active and self.mode == "toggle":
                self._release()
            elif not active:
                self._active = self.on_press() is not False
        except Exception:
            self._active = False
            self.logger.exception("Hotkey action failed")

    def _release(self) -> None:
        self._active = False
        self.on_release()

    def close(self) -> None:
        self._closed.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=1)
        self._executor.shutdown(wait=True, cancel_futures=True)
