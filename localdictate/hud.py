"""The compact HTML/CSS control displayed while Parrot Flow is running."""

from __future__ import annotations

import ctypes
import json
import logging
from collections.abc import Callable
from ctypes import wintypes
from queue import Empty, SimpleQueue
from threading import Event, Thread

import webview

_IDLE_WIDTH = 136
_RECORDING_WIDTH = 124
_HEIGHT = 34

_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_create_round_rect_rgn = _gdi32.CreateRoundRectRgn
_create_round_rect_rgn.argtypes = (ctypes.c_int,) * 6
_create_round_rect_rgn.restype = wintypes.HANDLE
_delete_object = _gdi32.DeleteObject
_delete_object.argtypes = (wintypes.HANDLE,)
_delete_object.restype = wintypes.BOOL
_set_window_rgn = _user32.SetWindowRgn
_set_window_rgn.argtypes = (wintypes.HWND, wintypes.HANDLE, wintypes.BOOL)
_set_window_rgn.restype = ctypes.c_int
_show_window = _user32.ShowWindow
_show_window.argtypes = (wintypes.HWND, ctypes.c_int)
_show_window.restype = wintypes.BOOL
_get_style = _user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else _user32.GetWindowLongW
_set_style = _user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else _user32.SetWindowLongW
_get_style.argtypes, _get_style.restype = (wintypes.HWND, ctypes.c_int), ctypes.c_ssize_t
_set_style.argtypes, _set_style.restype = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t), ctypes.c_ssize_t


