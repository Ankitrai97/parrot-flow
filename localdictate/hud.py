"""The compact HTML/CSS control displayed while Parrot Flow is running."""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from queue import Empty, SimpleQueue
from threading import Event, Thread

import webview

_IDLE_WIDTH = 42
_RECORDING_WIDTH = 124
_HEIGHT = 34


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
  @keyframes pulse { from { height: 3px; opacity: .52; } to { height: 15px; opacity: 1; } }
  @keyframes breathe { 50% { transform: scale(1.06); box-shadow: 0 0 0 3px rgba(65,255,165,.10), 0 0 16px rgba(43,238,139,.78), inset -2px -3px 5px rgba(0,36,19,.52); } }
</style>
</head>
<body>
  <main id="hud" class="idle">
    <div class="lamp-wrap"><span class="lamp" aria-label="Status"></span></div>
    <div class="wave" aria-hidden="true">
      <i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i>
    </div>
    <span class="divider" aria-hidden="true"></span>
    <button id="minimize" title="Hide control" aria-label="Hide control">−</button>
    <button id="cancel" title="Cancel dictation" aria-label="Cancel dictation">×</button>
  </main>
<script>
  function setHudState(state) {
    const hud = document.getElementById('hud');
    hud.className = state === 'recording' ? 'recording' : 'idle';
  }
  document.getElementById('minimize').addEventListener('click', (event) => {
    event.stopPropagation(); window.pywebview.api.minimize();
  });
  document.getElementById('cancel').addEventListener('click', (event) => {
    event.stopPropagation(); window.pywebview.api.cancel();
  });
</script>
</body>
</html>"""


class _HudApi:
    def __init__(self, hud: RecordingHud) -> None:
        self._hud = hud

    def minimize(self) -> None:
        self._hud.hide()

    def cancel(self) -> None:
        self._hud.cancel()


class RecordingHud:
    """A draggable, tiny, always-on-top Parrot Flow control."""

    def __init__(self, on_cancel: Callable[[], None]) -> None:
        self._on_cancel = on_cancel
        self._actions: SimpleQueue[str] = SimpleQueue()
        self._closed = Event()
        self._minimized = False
        self._window = webview.create_window(
            "Parrot Flow",
            html=_HTML,
            js_api=_HudApi(self),
            width=_IDLE_WIDTH,
            height=_HEIGHT,
            min_size=(_IDLE_WIDTH, _HEIGHT),
            resizable=False,
            frameless=True,
            easy_drag=True,
            hidden=True,
            on_top=True,
            transparent=True,
            background_color="#000000",
        )

    def run(self) -> None:
        """Run the native webview event loop on the application's main thread."""
        webview.start(self._start_action_worker, private_mode=True)

    def show_recording(self) -> None:
        self._actions.put("recording")

    def show_idle(self) -> None:
        self._actions.put("idle")

    def update_preview(self, _text: str) -> None:
        # The HUD intentionally has no transcript text: it is a status indicator only.
        return

    def hide(self) -> None:
        self._actions.put("hide")

    def cancel(self) -> None:
        self._on_cancel()
        self.hide()

    def close(self) -> None:
        self._actions.put("close")

    def _start_action_worker(self) -> None:
        self._make_native_host_transparent()
        self._apply_native_pill_shape()
        Thread(target=self._drain_actions, name="parrot-flow-hud", daemon=True).start()

    def _make_native_host_transparent(self) -> None:
        """Remove the WinForms host surface behind the HTML control.

        WebView2's transparent pixels otherwise reveal its native host, which is
        the faint rectangular backdrop visible around the rounded CSS panel.
        The chroma key exists only in the host; the HTML itself never paints it.
        """
        native_window = self._window.native
        if native_window is None:
            return
        from System.Drawing import Color

        chroma_key = Color.FromArgb(255, 0, 255)
        native_window.BackColor = chroma_key
        native_window.TransparencyKey = chroma_key
        native_window.webview.DefaultBackgroundColor = Color.Transparent

    def _apply_native_pill_shape(self) -> None:
        native_window = self._window.native
        if native_window is None:
            return
        width, height = native_window.Width, native_window.Height
        region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, height, height)
        if region:
            # Windows owns the region after a successful SetWindowRgn call.
            ctypes.windll.user32.SetWindowRgn(native_window.Handle.ToInt64(), region, True)

    def _drain_actions(self) -> None:
        while not self._closed.is_set():
            try:
                action = self._actions.get(timeout=0.25)
            except Empty:
                continue
            if action == "close":
                self._closed.set()
                self._window.destroy()
                return
            if action == "hide":
                self._minimized = True
                self._window.hide()
                continue
            if action == "idle" and self._minimized:
                continue
            self._minimized = False
            if action == "recording":
                self._window.resize(_RECORDING_WIDTH, _HEIGHT)
                self._window.evaluate_js("setHudState('recording')")
            else:
                self._window.resize(_IDLE_WIDTH, _HEIGHT)
                self._window.evaluate_js("setHudState('idle')")
            self._apply_native_pill_shape()
            self._window.show()
