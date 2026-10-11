import logging
from types import SimpleNamespace

import numpy as np
import pytest

from localdictate.config import Settings
from localdictate.transcription import FasterWhisperTranscriber


def test_lazy_cuda_failure_retries_same_audio_on_cpu(monkeypatch):
    calls = []
    transcriber = FasterWhisperTranscriber(Settings(), logging.getLogger("test"))

    class Model:
        def transcribe(self, audio, **kwargs):
            calls.append((transcriber.settings.device, audio))
            assert kwargs["beam_size"] == 5
            assert kwargs["vad_filter"] is False

            def segments():
                if transcriber.settings.device == "cuda":
                    yield SimpleNamespace(text="partial text that must not be duplicated")
                    raise RuntimeError("CUDA failure during segment iteration")
                yield SimpleNamespace(text="Recovered dictation")

            return segments(), SimpleNamespace(language="en")

    monkeypatch.setattr(transcriber, "_get_model", lambda: Model())
    audio = np.ones(16000, dtype=np.float32)
    assert transcriber.transcribe(audio) == "Recovered dictation"
    assert [item[0] for item in calls] == ["cuda", "cpu"]
    assert all(item[1] is audio for item in calls)


def test_warmup_exercises_encoder_and_consumes_generator(monkeypatch):
    transcriber = FasterWhisperTranscriber(Settings(), logging.getLogger("test"))
    consumed = []

    class Model:
        def transcribe(self, audio, **kwargs):
            assert audio.size == 16000
            assert kwargs["vad_filter"] is False

            def segments():
                consumed.append(True)
                yield SimpleNamespace(text="")

            return segments(), SimpleNamespace(language="en")

    monkeypatch.setattr(transcriber, "_get_model", lambda: Model())
    transcriber.warm_up()
    assert consumed == [True]


def test_packaged_cuda_directories_are_registered_in_path(tmp_path, monkeypatch):
    import localdictate.transcription as module
    folders = [tmp_path / "nvidia" / lib / "bin" for lib in ("cublas", "cudnn")]
    for folder in folders:
        folder.mkdir(parents=True)
    registered = []
    monkeypatch.setattr(module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(module.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(module.sys, "prefix", str(tmp_path / "empty"))
    monkeypatch.setattr(module.os, "add_dll_directory", lambda path: registered.append(path))
    monkeypatch.setenv("PATH", "original")
    transcriber = FasterWhisperTranscriber(Settings(), logging.getLogger("test"))
    transcriber._configure_cuda_runtime()
    transcriber._configure_cuda_runtime()
    assert registered == [str(folder) for folder in folders]
    assert module.os.environ["PATH"].endswith("original")
    assert str(folders[0]) in module.os.environ["PATH"]


def test_cpu_runtime_failure_is_not_retried_forever(monkeypatch):
    transcriber = FasterWhisperTranscriber(Settings(device="cpu", compute_type="int8"),
                                         logging.getLogger("test"))
    def fail():
        raise RuntimeError("out of memory")
    monkeypatch.setattr(transcriber, "_get_model", fail)
    with pytest.raises(RuntimeError, match="out of memory"):
        transcriber.transcribe(np.ones(16000, dtype=np.float32))
