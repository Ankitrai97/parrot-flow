from __future__ import annotations

from collections.abc import Callable
import ctypes
from ctypes import wintypes
from pathlib import Path
from queue import Empty, SimpleQueue
import sys
import tkinter as tk


class RecordingHud:
    """Draggable floating dictation control with compact and recording states."""

    _TRANSPARENT = "#f2f4f8"
    _PANEL = "#111827"
    _PANEL_MUTED = "#1f2937"
    _TEXT = "#f9fafb"
    _SUBTLE = "#9ca3af"
    _ACCENT = "#8b5cf6"
    _RECORDING = "#ef4444"
    _SUCCESS = "#22c55e"
    _GWL_EXSTYLE = -20
    _WS_EX_NOACTIVATE = 0x08000000

    def __init__(self, on_start: Callable[[], None], on_stop: Callable[[], None],
                 on_cancel: Callable[[], None]) -> None:
        self._on_start, self._on_stop, self._on_cancel = on_start, on_stop, on_cancel
        self._actions: SimpleQueue[tuple[str, str | None]] = SimpleQueue()
        self._state = "hidden"
        self._preview = "Speak naturally. Your live transcript appears here."
        self._drag_origin: tuple[int, int] | None = None
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", self._TRANSPARENT)
        self._make_non_activating()
        project_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        avatar_path = project_root / "assets" / "parrot-avatar.png"
        self._parrot_avatar = tk.PhotoImage(file=str(avatar_path)).subsample(2, 2)
        self.canvas = tk.Canvas(self.root, bg=self._TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self._begin_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._draw()
        self.root.after(40, self._drain)

    def _make_non_activating(self) -> None:
        """Keep typing focus in the target app when a HUD button is clicked."""
        self.root.update_idletasks()
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_style = user32.GetWindowLongW
        get_style.argtypes = (wintypes.HWND, ctypes.c_int)
        get_style.restype = ctypes.c_long
        set_style = user32.SetWindowLongW
        set_style.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
        set_style.restype = ctypes.c_long
        hwnd = wintypes.HWND(self.root.winfo_id())
        style = get_style(hwnd, self._GWL_EXSTYLE)
        set_style(hwnd, self._GWL_EXSTYLE, style | self._WS_EX_NOACTIVATE)

    def show_recording(self) -> None:
        self._actions.put(("recording", None))

    def show_idle(self) -> None:
        self._actions.put(("idle", None))

    def hide(self) -> None:
        self._actions.put(("hide", None))

    def update_preview(self, text: str) -> None:
        self._actions.put(("preview", text))

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        self._actions.put(("close", None))

    def _draw_round_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: object) -> None:
        self.canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, **kwargs)
        self.canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, **kwargs)
        for x, y in ((x1 + radius, y1 + radius), (x2 - radius, y1 + radius),
                     (x1 + radius, y2 - radius), (x2 - radius, y2 - radius)):
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, **kwargs)

    def _button(self, x1: int, y1: int, x2: int, y2: int, label: str, fill: str, action: str) -> None:
        self._draw_round_rect(x1, y1, x2, y2, 13, fill=fill, outline="", tags=("action", action))
        self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=label, fill=self._TEXT,
                                font=("Segoe UI", 10, "bold"), tags=("action", action))
        self.canvas.tag_bind(action, "<Button-1>", lambda _event, name=action: self._activate(name))

    def _recording_indicator(self, x: int, y: int) -> None:
        """Small glossy red indicator over the avatar while the mic is active."""
        self.canvas.create_oval(x - 8, y - 7, x + 9, y + 10, fill="#32080c", outline="")
        self.canvas.create_oval(x - 7, y - 8, x + 7, y + 6, fill="#dc2626", outline="#fca5a5")
        self.canvas.create_oval(x - 4, y - 5, x + 1, y, fill="#fff1f2", outline="")

    def _draw(self) -> None:
        expanded = self._state == "recording"
        width, height = (326, 76)
        self.canvas.config(width=width, height=height)
        self.canvas.delete("all")
        # Compact dark-glass pill based on the supplied Parrot Flow reference.
        self._draw_round_rect(7, 9, width - 3, height - 3, 29, fill="#020617", outline="")
        self._draw_round_rect(3, 3, width - 7, height - 9, 29, fill="#0c1726", outline="#334155", width=1)
        self.canvas.create_image(42, 35, image=self._parrot_avatar)
        if expanded:
            self._recording_indicator(63, 18)
            self.canvas.create_text(80, 28, text="Parrot Flow", anchor="w", fill=self._TEXT,
                                    font=("Segoe UI", 11, "bold"))
            self.canvas.create_text(80, 47, text="Listening…", anchor="w", fill="#fca5a5",
                                    font=("Segoe UI", 9, "bold"))
            self._button(162, 20, 250, 56, "■  Stop", self._ACCENT, "stop")
            self._button(258, 20, 314, 56, "Cancel", "#334155", "cancel")
        else:
            self.canvas.create_text(80, 28, text="Parrot Flow", anchor="w", fill=self._TEXT,
                                    font=("Segoe UI", 11, "bold"))
            self.canvas.create_text(80, 47, text="Ready", anchor="w", fill="#6ee7b7",
                                    font=("Segoe UI", 9))
            self._button(222, 20, 286, 56, "▶  Start", self._ACCENT, "start")
            self.canvas.create_text(302, 38, text="×", fill=self._SUBTLE, font=("Segoe UI", 18),
                                    tags=("action", "hide"))
            self.canvas.tag_bind("hide", "<Button-1>", lambda _event: self._activate("hide"))

    def _activate(self, action: str) -> None:
        if action == "start":
            self._on_start()
        elif action == "stop":
            self._on_stop()
        elif action == "cancel":
            self._on_cancel()
        elif action == "hide":
            # Hiding an active recorder must not leave the microphone running
            # invisibly. The compact control can be hidden without stopping.
            if self._state == "recording":
                self._on_cancel()
            self.hide()

    def _begin_drag(self, event: tk.Event[tk.Misc]) -> None:
        current = self.canvas.gettags("current")
        if "action" not in current:
            self._drag_origin = (event.x_root, event.y_root)

    def _drag(self, event: tk.Event[tk.Misc]) -> None:
        if self._drag_origin is None:
            return
        previous_x, previous_y = self._drag_origin
        self.root.geometry(f"+{self.root.winfo_x() + event.x_root - previous_x}+{self.root.winfo_y() + event.y_root - previous_y}")
        self._drag_origin = (event.x_root, event.y_root)

    def _end_drag(self, _event: tk.Event[tk.Misc]) -> None:
        self._drag_origin = None

    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.update_idletasks()
        if self.root.winfo_x() <= 1 and self.root.winfo_y() <= 1:
            x = self.root.winfo_screenwidth() - self.root.winfo_width() - 32
            y = self.root.winfo_screenheight() - self.root.winfo_height() - 100
            self.root.geometry(f"+{x}+{y}")
        self.root.lift()

    def _drain(self) -> None:
        try:
            while True:
                action, value = self._actions.get_nowait()
                if action == "recording":
                    self._state = "recording"
                    self._draw()
                    self._show_window()
                elif action == "idle":
                    self._state = "idle"
                    self._preview = "Speak naturally. Your live transcript appears here."
                    self._draw()
                    self._show_window()
                elif action == "hide":
                    self._state = "hidden"
                    self.root.withdraw()
                elif action == "preview" and value is not None and self._state == "recording":
                    self._preview = value
                    self._draw()
                elif action == "close":
                    self.root.quit()
                    return
        except Empty:
            pass
        self.root.after(40, self._drain)
