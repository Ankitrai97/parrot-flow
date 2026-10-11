import logging
from threading import Lock

from localdictate.injection import WindowsTextInjector


def test_foreground_tracker_does_not_overwrite_current_dictation_target():
    injector = WindowsTextInjector.__new__(WindowsTextInjector)
    injector._logger = logging.getLogger("test")
    injector._target_lock = Lock()
    injector._target_window = 100
    injector._dictation_target = None
    injector._remember_foreground = lambda: None
    injector.capture_focus()
    injector._target_window = 200  # User opened another app during inference.
    activated = []
    injector._activate_target = lambda target: activated.append(target) or True
    injector._typing_delay = 0
    injector._get_key_state = lambda key: 0
    injector._get_foreground = lambda: 100
    injector._send_input = lambda count, events, size: count
    injector.inject("x")
    assert activated == [100]


def test_long_transcript_tail_and_unicode_are_sent_in_paced_character_groups(monkeypatch):
    import localdictate.injection as module
    text = "Tomorrow morning, I need to send the proposal to John before ten thirty, and then call Sarah to confirm the meeting. 🙂"
    injector = WindowsTextInjector.__new__(WindowsTextInjector)
    injector._logger = logging.getLogger("test")
    injector._target_lock = Lock()
    injector._dictation_target = None
    injector._typing_delay = 0.01
    injector._get_key_state = lambda key: 0
    units, calls, pauses = [], [], []
    def send(count, events, size):
        calls.append(count)
        for event in events:
            if not event.union.ki.dwFlags & module.KEYEVENTF_KEYUP:
                units.append(event.union.ki.wScan)
        return count
    injector._send_input = send
    monkeypatch.setattr(module.time, "sleep", pauses.append)
    injector.inject(text)
    actual = b"".join(unit.to_bytes(2, "little") for unit in units).decode("utf-16-le")
    assert actual == text
    assert len(calls) == len(text)
    assert max(calls) == 4  # Both halves of a surrogate stay in one group.
    assert pauses == [0.01] * len(text)


def test_insertion_waits_until_shortcut_modifiers_are_released(monkeypatch):
    import localdictate.injection as module
    injector = WindowsTextInjector.__new__(WindowsTextInjector)
    pressed = [True]
    injector._get_key_state = lambda key: 0x8000 if pressed[0] else 0
    monkeypatch.setattr(module.time, "sleep", lambda seconds: pressed.__setitem__(0, False))
    injector._wait_for_modifiers()
    assert not pressed[0]
