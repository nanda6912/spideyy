from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from voice.speech import SpeechRecognizer, build_wake_grammar
from wake.wake_phrase import WakePhraseDetector


DEFAULT_MODEL_PATH = Path(
    "data/models/vosk-model-small-en-us-0.15"
)


class VoiceWakeService:
    """Connects speech recognition with JARVIS wake-phrase detection."""

    def __init__(
        self,
        *,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        device: int | None = 1,
        on_wake: Callable[[str], None] | None = None,
    ) -> None:
        self._detector = WakePhraseDetector()
        self._on_wake = on_wake

        self._recognizer = SpeechRecognizer(
            model_path,
            device=device,
            on_text=self._process_text,
        )
        self._recognizer.set_grammar(self._wake_grammar())

    @property
    def is_running(self) -> bool:
        return self._recognizer.is_running

    @property
    def is_awake(self) -> bool:
        return self._detector.is_active

    def start(self) -> None:
        self._recognizer.start()

    def stop(self) -> None:
        self._recognizer.stop()
        self._detector.reset()

    def reset(self) -> None:
        self._detector.reset()
        self._recognizer.set_grammar(self._wake_grammar())

    def process_text(self, text: str) -> bool:
        """Process recognized text and return whether it triggered wake."""

        if not text.strip():
            return False

        if self._detector.process(text):
            if self._on_wake is not None:
                self._on_wake(text)

            return True

        return False

    def _process_text(self, text: str) -> None:
        try:
            self.process_text(text)
        except Exception:
            # Recognition callbacks must never terminate
            # the microphone processing path.
            return

    def _wake_grammar(self) -> list[str]:
        return build_wake_grammar(self._detector.WAKE_PHRASE)
