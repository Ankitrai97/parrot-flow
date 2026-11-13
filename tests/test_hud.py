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
    hud._is_busy = lambda: False
    hud._state = "idle"
    hud._on_stop = lambda: actions.append("stop")
    hud._on_toggle = lambda: actions.append("start")
    api = _HudApi(hud)
    api.stop()
    api.stop()  # Repeated stop while idle stays a stop operation.
    assert actions == ["stop", "stop"]


def test_all_hud_actions_are_noops_while_busy():
    from queue import SimpleQueue
    actions = []
    hud = RecordingHud.__new__(RecordingHud)
    hud._is_busy = lambda: True
    hud._state = "idle"  # Backend protects even before the webview renders processing.
    hud._actions = SimpleQueue()
    hud._on_stop = hud._on_toggle = hud._on_cancel = lambda: actions.append(True)
    hud._on_settings = hud._on_insert = lambda: actions.append(True)
    for action in (hud.toggle, hud.stop, hud.cancel, hud.hide, hud.open_settings, hud.insert):
        action()
    assert actions == []
    assert hud._actions.empty()


def test_drag_handle_is_separate_and_status_light_is_not_a_button():
    from localdictate.hud import _HTML
    assert 'class="pywebview-drag-region"' in _HTML
    assert "pointer.moved" in _HTML
    assert "pointer.target !== e.target" in _HTML
    assert "querySelector('.lamp-wrap').addEventListener" not in _HTML
