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
