from localdictate.instance_guard import SingleInstanceGuard


def test_second_guard_cannot_start_same_service(monkeypatch):
    import uuid
    namespace = uuid.uuid4().hex
    monkeypatch.setattr(SingleInstanceGuard, "_MUTEX_NAME", f"Local\\ParrotFlow-Test-{namespace}")
    monkeypatch.setattr(SingleInstanceGuard, "_SHOW_EVENT_NAME", f"Local\\ParrotFlow-Test-Show-{namespace}")
    first = SingleInstanceGuard()
    second = SingleInstanceGuard()
    try:
        assert first.acquire()
        assert not second.acquire()
        assert first.wait_for_show(100)
        assert not first.wait_for_show(1)
    finally:
        first.close()
        second.close()
