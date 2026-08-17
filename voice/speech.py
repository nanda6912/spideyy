from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from collections.abc import Iterable, Sequence
from typing import Callable, Literal

import numpy as np
from vosk import KaldiRecognizer, Model

from core.command_registry import get_default_command_registry
from voice.audio import AudioCapture


SpeechEventKind = Literal["audio", "partial", "final"]


COMMAND_PHRASES = tuple(get_default_command_registry().get_static_phrases())


def build_wake_grammar(wake_phrase: str) -> list[str]:
    """Build the deliberately small grammar used while waiting for wake speech."""
    return _normalize_grammar_phrases([wake_phrase])


def build_command_grammar(
    application_names: Iterable[str], monitor_count: int
) -> list[str]:
    """Build exact command phrases for Vosk's constrained command mode.

    Application names are supplied by the registry, including its aliases.  This
    deliberately does not attempt to repair text after recognition.
    """

    if isinstance(monitor_count, bool) or not isinstance(monitor_count, int):
        raise TypeError("monitor_count must be an integer")
    if monitor_count < 0:
        raise ValueError("monitor_count cannot be negative")

    names = _normalize_grammar_phrases(application_names)
    phrases = get_default_command_registry().get_grammar_phrases(
        names, monitor_count
    )
    return _normalize_grammar_phrases(phrases)



def _normalize_grammar_phrases(commands: Iterable[str]) -> list[str]:
    """Validate, normalize, and deterministically deduplicate grammar phrases."""

    if isinstance(commands, (str, bytes)):
        raise TypeError("commands must be an iterable of non-empty strings")

    try:
        values = iter(commands)
    except TypeError as error:
        raise TypeError("commands must be an iterable of non-empty strings") from error

    normalized: set[str] = set()
    for command in values:
        if not isinstance(command, str):
            raise TypeError("each grammar command must be a string")
        phrase = " ".join(command.casefold().split())
        if not phrase:
            raise ValueError("grammar commands cannot be empty")
        normalized.add(phrase)
    return sorted(normalized)


_NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
    5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
    10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
    14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
    18: "eighteen", 19: "nineteen", 20: "twenty",
    30: "thirty", 40: "forty", 50: "fifty", 60: "sixty",
    70: "seventy", 80: "eighty", 90: "ninety",
}


def _number_to_words(number: int) -> str:
    if number < 0 or number >= 100:
        raise ValueError("grammar numbers must be between 0 and 99")
    if number in _NUMBER_WORDS:
        return _NUMBER_WORDS[number]
    tens, units = divmod(number, 10)
    return f"{_NUMBER_WORDS[tens * 10]} {_NUMBER_WORDS[units]}"


def _vosk_phrase(phrase: str) -> str:
    """Use Vosk vocabulary words while retaining canonical command text."""
    return re.sub(
        r"(?<![a-z0-9])(\d+)(?![a-z0-9])",
        lambda match: _number_to_words(int(match.group(1))),
        phrase,
    )


@dataclass(frozen=True, slots=True)
class SpeechDiagnostic:
    """A single diagnostic observation from the speech pipeline."""

    kind: SpeechEventKind
    sample_rate: int
    block_size: int
    device: int | None
    timestamp: float = field(default_factory=time.monotonic)
    elapsed_since_previous_event: float | None = None
    elapsed_since_previous_result: float | None = None
    text: str = ""
    rms: float | None = None
    peak: float | None = None


