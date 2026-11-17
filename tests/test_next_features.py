import logging
import time
from dataclasses import asdict

import numpy as np
import pytest

from localdictate.audio import MicrophoneRecorder
from localdictate.config import Settings, load_settings, save_settings
from localdictate.dictionary import apply_dictionary, parse_rules
from localdictate.service import RecordingController
from localdictate.settings_ui import updated_settings
from test_service import Injector, Recorder, Transcriber


def test_dictionary_longest_phrase_whole_words_and_no_cascade():
    rules = 'parrot => bird\nparrot flow => Parrot Flow\nbird => eagle'
    assert apply_dictionary('PARROT FLOW, parrot, parrots, bird.', rules) == 'Parrot Flow, bird, parrots, eagle.'


@pytest.mark.parametrize('rules', ['bad line', 'x =>', '=> y', 'X => a\nx => b'])
def test_bad_dictionary_rejected(rules):
    with pytest.raises(ValueError): parse_rules(rules)


def test_dictionary_roundtrip_and_settings_validation(tmp_path):
    rules = 'parrot low => Parrot Flow\nहिंदी => हिन्दी'
    settings = updated_settings(Settings(), asdict(Settings()) | {'dictionary_rules': rules})
    path = tmp_path / 'config.toml'
    save_settings(settings, path)
    assert load_settings(path).dictionary_rules == rules


def test_actual_audio_meter_and_stale_samples():
    recorder = MicrophoneRecorder(16000, None)
    recorder._capture(np.full((160, 1), .02, dtype=np.float32), 160, None, False)
    level, active = recorder.meter()
    assert active and level == pytest.approx(.02)
    recorder._last_capture_at = time.monotonic() - 2
    assert not recorder.meter()[1]


def test_dictionary_delivery_and_recovery_never_injects_until_requested():
    injector = Injector()
    controller = RecordingController(Settings(dictionary_rules='hello world => Hello Ankit'),
        Transcriber(), injector, logging.getLogger('test'), Recorder)
    controller.start()
    controller.stop()
    controller._executor.submit(lambda: None).result(3)
    assert injector.text == ['Hello Ankit']
    assert controller.recovery_text() == 'Hello Ankit'
    controller.prepare_recovery('Edited result')
    assert controller.pending_text == 'Edited result'
    assert injector.text == ['Hello Ankit']
    assert not controller.start()
    controller.clear_recovery()
    assert not controller.recovery_text()
    controller.close()


def test_recovery_protected_during_recording():
    controller = RecordingController(Settings(), Transcriber(), Injector(), logging.getLogger('test'), Recorder)
    controller.start()
    for action in (controller.recovery_text, controller.clear_recovery,
                   lambda: controller.prepare_recovery('text')):
        with pytest.raises(ValueError): action()
    controller.close()
