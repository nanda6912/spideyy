from __future__ import annotations

from threading import Lock

import pyttsx3


class TextToSpeech:
    """Windows text-to-speech service using pyttsx3."""

    def __init__(
        self,
        *,
        rate: int = 175,
        volume: float = 1.0,
        voice_id: str | None = None,
    ) -> None:
        self._engine = pyttsx3.init()
        self._lock = Lock()

        self._engine.setProperty("rate", rate)
        self._engine.setProperty("volume", volume)

        if voice_id is not None:
            self._engine.setProperty("voice", voice_id)

    def speak(self, text: str) -> None:
        """Speak text synchronously."""
        if not text.strip():
            return

        with self._lock:
            self._engine.say(text)
            self._engine.runAndWait()

    def stop(self) -> None:
        """Stop current speech."""
        with self._lock:
            self._engine.stop()