# This is deliberately an HTML/CSS interface rather than a bitmap or a canvas.
# Keeping the markup here makes the tiny always-on-top window self-contained and
# avoids an additional local web server or packaged image asset.
_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; background: transparent; }
  body { font-family: "Segoe UI", sans-serif; user-select: none; }
  #hud {
    width: 100%; height: 100%; position: relative; display: flex; align-items: center;
    border: 1px solid rgba(255,255,255,.16); border-radius: 17px;
    background: linear-gradient(135deg, #0f182a, #070c17);
    box-shadow: inset 0 1px 0 rgba(255,255,255,.11), inset 0 -1px 0 rgba(0,0,0,.35);
    overflow: hidden; transition: background .22s ease, border-color .22s ease;
  }
  #hud::before {
    content: ""; position: absolute; inset: 1px; border-radius: 16px; pointer-events: none;
    background: linear-gradient(112deg, rgba(255,255,255,.09), transparent 31%, transparent 72%, rgba(255,255,255,.035));
  }
  #hud.recording { border-color: rgba(56,230,150,.30); }
  #hud.idle { border-color: rgba(255,89,103,.31); }
  .lamp-wrap { width: 34px; height: 100%; display: grid; place-items: center; flex: 0 0 34px; }
  .lamp {
    width: 17px; height: 17px; position: relative; border-radius: 50%;
    transition: background .24s ease, box-shadow .24s ease, transform .24s ease;
  }
  .lamp::before {
    content: ""; position: absolute; width: 5px; height: 5px; top: 3px; left: 4px; border-radius: 50%;
    background: rgba(255,255,255,.82); filter: blur(.2px);
  }
  .lamp::after {
    content: ""; position: absolute; inset: -4px; border-radius: inherit; opacity: .28;
    background: inherit; filter: blur(5px); transition: opacity .24s ease;
  }
  .recording .lamp {
    background: radial-gradient(circle at 34% 28%, #d9ffe9 0 9%, #55f4a0 17%, #14bb68 48%, #05733f 76%, #01391f 100%);
    box-shadow: 0 0 0 2px rgba(65,255,165,.11), 0 0 13px rgba(43,238,139,.62), inset -2px -3px 5px rgba(0,36,19,.52);
    animation: breathe 1.55s ease-in-out infinite;
  }
  .idle .lamp {
    background: radial-gradient(circle at 34% 28%, #ffe0e2 0 9%, #ff7280 18%, #dc3146 48%, #8d1022 76%, #4a0610 100%);
    box-shadow: 0 0 0 2px rgba(255,93,110,.10), 0 0 10px rgba(238,47,71,.44), inset -2px -3px 5px rgba(51,0,7,.55);
  }
  .wave { height: 20px; display: flex; align-items: center; gap: 2px; flex: 1; min-width: 0; }
  .wave i {
    width: 2px; height: 4px; display: block; border-radius: 99px;
    background: linear-gradient(#a8ffd4, #27d987); box-shadow: 0 0 4px rgba(54,246,151,.70);
    animation: pulse 760ms ease-in-out infinite alternate; transform-origin: center;
  }
  .wave i:nth-child(2n) { animation-delay: -220ms; }
  .wave i:nth-child(3n) { animation-delay: -470ms; }
  .wave i:nth-child(4n) { animation-delay: -110ms; }
  .divider { width: 1px; height: 15px; margin: 0 5px 0 4px; background: rgba(255,255,255,.12); }
  button {
    z-index: 1; appearance: none; border: 0; padding: 0; width: 20px; height: 24px;
    display: grid; place-items: center; color: rgba(240,244,255,.72); background: transparent;
    border-radius: 9px; cursor: pointer; font: 600 15px/1 "Segoe UI", sans-serif;
    transition: color .15s ease, background .15s ease, transform .15s ease;
  }
  button:hover { color: #fff; background: rgba(255,255,255,.10); }
  button:active { transform: scale(.86); }
  #minimize { font-size: 15px; padding-bottom: 5px; }
  #cancel { margin-right: 1px; font-size: 17px; font-weight: 400; }
  #cancel:hover { color: #fff; background: rgba(255,70,91,.72); }
  .idle .wave, .idle .divider, .idle #cancel { display: none; }
  .idle #minimize { margin-left: -12px; }
  .lamp-wrap { cursor: pointer; }
  .lamp-wrap { cursor: default; width: 26px; flex-basis: 26px; }
  .pywebview-drag-region { width: 18px; flex: 0 0 18px; color: #8493ae; cursor: move; text-align: center; }
  button { flex-shrink: 0; }
  #start { width: 28px; font-size: 12px; }
  #insert { display: none; width: 44px; font-size: 11px; }
  .pending #insert { display: grid; }
  .recording #start, .processing #start, .pending #start { display: none; }
  .pending #message, .notice #message { display: block; }
  .pending .wave, .pending .divider, .pending #stop,
  .notice .wave, .notice .divider, .notice #stop { display: none; }
  .processing button { visibility: hidden; pointer-events: none; }
  .processing .pywebview-drag-region { pointer-events: none; }
  button:disabled { opacity: .4; pointer-events: none; }
  .idle #minimize { margin-left: 0; }
  #message { display: none; color: #f1e3b4; font-size: 11px; flex: 1; padding-right: 6px; }
  .processing .lamp { background: #ffc14c; animation: breathe 1s infinite; }
  .error .lamp { background: #ff5368; }
  .processing #message, .error #message { display: block; }
  .processing .wave, .error .wave, .processing .divider, .error .divider,
  .processing #cancel, .error #cancel { display: none; }
  #stop { font-size: 12px; width: 22px; color: #9affa9; }
  .idle #stop, .processing #stop, .error #stop { display: none; }
  @keyframes pulse { from { height: 3px; opacity: .52; } to { height: 15px; opacity: 1; } }
  @keyframes breathe { 50% { transform: scale(1.06); box-shadow: 0 0 0 3px rgba(65,255,165,.10), 0 0 16px rgba(43,238,139,.78), inset -2px -3px 5px rgba(0,36,19,.52); } }
</style>
</head>
<body>
  <main id="hud" class="idle">
    <span class="pywebview-drag-region" title="Drag to move">⠿</span>
    <div class="lamp-wrap" title="Status only"><span class="lamp" aria-label="Status"></span></div>
    <button id="start" title="Start dictation" aria-label="Start dictation">●</button>
    <div class="wave" aria-hidden="true">
      <i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i>
    </div>
    <span class="divider" aria-hidden="true"></span>
    <span id="message"></span>
    <button id="insert" title="Insert saved transcript">Insert</button>
    <button id="stop" title="Stop and transcribe" aria-label="Stop and transcribe">■</button>
    <button id="minimize" title="Hide control" aria-label="Hide control">−</button>
    <button id="cancel" title="Cancel dictation" aria-label="Cancel dictation">×</button>
    <button id="settings" title="Settings" aria-label="Settings">⚙</button>
  </main>
<script>
  function setHudState(state, message) {
    const hud = document.getElementById('hud');
    hud.className = state;
    document.getElementById('message').textContent = message || '';
    document.querySelectorAll('button').forEach(b => b.disabled = state === 'processing');
    hud.title = message || (state === 'recording' ? 'Listening — click stop to transcribe' : 'Ready — click record or press your hotkey');
  }
  let pointer = null;
  document.addEventListener('pointerdown', e => {
    pointer = {x:e.screenX, y:e.screenY, target:e.target, moved:false};
  });
  document.addEventListener('pointermove', e => {
    if (pointer && Math.hypot(e.screenX-pointer.x, e.screenY-pointer.y) > 4) pointer.moved = true;
  });
  document.addEventListener('pointercancel', () => pointer = null);
  for (const [id, action] of Object.entries({start:'toggle', stop:'stop', minimize:'minimize',
                                          cancel:'cancel', settings:'settings', insert:'insert'})) {
    document.getElementById(id).addEventListener('click', async e => {
      e.stopPropagation();
      if (!e.isTrusted || e.button !== 0 || (pointer && (pointer.moved ||
          pointer.target !== e.target)) || document.getElementById('hud').className === 'processing') return;
      pointer = null;
      if (action === 'stop' || action === 'insert') setHudState('processing', 'Working…');
      try { await window.pywebview.api[action](true); }
      catch (error) { setHudState('error', 'Control unavailable — reopen Parrot Flow'); }
    });
  }
</script>
</body>
</html>"""


class _HudApi:
    def __init__(self, hud: RecordingHud) -> None:
        self._hud = hud

    def minimize(self, user_initiated: bool = False) -> None:
        self._hud.hide()

    def cancel(self, user_initiated: bool = False) -> None:
        self._hud.cancel()

    def toggle(self, user_initiated: bool = False) -> None:
        if user_initiated is True:
            self._hud.toggle()

    def stop(self, user_initiated: bool = False) -> None:
        self._hud.stop()

    def settings(self, user_initiated: bool = False) -> None:
        self._hud.open_settings()

    def insert(self, user_initiated: bool = False) -> None:
        self._hud.insert()


class RecordingHud:
    """A draggable, tiny, always-on-top Parrot Flow control."""

    def __init__(self, on_cancel: Callable[[], None], on_toggle: Callable[[], None] | None = None,
                 on_stop: Callable[[], None] | None = None,
                 is_busy: Callable[[], bool] = lambda: False,
                 on_settings=None, on_insert=None, on_ready=None,
                 title: str = "Parrot Flow") -> None:
        self._on_cancel = on_cancel
        self._on_toggle = on_toggle
        self._on_stop = on_stop
        self._is_busy = is_busy
        self._on_settings, self._on_insert = on_settings, on_insert
        self._on_ready = on_ready
        self._actions: SimpleQueue[tuple[str, str]] = SimpleQueue()
        self._state, self._message = "idle", ""
        self._closed = Event()
        self._minimized = False
        self._window = webview.create_window(
            title,
            html=_HTML,
            js_api=_HudApi(self),
            width=_IDLE_WIDTH,
            height=_HEIGHT,
            min_size=(_IDLE_WIDTH, _HEIGHT),
            resizable=False,
            frameless=True,
            easy_drag=False,
            hidden=True,
            on_top=True,
            background_color="#070c17",
        )
        self._window.events.closing += lambda: False if self._is_busy() else None

    def run(self) -> None:
        """Run the native webview event loop on the application's main thread."""
        webview.start(self._start_action_worker, private_mode=True)

    def show_recording(self) -> None:
        self.show_status("recording")

    def show_idle(self) -> None:
        self.show_status("idle")

    def show_status(self, state: str, message: str = "") -> None:
        self._state, self._message = state, message
        self._actions.put((state, message))

    def show(self) -> None:
        self._actions.put(("show", ""))

    def toggle(self) -> None:
        if self._is_busy() or self._state == "processing":
            return
        if self._on_toggle:
            logging.getLogger("localdictate").info("HUD dictation button clicked")
            self._on_toggle()

    def stop(self) -> None:
        if self._is_busy() or self._state == "processing":
            return
        if self._on_stop:
            self._on_stop()

    def update_preview(self, _text: str) -> None:
        # The HUD intentionally has no transcript text: it is a status indicator only.
        return

    def hide(self) -> None:
        if self._is_busy() or self._state == "processing":
            return
        self._actions.put(("hide", ""))

    def cancel(self) -> None:
        if self._is_busy() or self._state == "processing":
            return
        self._on_cancel()
        self.hide()

    def open_settings(self) -> None:
        if (not self._is_busy() and self._state not in {"processing", "recording", "pending"}
                and self._on_settings):
            logging.getLogger("localdictate").info("Opening settings")
            self._on_settings()

    def insert(self) -> None:
        if not self._is_busy() and self._state == "pending" and self._on_insert:
            self._on_insert()

    def close(self) -> None:
        self._actions.put(("close", ""))

    def _start_action_worker(self) -> None:
        self._window.events.loaded.wait()
        self._apply_native_pill_shape()
        Thread(target=self._drain_actions, name="parrot-flow-hud", daemon=True).start()
        if self._on_ready:
            self._on_ready()

    def _apply_native_pill_shape(self) -> None:
        native_window = self._window.native
        if native_window is None:
            return
        width, height = native_window.Width, native_window.Height
        region = _create_round_rect_rgn(0, 0, width + 1, height + 1, height, height)
        if not region:
            return
        handle = wintypes.HWND(native_window.Handle.ToInt64())
        if not _set_window_rgn(handle, region, True):
            # The system owns a region after a successful call; release it only
            # when Windows rejected it.
            _delete_object(region)

    def _drain_actions(self) -> None:
        while not self._closed.is_set():
            try:
                action, message = self._actions.get(timeout=0.25)
            except Empty:
                continue
            if action == "close":
                self._closed.set()
                self._window.destroy()
                return
            if action == "hide":
                if self._is_busy() or self._state == "processing":
                    continue
                self._minimized = True
                self._window.hide()
                continue
            if action == "idle" and self._minimized:
                continue
            self._minimized = False
            if action == "show":
                action, message = self._state, self._message
            width = {"recording": 196, "processing": 270, "error": 520,
                     "pending": 520, "notice": 520}.get(action, _IDLE_WIDTH)
            try:
                self._window.resize(width, _HEIGHT)
                self._window.evaluate_js(f"setHudState({json.dumps(action)}, {json.dumps(message)})")
                self._apply_native_pill_shape()
                native = self._window.native
                if native is not None:
                    from System import Action
                    # Update WinForms' managed visibility as well as the HWND.
                    # Unlike webview.show(), do not call Activate().
                    def show_without_activation():
                        handle = wintypes.HWND(native.Handle.ToInt64())
                        style = _get_style(handle, -20)
                        _set_style(handle, -20, style | 0x08000000)
                        try:
                            native.Show()
                            _show_window(handle, 4)
                        finally:
                            # WebView2 needs normal activation for mouse buttons.
                            _set_style(handle, -20, style)
                    native.Invoke(Action(show_without_activation))
            except Exception:
                logging.getLogger("localdictate").exception("Unable to update floating control")
