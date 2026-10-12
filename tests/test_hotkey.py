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
    hotkey._armed_at = 0
    hotkey._handle(keyboard.KeyboardEvent("down", 91, name="left windows"))
    hotkey._executor.submit(lambda: None).result(timeout=2)
    assert starts == []
    hotkey.close()


def test_launch_keys_and_queued_launch_events_are_ignored_but_fresh_chord_works():
    import logging

    import keyboard

    starts = []
    hotkey = PushToTalkHotkey("ctrl+windows", lambda: starts.append(True), lambda: None,
                             logging.getLogger("test"), key_is_down=lambda key: True)
    hotkey._handle(keyboard.KeyboardEvent("down", 91, name="left windows", time=99))
    hotkey._armed_at = 100
    hotkey._armed.set()
    hotkey._handle(keyboard.KeyboardEvent("down", 91, name="left windows", time=99))
    hotkey._executor.submit(lambda: None).result(timeout=2)
    assert starts == []
    hotkey._handle(keyboard.KeyboardEvent("down", 91, name="right windows", time=101))
    hotkey._handle(keyboard.KeyboardEvent("down", 91, name="right windows", time=101.1))
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
    assert hotkey._armed_at >= 100.3
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
