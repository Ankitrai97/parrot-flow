from types import SimpleNamespace

from localdictate.hud import RecordingHud, _HudApi


def test_hud_bridge_requires_an_explicit_user_click_to_start():
    starts = []
    api = _HudApi(SimpleNamespace(toggle=lambda: starts.append(True)))
    api.toggle()
    api.toggle(False)
    assert starts == []
    api.toggle(True)
    assert starts == [True]


def test_stop_control_never_toggles_into_a_new_recording():
    actions = []
    hud = RecordingHud.__new__(RecordingHud)
    hud._on_stop = lambda: actions.append("stop")
    hud._on_toggle = lambda: actions.append("start")
    api = _HudApi(hud)
    api.stop()
    api.stop()  # Repeated stop while idle stays a stop operation.
    assert actions == ["stop", "stop"]