class SpeechRecognizer:
    """Offline speech recognition using AudioCapture and Vosk."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        sample_rate: int = 16_000,
        block_size: int = 2_048,
        device: int | None = 1,
        on_text: Callable[[str], None] | None = None,
        on_partial_text: Callable[[str], None] | None = None,
        on_diagnostic: Callable[[SpeechDiagnostic], None] | None = None,
    ) -> None:
        self._model_path = Path(model_path)
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._device = device
        self._on_text = on_text
        self._on_partial_text = on_partial_text
        self._on_diagnostic = on_diagnostic
        self._last_diagnostic_time: float | None = None
        self._last_result_time: float | None = None
        self._last_partial_text = ""
        self._grammar: tuple[str, ...] | None = None
        self._vosk_to_canonical: dict[str, str] = {}

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"Vosk model not found: {self._model_path}"
            )

        self._model = Model(str(self._model_path))
        self._recognizer = self._create_recognizer()

        self._lock = Lock()

        self._audio = AudioCapture(
            self._process_audio,
            sample_rate=self._sample_rate,
            block_size=self._block_size,
            channels=1,
            device=device,
        )

    @property
    def is_running(self) -> bool:
        return self._audio.is_running

    def start(self) -> None:
        self._audio.start()

    def stop(self) -> None:
        self._audio.stop()

    def reset(self) -> None:
        """Reset the underlying recognizer so the next utterance starts cleanly."""
        with self._lock:
            self._recognizer = self._create_recognizer()
            self._last_partial_text = ""
            self._last_diagnostic_time = None
            self._last_result_time = None

    @property
    def grammar(self) -> tuple[str, ...] | None:
        """Return the active constrained grammar, or ``None`` in general mode."""
        with self._lock:
            return self._grammar

    def set_grammar(self, commands: Sequence[str]) -> None:
        """Activate exact Vosk phrases for command recognition.

        Passing an empty sequence returns the recognizer to unconstrained,
        general recognition mode.
        """
        normalized = tuple(_normalize_grammar_phrases(commands))
        grammar = normalized or None
        with self._lock:
            if grammar == self._grammar:
                return
            self._grammar = grammar
            self._vosk_to_canonical = (
                {_vosk_phrase(phrase): phrase for phrase in grammar}
                if grammar is not None
                else {}
            )
            self._recognizer = self._create_recognizer()
            self._last_partial_text = ""
            self._last_diagnostic_time = None
            self._last_result_time = None

    def reset_grammar(self) -> None:
        """Return to general recognition and recreate the Vosk recognizer."""
        self.set_grammar(())

    def process_audio(self, samples: np.ndarray) -> str | None:
        """Process one float32 audio block and return final text if available."""

        if samples.size == 0:
            return None

        pcm_samples = np.ascontiguousarray(
            np.clip(samples, -1.0, 1.0), dtype=np.float32
        )
        rms = float(np.sqrt(np.mean(np.square(pcm_samples))))
        peak = float(np.max(np.abs(pcm_samples)))
        pcm = (pcm_samples * 32767).astype(np.int16, copy=False).tobytes()

        self._emit_diagnostic(
            SpeechDiagnostic(
                kind="audio",
                sample_rate=self._sample_rate,
                block_size=self._block_size,
                device=self._device,
                rms=rms,
                peak=peak,
            )
        )

        with self._lock:
            accepted = self._recognizer.AcceptWaveform(pcm)
            if not accepted:
                partial = self._safe_json_result(self._recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                if partial_text:
                    self._emit_partial(partial_text)
                return None

            result = self._safe_json_result(self._recognizer.Result())

        text = self._canonical_grammar_result(result.get("text", "").strip())
        self._emit_final(text)

        if text and self._on_text is not None:
            self._on_text(text)

        return text or None

    def _create_recognizer(self) -> KaldiRecognizer:
        if self._grammar is None:
            return KaldiRecognizer(self._model, self._sample_rate)
        return KaldiRecognizer(
            self._model,
            self._sample_rate,
            json.dumps(list(self._vosk_to_canonical)),
        )

    def _canonical_grammar_result(self, text: str) -> str:
        """Return an exact constrained-grammar result in router-facing form."""
        with self._lock:
            return self._vosk_to_canonical.get(text, text)

    @staticmethod
    def _safe_json_result(raw_result: str) -> dict[str, str]:
        try:
            parsed = json.loads(raw_result)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return {
                key: value
                for key, value in parsed.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        return {}

    def _emit_partial(self, text: str) -> None:
        if text == self._last_partial_text:
            return
        self._last_partial_text = text
        previous_result = self._last_result_time
        self._emit_diagnostic(
            SpeechDiagnostic(
                kind="partial",
                sample_rate=self._sample_rate,
                block_size=self._block_size,
                device=self._device,
                text=text,
                elapsed_since_previous_result=(
                    None
                    if previous_result is None
                    else time.monotonic() - previous_result
                ),
            )
        )
        if self._on_partial_text is not None:
            self._on_partial_text(text)

    def _emit_final(self, text: str) -> None:
        self._last_partial_text = ""
        previous_result = self._last_result_time
        self._last_result_time = time.monotonic()
        self._emit_diagnostic(
            SpeechDiagnostic(
                kind="final",
                sample_rate=self._sample_rate,
                block_size=self._block_size,
                device=self._device,
                text=text,
                elapsed_since_previous_result=(
                    None
                    if previous_result is None
                    else self._last_result_time - previous_result
                ),
            )
        )

    def _emit_diagnostic(self, diagnostic: SpeechDiagnostic) -> None:
        if self._on_diagnostic is None:
            return

        last = self._last_diagnostic_time
        self._last_diagnostic_time = diagnostic.timestamp
        if last is not None:
            diagnostic = SpeechDiagnostic(
                kind=diagnostic.kind,
                sample_rate=diagnostic.sample_rate,
                block_size=diagnostic.block_size,
                device=diagnostic.device,
                timestamp=diagnostic.timestamp,
                elapsed_since_previous_event=diagnostic.timestamp - last,
                elapsed_since_previous_result=diagnostic.elapsed_since_previous_result,
                text=diagnostic.text,
                rms=diagnostic.rms,
                peak=diagnostic.peak,
            )

        self._on_diagnostic(diagnostic)

    def get_partial_text(self) -> str:
        """Return the current partial recognition result."""

        with self._lock:
            result = self._safe_json_result(self._recognizer.PartialResult())

        return result.get("partial", "").strip()

    def _process_audio(self, samples: np.ndarray) -> None:
        try:
            self.process_audio(samples)
        except Exception:
            # AudioCapture must not lose its stream because of
            # an exception in speech processing.
            return
