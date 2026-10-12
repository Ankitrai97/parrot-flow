from localdictate.hotkey import PushToTalkHotkey


def test_windows_trigger_accepts_both_physical_windows_keys():
    assert PushToTalkHotkey._matching_key_names("windows") == {
        "windows", "win", "left windows", "right windows", "left win", "right win"
    }


def test_regular_trigger_stays_exact():
    assert PushToTalkHotkey._matching_key_names("space") == {"space"}


def test_toggle_uses_controller_state_after_cancel():
    import logging
    active = [False]
    starts = []
    def start():
        active[0] = True
        starts.append(True)
        return True
    def stop(): active[0] = False
    hotkey = PushToTalkHotkey("ctrl+space", start, stop, logging.getLogger("test"),
                             is_recording=lambda: active[0])
    hotkey._press()
    active[0] = False  # HUD cancel / silence stop / device failure
    hotkey._press()
    assert len(starts) == 2
    hotkey.close()


def test_failed_start_does_not_leave_hotkey_in_recording_state():
    import logging
    hotkey = PushToTalkHotkey("ctrl+space", lambda: False, lambda: None, logging.getLogger("test"))
    hotkey._press()
    assert not hotkey._active
    hotkey.close()


def test_stale_control_cache_cannot_turn_windows_search_into_dictation(monkeypatch):
    import logging

    import keyboard

    monkeypatch.setattr(keyboard, "is_pressed", lambda key: True)
    starts = []
    hotkey = PushToTalkHotkey("ctrl+windows", lambda: starts.append(True), lambda: None,
                             logging.getLogger("test"), key_is_down=lambda key: key == "windows")
    hotkey._armed.set()
    hotkey._observe_chord(all(hotkey._key_is_down(key) for key in hotkey._keys))
    hotkey._executor.submit(lambda: None).result(timeout=2)
    assert starts == []
    hotkey.close()


def test_launch_chord_is_ignored_and_each_fresh_chord_toggles_once():
    import logging

    starts = []
    hotkey = PushToTalkHotkey("ctrl+windows", lambda: starts.append(True), lambda: None,
                             logging.getLogger("test"), key_is_down=lambda key: True)
    hotkey._observe_chord(True)
    hotkey._executor.submit(lambda: None).result(timeout=2)
    assert starts == []
    hotkey._armed.set()
    hotkey._observe_chord(False)
    hotkey._observe_chord(True)
    hotkey._observe_chord(True)
    hotkey._executor.submit(lambda: None).result(timeout=2)
    assert starts == [True]  # Repeated key-down does not toggle again.
    hotkey.close()


def test_arming_waits_for_all_launch_keys_to_be_released(monkeypatch):
    import logging
    from types import SimpleNamespace

    import localdictate.hotkey as module

    elapsed = [0.0]
    hotkey = PushToTalkHotkey("ctrl+windows", lambda: None, lambda: None,
                             logging.getLogger("test"), key_is_down=lambda key: elapsed[0] < 0.1)
    monkeypatch.setattr(module.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(module.time, "time", lambda: 100 + elapsed[0])
    hotkey._closed = SimpleNamespace(is_set=lambda: False,
                                    wait=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
                                    set=lambda: None)
    hotkey._arm_when_released()
    assert elapsed[0] >= 0.3
    assert hotkey._armed.is_set()
    hotkey.close()


def test_quick_start_and_stop_survive_keys_being_released_before_callback_runs():
    import logging
    from threading import Event

    import numpy as np

    from localdictate.config import Settings
    from localdictate.service import RecordingController

    class Recorder:
        def __init__(self, *args):
            pass
        def start(self):
            pass
        def stop(self):
            return np.array([0.1, 0.2], dtype=np.float32)
    class Transcriber:
        def transcribe(self, audio):
            return "Hello world"
    class Injector:
        def __init__(self):
            self.text = []
        def inject(self, text):
            self.text.append(text)

    blocked, unblock = Event(), Event()
    controller = RecordingController(Settings(), Transcriber(), Injector(),
                                     logging.getLogger("test"), Recorder)
    hotkey = PushToTalkHotkey("ctrl+windows", controller.start, controller.stop,
                             logging.getLogger("test"), is_recording=lambda: controller.recording,
                             key_is_down=lambda key: False)
    hotkey._armed.set()
    def delay_callback():
        blocked.set()
        assert unblock.wait(3)
    hotkey._executor.submit(delay_callback)
    assert blocked.wait(3)
    hotkey._observe_chord(True)
    hotkey._observe_chord(False)
    unblock.set()
    hotkey._executor.submit(lambda: None).result(timeout=3)
    assert controller.recording
    hotkey._observe_chord(True)
    hotkey._observe_chord(False)
    hotkey._executor.submit(lambda: None).result(timeout=3)
    assert not controller.recording
    controller._executor.shutdown(wait=True)
    assert controller.injector.text == ["Hello world"]
    hotkey.close()
    controller.close()


def test_real_poll_thread_observes_physical_press_release_and_stop():
    import logging
    from threading import Event

    pressed = set()
    started, stopped = Event(), Event()
    active = [False]
    def start():
        active[0] = True
        started.set()
        return True
    def stop():
        active[0] = False
        stopped.set()
    hotkey = PushToTalkHotkey("ctrl+windows", start, stop, logging.getLogger("test"),
                             is_recording=lambda: active[0], key_is_down=pressed.__contains__)
    hotkey.start()
    try:
        assert hotkey._armed.wait(2)
        pressed.update(("ctrl", "windows"))
        assert started.wait(2)
        pressed.clear()
        # Wait until the polling thread observes release, not a hard-coded delay.
        import time
        deadline = time.monotonic() + 2
        while hotkey._chord_down and time.monotonic() < deadline:
            Event().wait(0.005)
        assert not hotkey._chord_down
        pressed.update(("ctrl", "windows"))
        assert stopped.wait(2)
        assert not active[0]
    finally:
        pressed.clear()
        hotkey.close()


def test_physical_state_uses_current_down_bit_and_both_windows_keys():
    from localdictate.hotkey import _WindowsKeyState

    reader = _WindowsKeyState(["ctrl", "windows", "space"])
    reader._get_state = lambda code: 1  # Previously pressed, currently up.
    assert not reader("ctrl")
    assert not reader("windows")
    reader._get_state = lambda code: 0x8000 if code == 0x5C else 0
    assert reader("windows")
    assert not reader("ctrl")
    assert reader._codes["space"] == (0x20,)
