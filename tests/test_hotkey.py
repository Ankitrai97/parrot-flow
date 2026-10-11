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
