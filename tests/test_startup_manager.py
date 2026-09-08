from unittest.mock import patch

from system.startup_manager import DEFAULT_VALUE_NAME, RUN_KEY_PATH, StartupManager


class _Key:
    def __init__(self, store: dict[str, tuple[object, int]]) -> None:
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None


class FakeRegistry:
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, tuple[object, int]] = {}
        self.created: list[tuple[object, str, int, int]] = []
        self.deleted: list[str] = []

    def OpenKey(self, root, path, reserved, access):
        if path != RUN_KEY_PATH or not self.values:
            raise FileNotFoundError(path)
        return _Key(self.values)

    def CreateKeyEx(self, root, path, reserved, access):
        self.created.append((root, path, reserved, access))
        return _Key(self.values)

    def QueryValueEx(self, key, value_name):
        if value_name not in key.store:
            raise FileNotFoundError(value_name)
        return key.store[value_name]

    def SetValueEx(self, key, value_name, reserved, value_type, value) -> None:
        key.store[value_name] = (value, value_type)

    def DeleteValue(self, key, value_name) -> None:
        if value_name not in key.store:
            raise FileNotFoundError(value_name)
        self.deleted.append(value_name)
        del key.store[value_name]


def test_initial_missing_entry_is_disabled():
    assert StartupManager(registry_backend=FakeRegistry()).is_enabled() is False


def test_enable_writes_quoted_command_and_marks_startup_enabled():
    backend = FakeRegistry()
    manager = StartupManager(registry_backend=backend)
    command = '"C:/Program Files/Python/python.exe" "C:/SPIDEYY/app/main.py"'

    assert manager.enable(command) is True
    assert backend.values[DEFAULT_VALUE_NAME] == (command, backend.REG_SZ)
    assert manager.is_enabled() is True


def test_disable_removes_existing_entry_and_missing_entry_is_safe():
    backend = FakeRegistry()
    backend.values[DEFAULT_VALUE_NAME] = ("command", backend.REG_SZ)
    manager = StartupManager(registry_backend=backend)

    assert manager.disable() is True
    assert DEFAULT_VALUE_NAME in backend.deleted
    assert manager.is_enabled() is False
    assert manager.disable() is False


def test_missing_or_malformed_registry_values_are_disabled():
    backend = FakeRegistry()
    manager = StartupManager(registry_backend=backend)

    backend.values[DEFAULT_VALUE_NAME] = ("", backend.REG_SZ)
    assert manager.is_enabled() is False
    backend.values[DEFAULT_VALUE_NAME] = (object(), backend.REG_SZ)
    assert manager.is_enabled() is False
    backend.values[DEFAULT_VALUE_NAME] = ("command", 999)
    assert manager.is_enabled() is False


def test_default_command_uses_quoted_python_and_main_script():
    manager = StartupManager(registry_backend=FakeRegistry())

    with patch("system.startup_manager.sys.executable", "C:/Program Files/Python/python.exe"):
        command = manager.get_startup_command()

    assert command.startswith('"')
    assert 'python.exe" "' in command
    assert command.endswith('app\\main.py"') or command.endswith('app/main.py"')
