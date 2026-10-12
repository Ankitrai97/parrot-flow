import logging
import sys
from threading import Event
from types import SimpleNamespace

from localdictate import __main__ as application
from localdictate.config import Settings
from localdictate.service import RecordingController


def test_launch_and_model_preparation_stay_idle_without_opening_microphone(monkeypatch):
    ready = Event()
    statuses, audio_actions = [], []
    controllers = []

    class Hud:
        def __init__(self, cancel, toggle, on_stop):
            self.toggle, self.stop = toggle, on_stop

        def show_idle(self):
            statuses.append(("idle", ""))

        def show_status(self, state, message):
            statuses.append((state, message))
            if message.startswith("Ready"):
                ready.set()

        def run(self):
            assert ready.wait(5)
            assert all(state == "idle" for state, _ in statuses)
            assert not controllers[0].recording
            assert audio_actions == []

        def show(self):
            self.show_idle()

    class Transcriber:
        def __init__(self, settings, logger):
            self.settings = settings

        def warm_up(self):
            pass

        def transcribe(self, audio):
            audio_actions.append("transcribe")
            return "Unexpected"

    class Injector:
        def __init__(self, delay):
            pass

        def inject(self, text):
            audio_actions.append("inject")

    class Guard:
        def acquire(self):
            return True

        def wait_for_show(self):
            Event().wait(0.025)
            return False

        def close(self):
            pass

    def controller(*args, **kwargs):
        def recorder(*args):
            audio_actions.append("microphone")
            raise AssertionError("Startup must never open the microphone")
        result = RecordingController(*args, recorder_factory=recorder, **kwargs)
        controllers.append(result)
        return result

    monkeypatch.setitem(sys.modules, "localdictate.hud", SimpleNamespace(RecordingHud=Hud))
    monkeypatch.setattr(sys, "argv", ["parrot-flow"])
    monkeypatch.setattr(application, "load_settings", lambda: Settings())
    monkeypatch.setattr(application, "configure_logging", lambda: logging.getLogger("test"))
    monkeypatch.setattr(application, "FasterWhisperTranscriber", Transcriber)
    monkeypatch.setattr(application, "RecordingController", controller)
    monkeypatch.setattr(application, "WindowsTextInjector", Injector)
    monkeypatch.setattr(application, "SingleInstanceGuard", Guard)
    monkeypatch.setattr(application, "PushToTalkHotkey",
                        lambda *args, **kwargs: SimpleNamespace(start=lambda: None, close=lambda: None))
    monkeypatch.setattr(application.signal, "signal", lambda *args: None)
    application._main()
    assert statuses[0] == ("idle", "")
    assert audio_actions == []
