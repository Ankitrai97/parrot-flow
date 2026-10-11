from __future__ import annotations

import argparse
import ctypes
import json
import signal
import sys
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread

from . import __version__
from .config import load_settings
from .diagnostics import list_input_devices, test_microphone
from .hotkey import PushToTalkHotkey
from .injection import WindowsTextInjector
from .instance_guard import SingleInstanceGuard
from .logging_setup import configure_logging
from .service import RecordingController
from .startup import (
    disable_at_login,
    enable_at_login,
    install_start_menu_shortcut,
    remove_start_menu_shortcut,
)
from .transcription import FasterWhisperTranscriber


def _main() -> None:
    parser = argparse.ArgumentParser(description="Parrot Flow local voice-to-text service")
    parser.add_argument("--list-devices", action="store_true", help="List available microphone IDs")
    parser.add_argument("--test-mic", action="store_true", help="Record 5 seconds and show microphone level")
    parser.add_argument("--device", type=int, help="Use this microphone ID for a diagnostic command")
    parser.add_argument("--install-startup", action="store_true", help="Start Parrot Flow silently at Windows sign-in")
    parser.add_argument("--remove-startup", action="store_true", help="Disable Parrot Flow Windows sign-in startup")
    parser.add_argument("--install-app", action="store_true", help="Add Parrot Flow to the Windows Start Menu")
    parser.add_argument("--remove-app", action="store_true", help="Remove the Parrot Flow Start Menu shortcut")
    parser.add_argument("--check-model", action="store_true", help="Run a real model inference health check")
    parser.add_argument("--transcribe-file", type=Path, help="Transcribe a local audio file without typing it")
    parser.add_argument("--diagnostic-output", type=Path, help="Save diagnostic output (also works in the EXE)")
    arguments = parser.parse_args()
    logger = configure_logging()
    if arguments.diagnostic_output:
        # A windowed executable has no stdout/stderr. Explicit diagnostics can
        # still write a report without needing a console window.
        stream = arguments.diagnostic_output.open("w", encoding="utf-8")
        sys.stdout = sys.stderr = stream
    settings = load_settings()
    if arguments.install_startup:
        enable_at_login()
        print("Parrot Flow will now start silently when you sign in to Windows.")
        return
    if arguments.remove_startup:
        disable_at_login()
        print("Parrot Flow Windows sign-in startup disabled.")
        return
    if arguments.install_app:
        shortcut_path = install_start_menu_shortcut()
        print(f"Parrot Flow Start Menu shortcut installed: {shortcut_path}")
        return
    if arguments.remove_app:
        remove_start_menu_shortcut()
        disable_at_login()
        print("Parrot Flow Start Menu shortcut removed.")
        return
    if arguments.device is not None:
        settings = replace(settings, microphone=arguments.device, microphone_name=None)
    if arguments.list_devices:
        list_input_devices()
        return
    if arguments.test_mic:
        test_microphone(settings)
        return
    if arguments.check_model or arguments.transcribe_file:
        transcriber = FasterWhisperTranscriber(settings, logger)
        transcriber.warm_up()
        report = {"version": __version__, "device": transcriber.settings.device, "compute_type": transcriber.settings.compute_type,
                  "model": settings.model}
        if arguments.transcribe_file:
            from faster_whisper.audio import decode_audio
            audio = decode_audio(str(arguments.transcribe_file), sampling_rate=settings.sample_rate)
            report["transcript"] = transcriber.transcribe(audio)
        print(json.dumps(report, ensure_ascii=False), flush=True)
        return
    instance_guard = SingleInstanceGuard()
    if not instance_guard.acquire():
        logger.info("Existing Parrot Flow instance asked to show its control")
        return
    logger.info("Parrot Flow %s starting: executable=%s", __version__, sys.executable)
    from .hud import RecordingHud
    hud: RecordingHud | None = None

    def show_hud() -> None:
        if hud:
            hud.show_recording()

    def hide_hud() -> None:
        if hud:
            hud.show_idle()

    def update_hud(text: str) -> None:
        if hud:
            hud.update_preview(text)

    def status_hud(state: str, message: str) -> None:
        if hud:
            hud.show_status(state, message)

    transcriber = FasterWhisperTranscriber(settings, logger)
    controller = RecordingController(settings, transcriber,
                                     WindowsTextInjector(settings.injection_delay_seconds), logger,
                                     on_recording_started=show_hud, on_recording_stopped=hide_hud,
                                     on_live_preview=update_hud, on_status=status_hud)
    controller.ready = False
    preparing = Event()

    def prepare_model() -> None:
        preparing.set()
        status_hud("processing", "Preparing speech model…")
        try:
            transcriber.warm_up()
            controller.ready = True
            status_hud("idle", "Ready" if transcriber.settings.device == "cuda" else "Ready — CPU mode")
        except Exception:
            logger.exception("Unable to prepare the transcription model")
            status_hud("error", "Model unavailable. Click the light to retry; see log for details.")
        finally:
            preparing.clear()

    def start_recording() -> bool:
        if not controller.ready and not preparing.is_set():
            preparing.set()
            Thread(target=prepare_model, name="model-prepare", daemon=True).start()
            return False
        return controller.start()

    def toggle_recording() -> None:
        if controller.recording:
            controller.stop()
        else:
            start_recording()

    hud = RecordingHud(controller.cancel, toggle_recording)
    hotkey = PushToTalkHotkey(settings.hotkey, start_recording, controller.stop, logger,
                             settings.hotkey_mode, is_recording=lambda: controller.recording)
    stopped = Event()
    def shutdown(*_args: object) -> None:
        stopped.set()
        controller.cancel()
        hud.close()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        hotkey.start()
        preparing.set()
        Thread(target=prepare_model, name="model-prepare", daemon=True).start()

        def show_requests() -> None:
            while not stopped.is_set():
                if instance_guard.wait_for_show():
                    hud.show()

        Thread(target=show_requests, name="show-requests", daemon=True).start()
        print(f"Parrot Flow ready. Press {settings.hotkey} to start/stop; press Ctrl+C to quit.")
        hud.run()
    finally:
        stopped.set()
        hotkey.close()
        controller.close()
        logger.info("Parrot Flow stopped")
        instance_guard.close()


def main() -> None:
    try:
        _main()
    except Exception:
        logger = configure_logging()
        logger.exception("Parrot Flow startup or diagnostic failed")
        if "--diagnostic-output" not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None,
                "Parrot Flow could not start. Details are in %LOCALAPPDATA%\\ParrotFlow\\logs\\parrot-flow.log",
                "Parrot Flow", 0x10)
        raise


if __name__ == "__main__":
    main()
