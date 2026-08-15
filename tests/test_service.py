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
