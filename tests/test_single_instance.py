from system.single_instance import SingleInstanceGuard


class FakeEvent:
    def __init__(self, handle: object) -> None:
        self.handle = handle
        self.names: list[str] = []

    def CreateMutex(self, security, initial_owner, name):
        self.names.append(name)
        return self.handle


class FakeApi:
    def __init__(self, error: int) -> None:
        self.error = error
        self.closed: list[object] = []

    def GetLastError(self) -> int:
        return self.error

    def CloseHandle(self, handle: object) -> None:
        self.closed.append(handle)


class FakeError:
    ERROR_ALREADY_EXISTS = 183


def test_first_instance_acquires_and_releases_mutex():
    handle = object()
    event = FakeEvent(handle)
    api = FakeApi(error=0)
    guard = SingleInstanceGuard(
        win32event_backend=event,
        win32api_backend=api,
        winerror_backend=FakeError,
    )

    assert guard.acquire() is True
    assert guard.is_already_running is False
    assert event.names == [guard.name]
    guard.release()
    assert api.closed == [handle]


def test_duplicate_instance_is_rejected_and_handle_is_closed():
    handle = object()
    api = FakeApi(error=FakeError.ERROR_ALREADY_EXISTS)
    guard = SingleInstanceGuard(
        win32event_backend=FakeEvent(handle),
        win32api_backend=api,
        winerror_backend=FakeError,
    )

    assert guard.acquire() is False
    assert guard.is_already_running is True
    assert api.closed == [handle]
    assert guard.handle is None
