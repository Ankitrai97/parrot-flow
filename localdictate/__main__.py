from __future__ import annotations

import signal
from threading import Event
import argparse
from dataclasses import replace

from .config import load_settings
from .diagnostics import list_input_devices, test_microphone
from .hotkey import PushToTalkHotkey
from .hud import RecordingHud
from .injection import WindowsTextInjector
from .instance_guard import SingleInstanceGuard
from .logging_setup import configure_logging
from .service import RecordingController
from .startup import disable_at_login, enable_at_login
from .transcription import FasterWhisperTranscriber


def main() -> None:
    parser = argparse.ArgumentParser(description="Parrot Flow local voice-to-text service")
    parser.add_argument("--list-devices", action="store_true", help="List available microphone IDs")
    parser.add_argument("--test-mic", action="store_true", help="Record 5 seconds and show microphone level")
    parser.add_argument("--device", type=int, help="Use this microphone ID for a diagnostic command")
    parser.add_argument("--install-startup", action="store_true", help="Start LocalDictate silently at Windows sign-in")
    parser.add_argument("--remove-startup", action="store_true", help="Disable LocalDictate Windows sign-in startup")
    arguments = parser.parse_args()
    settings = load_settings()
    if arguments.install_startup:
        enable_at_login()
        print("Parrot Flow will now start silently when you sign in to Windows.")
        return
    if arguments.remove_startup:
        disable_at_login()
        print("Parrot Flow Windows sign-in startup disabled.")
        return
    if arguments.device is not None:
        settings = replace(settings, microphone=arguments.device)
    if arguments.list_devices:
        list_input_devices()
        return
    if arguments.test_mic:
        test_microphone(settings)
        return
    instance_guard = SingleInstanceGuard()
    if not instance_guard.acquire():
        print("Parrot Flow is already running. Close the existing copy before starting another one.")
        return
    logger = configure_logging()
    logger.info("Parrot Flow starting")
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

    transcriber = FasterWhisperTranscriber(settings, logger)
    try:
        transcriber.warm_up()
    except Exception:
        logger.exception("Unable to prepare the transcription model at startup")
        raise
    controller = RecordingController(settings, transcriber, WindowsTextInjector(), logger,
                                     on_recording_started=show_hud, on_recording_stopped=hide_hud,
                                     on_live_preview=update_hud)
    hud = RecordingHud(controller.start, controller.stop, controller.cancel)
    hotkey = PushToTalkHotkey(settings.hotkey, controller.start, controller.stop, logger, settings.hotkey_mode)
    stopped = Event()
    def shutdown(*_args: object) -> None:
        stopped.set()
        controller.stop()
        hud.close()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        hotkey.start()
        print(f"Parrot Flow ready. Press {settings.hotkey} to start/stop; press Ctrl+C to quit.")
        hud.run()
    finally:
        hotkey.close()
        controller.close()
        logger.info("Parrot Flow stopped")
        instance_guard.close()


if __name__ == "__main__":
    main()
