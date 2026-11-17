from localdictate.native_pill import compact_message, pill_size
from types import SimpleNamespace
import pytest


def test_idle_expands_only_horizontally():
    assert pill_size('idle') == (36, 14)
    assert pill_size('idle', True) == (66, 14)
    assert pill_size('recording', True) == (102, 28)


def test_errors_never_expand_to_fit_diagnostics():
    assert pill_size('error') == (144, 24)
    assert compact_message('error', 'No voice detected. Check your microphone or mute switch.') == 'No voice input'
    assert compact_message('pending', 'Clipboard unavailable: long diagnostic') == 'Text saved'
    assert compact_message('error', 'A very long unexpected failure') == 'Check settings'


def make_notice(monkeypatch, owner_state='error', busy=False):
    from localdictate.native_pill import NativePill
    monkeypatch.setattr('localdictate.native_pill.time.monotonic', lambda: 100.)
    calls = []
    pill = NativePill.__new__(NativePill)
    pill.owner = SimpleNamespace(_state=owner_state, _message='No voice detected',
                                 _is_busy=lambda: busy, show_idle=lambda:calls.append('idle'))
    pill.form = SimpleNamespace(Show=lambda:None)
    pill.user = SimpleNamespace(ShowWindow=lambda *args:None)
    pill.handle = 0
    pill.render = lambda:None
    pill.show('error', 'No voice detected')
    return pill, calls


def test_no_voice_returns_to_idle_after_seven_seconds(monkeypatch):
    pill, calls = make_notice(monkeypatch)
    assert pill._notice_deadline == 107.
    monkeypatch.setattr('localdictate.native_pill.time.monotonic', lambda:106.99)
    pill._expire_notice()
    assert calls == []
    monkeypatch.setattr('localdictate.native_pill.time.monotonic', lambda:107.)
    pill._expire_notice()
    pill._expire_notice()
    assert calls == ['idle']


@pytest.mark.parametrize('state,busy', [('recording',False), ('pending',False), ('error',True)])
def test_notice_timeout_cannot_override_new_work(monkeypatch, state, busy):
    pill, calls = make_notice(monkeypatch, state, busy)
    monkeypatch.setattr('localdictate.native_pill.time.monotonic', lambda:108.)
    pill._expire_notice()
    assert calls == []


def test_pending_and_actionable_errors_never_expire(monkeypatch):
    pill, _ = make_notice(monkeypatch)
    for state, message in [('pending','Text saved'), ('processing','Working'), ('error','Model unavailable')]:
        pill.show(state, message)
        assert pill._notice_deadline is None
