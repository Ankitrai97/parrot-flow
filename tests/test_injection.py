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
    injector._window_process_id = lambda window: 9 if window == 100 else 8
    injector._own_process_id = 8
    injector.mode = "unicode"
    injector.capture_focus()
    injector._target_window = 200  # User opened another app during inference.
    activated = []
    injector._activate_target = lambda target: activated.append(target) or True
    injector._typing_delay = 0
    injector._get_key_state = lambda key: 0
    foreground = [200]
    def activate(target):
        activated.append(target)
        foreground[0] = target
        return True
    injector._activate_target = activate
    injector._get_foreground = lambda: foreground[0]
    injector._send_input = lambda count, events, size: count
    injector.inject("x")
    assert activated == [100]


def test_long_transcript_tail_and_unicode_are_sent_in_paced_character_groups(monkeypatch):
    import localdictate.injection as module
    text = "Tomorrow morning, I need to send the proposal to John before ten thirty, and then call Sarah to confirm the meeting. 🙂"
    injector = WindowsTextInjector.__new__(WindowsTextInjector)
    injector._logger = logging.getLogger("test")
    injector._target_lock = Lock()
    injector._dictation_target = 100
    injector._dictation_pid = 9
    injector._window_process_id = lambda window: 9
    injector._get_foreground = lambda: 100
    injector.mode = "unicode"
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


def make_injector():
    injector = WindowsTextInjector.__new__(WindowsTextInjector)
    injector._logger = logging.getLogger("test")
    injector._target_lock = Lock()
    injector._dictation_target, injector._dictation_pid = 100, 9
    injector._own_process_id = 8
    injector._window_process_id = lambda window: 9
    injector._get_foreground = lambda: 100
    injector._get_key_state = lambda key: 0
    injector._typing_delay = 0
    injector.mode = "unicode"
    return injector


def test_legacy_unicode_uses_paced_compatibility_not_unvalidated_bursts(monkeypatch):
    import localdictate.injection as module
    injector = make_injector()
    calls, units, pauses = [], [], []
    def send(count, events, size):
        calls.append(count)
        units.extend(e.union.ki.wScan for e in events if not e.union.ki.dwFlags & module.KEYEVENTF_KEYUP)
        return count
    injector._send_input = send
    monkeypatch.setattr(module.time, "sleep", pauses.append)
    injector.inject("Hello 🙂 हिंदी")
    assert len(calls) == len("Hello 🙂 हिंदी")
    assert pauses == [0.01] * len("Hello 🙂 हिंदी")
    assert b"".join(x.to_bytes(2, "little") for x in units).decode("utf-16-le") == "Hello 🙂 हिंदी"


def test_focus_switch_defers_without_stealing_focus_or_sending_input():
    import pytest

    from localdictate.injection import InjectionDeferred
    injector = make_injector()
    injector._get_foreground = lambda: 200
    injector._send_input = lambda *args: pytest.fail("must not type into another app")
    injector._activate_target = lambda *args: pytest.fail("must not steal focus")
    with pytest.raises(InjectionDeferred):
        injector.inject("Do not lose this")


def test_paste_uses_one_chord_and_never_retries_after_restore_failure(monkeypatch):
    from contextlib import contextmanager

    import localdictate.injection as module
    from localdictate import clipboard
    saved, calls = [], []
    class FakeClipboard:
        @contextmanager
        def temporary(self, text):
            saved.append(text)
            yield
            raise clipboard.ClipboardUnavailable("restore busy")
    monkeypatch.setattr(clipboard, "ClipboardText", FakeClipboard)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    injector = make_injector()
    injector.mode = "paste"
    injector._send_input = lambda count, events, size: calls.append(count) or count
    injector.inject("All at once\nSecond line")
    assert saved == ["All at once\nSecond line"]
    assert calls == [4]


def test_partial_paste_is_not_followed_by_duplicate_keyboard_insertion(monkeypatch):
    from contextlib import contextmanager

    import pytest

    from localdictate import clipboard
    from localdictate.injection import PartialInsertionError
    class FakeClipboard:
        @contextmanager
        def temporary(self, text): yield
    monkeypatch.setattr(clipboard, "ClipboardText", FakeClipboard)
    injector = make_injector()
    injector.mode = "paste"
    calls = []
    injector._send_input = lambda count, events, size: calls.append(count) or 1
    with pytest.raises(PartialInsertionError):
        injector.inject("Hello")
    assert calls == [4, 2]  # Failed paste then key-up recovery only.


def test_unavailable_clipboard_defers_without_any_fallback_typing():
    import pytest
    from localdictate.injection import InjectionDeferred
    injector = make_injector()
    injector.mode = "paste"
    injector._paste = lambda *args: False
    injector._send_input = lambda *args: pytest.fail("unsafe fallback must not run")
    with pytest.raises(InjectionDeferred, match="copy plain text"):
        injector.inject("Complete transcript retained")
