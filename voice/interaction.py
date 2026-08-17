from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

from core.assistant import JarvisAssistant
from voice.speech import (
    SpeechRecognizer,
    build_command_grammar,
    build_wake_grammar,
)
from voice.tts import TextToSpeech
from wake.wake_phrase import WakePhraseDetector


DEFAULT_MODEL_PATH = Path(
    "data/models/vosk-model-small-en-us-0.15"
)


class VoiceInteraction:
    """Coordinates speech recognition, wake detection, commands, and TTS."""

    def __init__(
        self,
        assistant: JarvisAssistant,
        *,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        device: int | None = 1,
    ) -> None:
        self._assistant = assistant
        self._wake_detector = WakePhraseDetector()

        self._recognizer = SpeechRecognizer(
            model_path,
            device=device,
            on_text=self._on_recognized_text,
        )
        self._recognizer.set_grammar(self._wake_grammar())

        self._tts: TextToSpeech | None = None

        self._text_queue: queue.Queue[str | None] = queue.Queue()

        self._worker: threading.Thread | None = None
        self._running = False

        self._lock = threading.Lock()
        self._mode = "wake"

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    def start(self) -> None:
        if self._running:
            return

        self._running = True

        # Initialize TTS inside the same worker thread that will use it.
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="jarvis-voice-worker",
            daemon=True,
        )

        self._worker.start()

        self._recognizer.start()

        print("[VOICE] Recognition started.")

    def stop(self) -> None:
        if not self._running:
            return

        print("[VOICE] Stopping...")

        self._running = False

        self._recognizer.stop()

        self._text_queue.put(None)

        if (
            self._worker is not None
            and self._worker.is_alive()
            and threading.current_thread() is not self._worker
        ):
            self._worker.join(timeout=3.0)

        self._worker = None

        self._wake_detector.reset()
        self._recognizer.set_grammar(self._wake_grammar())

        with self._lock:
            self._mode = "wake"

        print("[VOICE] Stopped.")

    def _on_recognized_text(self, text: str) -> None:
        """Called by the Vosk/audio thread."""
        if not text.strip():
            return

        if not self._running:
            return

        print(f"[VOICE] Recognized: {text}")

        self._text_queue.put(text)

    def _worker_loop(self) -> None:
        # TTS is created inside this worker thread.
        self._tts = TextToSpeech()

        print("[VOICE] Worker ready.")

        while self._running:
            try:
                text = self._text_queue.get()

                if text is None:
                    break

                self._process_text(text)

            except Exception as exc:
                print(f"[VOICE] Worker error: {exc}")

        self._tts = None

    def _process_text(self, text: str) -> None:
        with self._lock:
            mode = self._mode

        print(f"[VOICE] Mode={mode}, text={text}")

        if mode == "wake":
            self._process_wake_phrase(text)

        elif mode == "command":
            self._process_command(text)

    def _process_wake_phrase(self, text: str) -> None:
        if not self._wake_detector.process(text):
            return

        print("[VOICE] WAKE PHRASE DETECTED.")

        try:
            self._assistant.begin_voice_session()

            self._recognizer.set_grammar(self._command_grammar())

            with self._lock:
                self._mode = "command"

            print("[VOICE] Now listening for command.")

            self._speak("Hello Buddy")

        except Exception as exc:
            print(f"[VOICE] Wake handling error: {exc}")

            self._wake_detector.reset()
            self._recognizer.set_grammar(self._wake_grammar())

            with self._lock:
                self._mode = "wake"

    def _process_command(self, text: str) -> None:
        print(f"[VOICE] Executing command: {text}")

        try:
            result = self._assistant.handle_voice_command(text)

            print(
                f"[VOICE] Command result: "
                f"success={result.success}, "
                f"message={result.message}"
            )

            self._speak(result.message)

        except Exception as exc:
            print(f"[VOICE] Command error: {exc}")

            self._speak(
                "I couldn't process that command."
            )

        finally:
            self._wake_detector.reset()
            self._recognizer.set_grammar(self._wake_grammar())

            with self._lock:
                self._mode = "wake"

            print("[VOICE] Returned to wake mode.")

    def _speak(self, text: str) -> None:
        if not text.strip():
            return

        if self._tts is None:
            print("[VOICE] TTS is not ready.")
            return

        print(f"[VOICE] Speaking: {text}")

        # Stop recognition while JARVIS speaks so that its own voice
        # does not become a new command.
        self._recognizer.stop()

        try:
            self._tts.speak(text)

        except Exception as exc:
            print(f"[VOICE] TTS error: {exc}")

        finally:
            self._recognizer.reset()

            if self._running:
                time.sleep(0.25)

                self._recognizer.start()

                print("[VOICE] Recognition resumed.")

    def _command_grammar(self) -> list[str]:
        """Derive the constrained command vocabulary from current system state."""
        application_names = [
            alias
            for application in self._assistant.registry.load_all()
            for alias in application.aliases
        ]
        monitor_count = self._assistant.monitor_manager.monitor_count()
        if isinstance(monitor_count, bool) or not isinstance(monitor_count, int):
            monitor_count = 0
        return build_command_grammar(application_names, monitor_count)

    def _wake_grammar(self) -> list[str]:
        return build_wake_grammar(self._wake_detector.WAKE_PHRASE)
