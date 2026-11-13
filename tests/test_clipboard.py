from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from localdictate.clipboard import ClipboardText, ClipboardUnavailable


def transaction(sequence_after=10):
    clipboard = ClipboardText.__new__(ClipboardText)
    sequence, writes = [10], []
    clipboard.u = SimpleNamespace(CreateWindowExW=lambda *a: 42, DestroyWindow=lambda h: True,
                                  GetClipboardSequenceNumber=lambda: sequence[0])
    @contextmanager
    def opened(owner): yield
    clipboard._open = opened
    clipboard._snapshot = lambda: [(13, b"original")]
    clipboard._replace = writes.append
    clipboard.private_formats = [100, 101]
    return clipboard, sequence, writes


def test_paste_restores_snapshot_and_excludes_history_and_cloud():
    clipboard, sequence, writes = transaction()
    with clipboard.temporary("Hello\nworld"):
        assert writes[0][:2] == [(100, b"\0" * 4), (101, b"\0" * 4)]
        assert writes[0][2] == (13, "Hello\r\nworld\0".encode("utf-16-le"))
    assert writes[-1] == [(13, b"original")]


def test_new_user_copy_is_not_overwritten_by_restore():
    clipboard, sequence, writes = transaction()
    with clipboard.temporary("Hello"):
        sequence[0] = 11
    assert len(writes) == 1


def test_unknown_format_is_rejected_before_emptying_clipboard():
    clipboard, sequence, writes = transaction()
    clipboard._snapshot = lambda: (_ for _ in ()).throw(ClipboardUnavailable())
    with pytest.raises(ClipboardUnavailable), clipboard.temporary("Hello"):
        pytest.fail("must not paste")
    assert writes == []


def test_clipboard_restored_even_if_injection_fails():
    clipboard, sequence, writes = transaction()
    with pytest.raises(RuntimeError), clipboard.temporary("Hello"):
        raise RuntimeError("injection failed")
    assert writes[-1] == [(13, b"original")]
