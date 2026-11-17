from io import BytesIO
import logging
import struct
from types import SimpleNamespace
import wave

from localdictate.sounds import _tone
from localdictate.config import Settings
from localdictate.injection import InjectionDeferred
from localdictate.service import RecordingController


def test_cues_are_short_quiet_pcm_with_smooth_endpoints():
    for kind in ('ready', 'inserted'):
        with wave.open(BytesIO(_tone(kind))) as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert .17 < wav.getnframes() / wav.getframerate() < .20
            data = wav.readframes(wav.getnframes())
            samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
            assert max(map(abs, samples)) <= 1966
            assert samples[0] == samples[-1] == 0
    assert _tone('ready') != _tone('inserted')


def test_completion_cue_only_after_successful_insertion():
    cues = []
    def blocked(text):
        raise InjectionDeferred('Choose a field')
    injector = SimpleNamespace(inject=blocked)
    controller = RecordingController(Settings(), None, injector, logging.getLogger('test'),
                                     on_inserted=lambda: cues.append('done'))
    try:
        controller._deliver('hello')
        assert cues == []
        assert controller.pending_text == 'hello'
        injector.inject = lambda text: None
        controller._deliver('hello')
        assert cues == ['done']
        assert controller.pending_text == ''
    finally:
        controller.close()
