"""Opt-in desktop smoke fixture. No microphone, user documents or cloud calls.

Run `python tests/desktop_smoke.py editor` and `python tests/desktop_smoke.py control`.
Focus the blank test editor, then use the fixture control's Start and Stop buttons.
"""
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import webview

from localdictate.config import Settings
from localdictate.hud import RecordingHud
from localdictate.injection import WindowsTextInjector
from localdictate.service import RecordingController

TEXT = ("This is a synthetic Parrot Flow insertion test. Complete text should appear together.\n" * 14
        + "Last line: café, हिंदी, 🙂.")
REPORT = Path(__file__).resolve().parent.parent / "outputs/desktop-smoke.json"


class EditorApi:
    def received(self, text):
        # Record only metrics, not clipboard or user content.
        REPORT.write_text(json.dumps({"exact_match": text.replace("\r\n", "\n") == TEXT,
                                      "characters": len(text), "expected": len(TEXT)}), encoding="utf-8")


class Recorder:
    def __init__(self, *args): pass
    def start(self): pass
    def stop(self): return np.ones(16000, dtype=np.float32)


class Transcriber:
    def transcribe(self, audio):
        time.sleep(3)  # Deliberate time to verify disabled controls.
        return TEXT


if sys.argv[-1] == "editor":
    editor_window = webview.create_window("Parrot Flow — Test editor", html="""<html><meta charset="utf-8">
    <style>body{font:18px Segoe UI;padding:25px;background:#eef4fa}textarea{width:100%;height:65%;font:16px Segoe UI}</style>
    <h2>Parrot Flow insertion test</h2><p>Disposable test field. No personal documents.</p>
    <textarea id="editor" aria-label="Test dictation field"></textarea><p id="result">Empty</p>
    <script>document.getElementById('editor').oninput=e=>{
    document.getElementById('result').textContent=e.target.value.length+' characters received';
    window.pywebview.api.received(e.target.value);};</script></html>""",
                          js_api=EditorApi(), width=750, height=620)
    editor_window.events.loaded += editor_window.show
    webview.start(private_mode=True)
else:
    logging.basicConfig(level=logging.INFO)
    controller = RecordingController(Settings(), Transcriber(), WindowsTextInjector(),
                                     logging.getLogger("smoke"), Recorder,
                                     on_recording_started=lambda: hud.show_recording(),
                                     on_recording_stopped=lambda: hud.show_idle(),
                                     on_status=lambda state, message: hud.show_status(state, message))
    hud = RecordingHud(controller.cancel, controller.start, controller.stop,
                       is_busy=lambda: controller.busy, on_insert=controller.insert_pending,
                       title="Parrot Flow — Test control")
    hud.show_idle()
    try:
        hud.run()
    finally:
        controller.close()
