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


def test_fixed_hud_has_recovery_access_without_drag_handle():
    from localdictate.hud import _HTML
    assert 'class="pywebview-drag-region"' not in _HTML
    assert 'Settings and recover last transcript' in _HTML
    assert "pointer.moved" in _HTML
    assert "pointer.target !== e.target" in _HTML
    assert "querySelector('.lamp-wrap').addEventListener" not in _HTML


def test_bottom_anchor_recenters_each_size_and_excludes_taskbar():
    from localdictate.hud import _bottom_center
    work = SimpleNamespace(left=0, top=0, right=1920, bottom=1040)
    assert _bottom_center(work, 64, 24) == (928, 1004)
    assert _bottom_center(work, 132, 38) == (894, 990)
    work = SimpleNamespace(left=-1920, top=-200, right=0, bottom=840)
    assert _bottom_center(work, 132, 38, 18) == (-1026, 784)


def test_settings_stays_available_for_pending_recovery():
    actions = []
    hud = RecordingHud.__new__(RecordingHud)
    hud._is_busy = lambda: False
    hud._on_settings = lambda: actions.append('settings')
    for state in ('idle', 'pending', 'error'):
        hud._state = state
        hud.open_settings()
    assert actions == ['settings'] * 3
    for state in ('processing', 'recording'):
        hud._state = state
        hud.open_settings()
    assert len(actions) == 3


def test_native_capsule_disables_competing_windows_decoration(monkeypatch):
    import ctypes
    from ctypes import wintypes
    from localdictate import hud
    calls = []
    def attribute(handle, key, pointer, size):
        calls.append((key, ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD)).contents.value))
        return 0
    monkeypatch.setattr(hud, '_dwm_attribute', attribute)
    hud._remove_native_decoration(123)
    assert calls == [(33, 1), (34, 0xFFFFFFFE), (2, 1)]
    assert 'html, body { background: #101010; }' in hud._HTML
    assert '#hud { background: #101010; border: 0; border-radius: 0;' in hud._HTML
