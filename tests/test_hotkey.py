from localdictate.hotkey import PushToTalkHotkey


def test_windows_trigger_accepts_both_physical_windows_keys():
    assert PushToTalkHotkey._matching_key_names("windows") == {
        "windows", "win", "left windows", "right windows", "left win", "right win"
    }


def test_regular_trigger_stays_exact():
    assert PushToTalkHotkey._matching_key_names("space") == {"space"}
