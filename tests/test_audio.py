import numpy as np
import pytest

from localdictate.audio import MicrophoneRecorder, resolve_microphone


def test_saved_microphone_name_prefers_wasapi_even_if_ids_change(monkeypatch):
    import localdictate.audio as module
    monkeypatch.setattr(module.sd, "query_devices", lambda: [
        {"name": "Microphone Array Realtek", "max_input_channels": 2, "hostapi": 0},
        {"name": "System Input RODE", "max_input_channels": 2, "hostapi": 0},
        {"name": "Microphone Array Realtek", "max_input_channels": 2, "hostapi": 1},
    ])
    monkeypatch.setattr(module.sd, "query_hostapis", lambda: [{"name": "MME"}, {"name": "Windows WASAPI"}])
    assert resolve_microphone(None, "Microphone Array Realtek") == 2


def test_missing_saved_microphone_does_not_use_unrelated_virtual_input(monkeypatch):
    import localdictate.audio as module
    monkeypatch.setattr(module.sd, "query_devices", lambda: [])
    with pytest.raises(RuntimeError, match="unavailable"):
        resolve_microphone(None, "Realtek")


def test_native_48khz_capture_resamples_to_whisper_rate():
    recorder = MicrophoneRecorder(16000, None)
    recorder._capture_rate = 48000
    audio = np.sin(2 * np.pi * 440 * np.arange(48000) / 48000).astype(np.float32)
    result = recorder._resample(audio)
    assert result.size == 16000
    assert result.dtype == np.float32
    frequency = np.fft.rfftfreq(result.size, 1 / 16000)[np.argmax(np.abs(np.fft.rfft(result)))]
    assert frequency == 440


def test_input_overflow_preserves_current_audio_block():
    recorder = MicrophoneRecorder(16000, None)
    recorder._capture(np.ones((160, 1), dtype=np.float32), 160, None, "input overflow")
    assert recorder.stop().size == 160
