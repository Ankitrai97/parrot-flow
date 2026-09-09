from __future__ import annotations

import logging
from collections.abc import Callable

import keyboard


class PushToTalkHotkey:
    """Keyboard-hook implementation for hold or one-press toggle dictation."""

    def __init__(self, shortcut: str, on_press: Callable[[], None], on_release: Callable[[], None],
                 logger: logging.Logger, mode: str = "toggle") -> None:
        tokens = [token.strip().lower() for token in shortcut.split("+") if token.strip()]
        if len(tokens) < 2:
            raise ValueError("Hotkey must include a modifier and key, for example ctrl+space")
        self.modifiers, self.trigger = tokens[:-1], tokens[-1]
        if mode not in {"hold", "toggle"}:
            raise ValueError("Hotkey mode must be 'hold' or 'toggle'")
        self.on_press, self.on_release, self.logger = on_press, on_release, logger
        self.mode, self._active, self._hook, self._trigger_down = mode, False, None, False
        self._trigger_names = self._matching_key_names(self.trigger)

    @staticmethod
    def _matching_key_names(trigger: str) -> set[str]:
        """Account for the names Windows emits for the physical logo keys."""
        if trigger in {"windows", "win", "left windows", "right windows", "left win", "right win"}:
            return {"windows", "win", "left windows", "right windows", "left win", "right win"}
        return {trigger}

    def start(self) -> None:
        self._hook = keyboard.hook(self._handle, suppress=False)
        self.logger.info("Global %s hotkey enabled: %s+%s", self.mode, "+".join(self.modifiers), self.trigger)

    def _handle(self, event: keyboard.KeyboardEvent) -> None:
        if event.name not in self._trigger_names:
            return
        if event.event_type == "down":
            if self._trigger_down:
                return
            self._trigger_down = True
            if not all(keyboard.is_pressed(key) for key in self.modifiers):
                return
            if self._active and self.mode == "toggle":
                self._active = False
                self.on_release()
            elif not self._active:
                self._active = True
                self.on_press()
        elif event.event_type == "up":
            self._trigger_down = False
            if self.mode != "hold" or not self._active:
                return
            self._active = False
            self.on_release()

    def close(self) -> None:
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
