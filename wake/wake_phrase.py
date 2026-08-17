from __future__ import annotations

import re


class WakePhraseDetector:
    """Detects the JARVIS wake phrase from recognized speech."""

    WAKE_PHRASE = "hello jarvis"

    def __init__(self) -> None:
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def process(self, text: str) -> bool:
        normalized = self._normalize(text)

        if self.WAKE_PHRASE in normalized:
            self._active = True
            return True

        return False

    def reset(self) -> None:
        self._active = False

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)

        return text