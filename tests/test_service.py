import logging

import numpy as np

from localdictate.config import Settings
from localdictate.service import RecordingController


class Recorder:
    def __init__(self, *_args): self.started = False
    def start(self): self.started = True
    def stop(self): return np.array([0, 0.1, 0.2, 0], dtype=np.float32)


class Transcriber:
    def transcribe(self, audio):
        assert audio.size > 0
        return "Hello world"


class Injector:
    def __init__(self): self.text = []
    def inject(self, text): self.text.append(text)


class CancellableRecorder(Recorder):
    def __init__(self, *_args):
        super().__init__()
        self.stopped = False
    def stop(self):
        self.stopped = True
        return super().stop()


def test_controller_records_transcribes_and_injects():
    injector = Injector()
    controller = RecordingController(Settings(silence_threshold=0.01), Transcriber(), injector,
                                     logging.getLogger("test"), Recorder)
    controller.start()
    controller.stop()
    controller._executor.shutdown(wait=True)
    assert injector.text == ["Hello world"]


def test_controller_cancels_without_transcribing_or_injecting():
    injector = Injector()
    controller = RecordingController(Settings(silence_threshold=0.01), Transcriber(), injector,
                                     logging.getLogger("test"), CancellableRecorder)
    controller.start()
    recorder = controller._recorder
    controller.cancel()
    controller._executor.shutdown(wait=True)
    assert recorder.stopped
    assert injector.text == []


def test_no_audio_is_reported_and_next_recording_can_start():
    class SilentRecorder(Recorder):
        def stop(self): return np.zeros(1600, dtype=np.float32)
    statuses = []
    controller = RecordingController(Settings(live_preview=False), Transcriber(), Injector(),
                                     logging.getLogger("test"), SilentRecorder,
                                     on_status=lambda state, message: statuses.append((state, message)))
    controller.start()
    controller.stop()
    assert statuses[-1][0] == "error"
    assert "No voice" in statuses[-1][1]
    assert controller.start() is True
    controller.close()


def test_failed_microphone_start_can_be_retried():
    class BrokenRecorder(Recorder):
        def start(self): raise RuntimeError("unplugged")
    statuses = []
    controller = RecordingController(Settings(live_preview=False), Transcriber(), Injector(),
                                     logging.getLogger("test"), BrokenRecorder,
                                     on_status=lambda state, message: statuses.append(state))
    assert controller.start() is False
    assert not controller.recording
    assert statuses == ["error"]
    controller._factory = Recorder
    assert controller.start() is True
    controller.close()


def test_processing_prevents_another_dictation_overwriting_target():
    from threading import Event
    started, finish = Event(), Event()
    class SlowTranscriber:
        def transcribe(self, audio):
            started.set()
            assert finish.wait(5)
            return "Finished"
    injector = Injector()
    controller = RecordingController(Settings(live_preview=False), SlowTranscriber(), injector,
                                     logging.getLogger("test"), Recorder)
    controller.start()
    controller.stop()
    assert started.wait(5)
    assert controller.start() is False
    finish.set()
    controller._executor.shutdown(wait=True)
    assert injector.text == ["Finished"]


def test_transcription_failure_releases_busy_state_and_reports_error():
    class BrokenTranscriber:
        def transcribe(self, audio): raise RuntimeError("inference failed")
    statuses = []
    controller = RecordingController(Settings(live_preview=False), BrokenTranscriber(), Injector(),
                                     logging.getLogger("test"), Recorder,
                                     on_status=lambda state, message: statuses.append(state))
    controller.start()
    controller.stop()
    controller._executor.shutdown(wait=True)
    assert statuses == ["processing", "error"]
    assert not controller._busy


def test_cancel_stop_and_hotkey_cannot_interrupt_processing():
    from threading import Event
    entered, finish = Event(), Event()
    class SlowTranscriber:
        def transcribe(self, audio):
            entered.set()
            assert finish.wait(3)
            return "Complete result"
    injector = Injector()
    controller = RecordingController(Settings(), SlowTranscriber(), injector,
                                     logging.getLogger("test"), Recorder)
    controller.start()
    controller.stop()
    try:
        assert entered.wait(3)
        controller.cancel()
        controller.stop()
        assert controller.busy
        assert not controller.start()
    finally:
        finish.set()
        controller.close()
    assert injector.text == ["Complete result"]


def test_deferred_transcript_survives_focus_switch_and_inserts_once():
    from localdictate.injection import InjectionDeferred
    class FocusInjector(Injector):
        def __init__(self):
            super().__init__()
            self.focus = False
        def capture_focus(self): pass
        def inject(self, text):
            if not self.focus:
                raise InjectionDeferred()
            super().inject(text)
    injector = FocusInjector()
    controller = RecordingController(Settings(), Transcriber(), injector,
                                     logging.getLogger("test"), Recorder)
    controller.start()
    controller.stop()
    controller._executor.submit(lambda: None).result(3)
    assert controller.pending_text == "Hello world"
    assert not controller.start()
    injector.focus = True
    controller.insert_pending()
    controller._executor.submit(lambda: None).result(3)
    controller.insert_pending()
    assert injector.text == ["Hello world"]
    assert not controller.pending_text
    controller.close()


def test_ai_mode_polishes_once_and_fast_mode_never_calls_provider():
    class Enhancer:
        calls = 0
        def enhance(self, text, settings):
            self.calls += 1
            return "Hello, world!"
    for enabled in (False, True):
        enhancer, injector = Enhancer(), Injector()
        controller = RecordingController(Settings(enhance_with_llm=enabled), Transcriber(), injector,
                                         logging.getLogger("test"), Recorder, enhancer=enhancer)
        controller.start()
        controller.stop()
        controller.close()
        assert injector.text == ["Hello, world!" if enabled else "Hello world"]
        assert enhancer.calls == int(enabled)


def test_ai_timeout_uses_original_text_and_releases_controls():
    class Enhancer:
        def enhance(self, *args): raise TimeoutError()
    injector, statuses = Injector(), []
    controller = RecordingController(Settings(enhance_with_llm=True), Transcriber(), injector,
                                     logging.getLogger("test"), Recorder, enhancer=Enhancer(),
                                     on_status=lambda state, msg: statuses.append((state, msg)))
    controller.start()
    controller.stop()
    controller._executor.shutdown(wait=True)
    assert injector.text == ["Hello world"]
    assert not controller.busy
    assert statuses[-1][0] == "notice"


def test_settings_cannot_change_mid_recording_or_processing():
    controller = RecordingController(Settings(), Transcriber(), Injector(), logging.getLogger("test"), Recorder)
    saved = []
    controller.start()
    import pytest
    with pytest.raises(ValueError):
        controller.configure(Settings(enhance_with_llm=True), saved.append)
    assert saved == []
    controller.close()
