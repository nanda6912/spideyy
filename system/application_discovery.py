"""Bounded Windows application discovery and SQLite-backed registry."""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Iterator


DEFAULT_REGISTRY_PATH = Path("data/applications.db")
_COMMAND_PREFIXES = ("open ", "launch ", "start ", "run ")
_KNOWN_ALIASES: dict[str, frozenset[str]] = {
    "google chrome": frozenset({"chrome"}),
    "visual studio code": frozenset({"vscode", "vs code", "code"}),
    "intellij idea": frozenset({"intellij", "idea"}),
    "eclipse ide": frozenset({"eclipse"}),
    "windows terminal": frozenset({"terminal"}),
}


def normalize_name(value: str) -> str:
    """Return a deterministic, comparison-friendly application name."""
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    for prefix in _COMMAND_PREFIXES:
        if normalized.startswith(prefix):
            return normalized[len(prefix) :].strip()
    return normalized


def _compact(value: str) -> str:
    return value.replace(" ", "")


def aliases_for(name: str) -> tuple[str, ...]:
    """Return stable aliases, including well-known spoken application names."""
    normalized = normalize_name(name)
    aliases = {normalized, *_KNOWN_ALIASES.get(normalized, ())}
    for known_name, known_aliases in _KNOWN_ALIASES.items():
        if _compact(normalized) == _compact(known_name):
            aliases.update(known_aliases)
    words = normalized.split()
    if len(words) > 1:
        aliases.add("".join(word[0] for word in words))
    return tuple(sorted(aliases))


@dataclass(frozen=True, slots=True)
class DiscoveredApplication:
    """A launchable application discovered from a Windows-owned location."""

    name: str
    executable_path: Path
    shortcut_path: Path | None
    publisher: str | None
    source: str
    normalized_name: str
    aliases: tuple[str, ...]

    @classmethod
    def create(
        cls,
        name: str,
        executable_path: Path | str,
        *,
        shortcut_path: Path | str | None = None,
        publisher: str | None = None,
        source: str,
    ) -> DiscoveredApplication:
        """Build an application record with normalized matching fields."""
        cleaned_name = name.strip()
        normalized = normalize_name(cleaned_name)
        return cls(
            name=cleaned_name,
            executable_path=Path(executable_path),
            shortcut_path=Path(shortcut_path) if shortcut_path else None,
            publisher=publisher.strip() if publisher else None,
            source=source,
            normalized_name=normalized,
            aliases=aliases_for(cleaned_name),
        )

    def is_valid(self) -> bool:
        """Return whether this record is safe and useful to register."""
        return bool(
            self.name
            and self.normalized_name
            and self.source
            and self.executable_path.is_file()
            and self.executable_path.suffix.casefold() == ".exe"
        )


class ApplicationRegistry:
    """Persists discovered applications in a small local SQLite database."""

    def __init__(self, database_path: Path | str = DEFAULT_REGISTRY_PATH) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS applications (
                        executable_path TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        shortcut_path TEXT,
                        publisher TEXT,
                        source TEXT NOT NULL,
                        normalized_name TEXT NOT NULL,
                        aliases TEXT NOT NULL
                    )
                    """
                )

    def replace_all(self, applications: Iterable[DiscoveredApplication]) -> None:
        """Replace the registry with validated discovery results."""
        valid = [application for application in applications if application.is_valid()]
        rows = [
            (
                str(application.executable_path),
                application.name,
                str(application.shortcut_path) if application.shortcut_path else None,
                application.publisher,
                application.source,
                application.normalized_name,
                "\x1f".join(application.aliases),
            )
            for application in valid
        ]
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("DELETE FROM applications")
                connection.executemany(
                    """
                    INSERT INTO applications
                    (executable_path, name, shortcut_path, publisher, source, normalized_name, aliases)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def load_all(self) -> list[DiscoveredApplication]:
        """Load all registered applications ordered deterministically by name."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT name, executable_path, shortcut_path, publisher, source, normalized_name, aliases
                FROM applications ORDER BY normalized_name, executable_path
                """
            ).fetchall()
        return [
            DiscoveredApplication(
                name=row[0],
                executable_path=Path(row[1]),
                shortcut_path=Path(row[2]) if row[2] else None,
                publisher=row[3],
                source=row[4],
                normalized_name=row[5],
                aliases=tuple(row[6].split("\x1f")),
            )
            for row in rows
        ]

    def match(self, query: str) -> DiscoveredApplication | None:
        """Find the highest deterministic match for a spoken application query."""
        normalized_query = normalize_name(query)
        if not normalized_query:
            return None

        candidates: list[tuple[int, str, DiscoveredApplication]] = []
        compact_query = _compact(normalized_query)
        for application in self.load_all():
            terms = application.aliases
            if normalized_query in terms or compact_query in {_compact(term) for term in terms}:
                candidates.append((100, application.normalized_name, application))
                continue

            best_ratio = max(
                SequenceMatcher(None, normalized_query, term).ratio() for term in terms
            )
            if best_ratio >= 0.78:
                candidates.append((round(best_ratio * 100), application.normalized_name, application))

        if not candidates:
            return None
        return max(candidates, key=lambda item: (item[0], item[1]))[2]


