from localdictate.instance_guard import SingleInstanceGuard


def test_second_guard_cannot_start_same_service():
    first = SingleInstanceGuard()
    second = SingleInstanceGuard()
    try:
        assert first.acquire()
        assert not second.acquire()
    finally:
        first.close()
        second.close()