class ApplicationDiscovery:
    """Discovers applications from bounded Windows sources only."""

    def discover(self) -> list[DiscoveredApplication]:
        """Discover valid applications and remove duplicates by executable path."""
        discovered: dict[Path, DiscoveredApplication] = {}
        for application in self._discover_start_menu():
            discovered.setdefault(application.executable_path, application)
        for application in self._discover_registry():
            discovered.setdefault(application.executable_path, application)
        for application in self._discover_user_programs():
            discovered.setdefault(application.executable_path, application)
        return sorted(discovered.values(), key=lambda item: (item.normalized_name, str(item.executable_path)))

    def discover_and_store(self, registry: ApplicationRegistry) -> list[DiscoveredApplication]:
        """Discover applications and atomically replace the persistent registry."""
        applications = self.discover()
        registry.replace_all(applications)
        return applications

    def _discover_start_menu(self) -> Iterator[DiscoveredApplication]:
        for folder in self._start_menu_folders():
            if not folder.is_dir():
                continue
            for shortcut in folder.rglob("*.lnk"):
                target = self._resolve_shortcut(shortcut)
                if target is not None:
                    yield DiscoveredApplication.create(
                        shortcut.stem, target, shortcut_path=shortcut, source="start_menu"
                    )

    @staticmethod
    def _start_menu_folders() -> tuple[Path, ...]:
        program_data = os.environ.get("PROGRAMDATA")
        app_data = os.environ.get("APPDATA")
        folders = []
        if program_data:
            folders.append(Path(program_data) / "Microsoft/Windows/Start Menu/Programs")
        if app_data:
            folders.append(Path(app_data) / "Microsoft/Windows/Start Menu/Programs")
        return tuple(folders)

    @staticmethod
    def _resolve_shortcut(shortcut: Path) -> Path | None:
        try:
            from win32com.client import Dispatch  # type: ignore[import-not-found]

            target = Dispatch("WScript.Shell").CreateShortcut(str(shortcut)).TargetPath
            path = Path(target)
            return path if path.is_file() and path.suffix.casefold() == ".exe" else None
        except (ImportError, OSError):
            return None

    def _discover_registry(self) -> Iterator[DiscoveredApplication]:
        try:
            import winreg
        except ImportError:
            return

        roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
        access_modes = (winreg.KEY_READ, winreg.KEY_READ | getattr(winreg, "KEY_WOW64_32KEY", 0))
        for root in roots:
            for access in access_modes:
                yield from self._read_app_paths(winreg, root, access)
                yield from self._read_uninstall_entries(winreg, root, access)

    @staticmethod
    def _read_app_paths(winreg: object, root: int, access: int) -> Iterator[DiscoveredApplication]:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        try:
            with winreg.OpenKey(root, key_path, 0, access) as key:
                index = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, index)
                        index += 1
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            executable, _ = winreg.QueryValueEx(subkey, None)
                        path = Path(str(executable).strip('"'))
                        if path.is_file() and path.suffix.casefold() == ".exe":
                            yield DiscoveredApplication.create(
                                path.stem, path, source="registry_app_paths"
                            )
                    except OSError:
                        break
        except OSError:
            return

    @staticmethod
    def _read_uninstall_entries(winreg: object, root: int, access: int) -> Iterator[DiscoveredApplication]:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        try:
            with winreg.OpenKey(root, key_path, 0, access) as key:
                index = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, index)
                        index += 1
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                            icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                            try:
                                publisher, _ = winreg.QueryValueEx(subkey, "Publisher")
                            except OSError:
                                publisher = None
                        path = Path(str(icon).split(",", maxsplit=1)[0].strip('"'))
                        if path.is_file() and path.suffix.casefold() == ".exe":
                            yield DiscoveredApplication.create(
                                str(name), path, publisher=str(publisher) if publisher else None,
                                source="registry_uninstall",
                            )
                    except OSError:
                        break
        except OSError:
            return

    @staticmethod
    def _discover_user_programs() -> Iterator[DiscoveredApplication]:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return
        programs = Path(local_app_data) / "Programs"
        if not programs.is_dir():
            return
        for executable in programs.glob("*/*.exe"):
            yield DiscoveredApplication.create(
                executable.stem, executable, source="local_appdata_programs"
            )
