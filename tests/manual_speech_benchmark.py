"""Manual constrained-recognition benchmark; it never executes desktop commands."""

from __future__ import annotations

import queue
import time
from pathlib import Path

from system.application_discovery import ApplicationRegistry
from system.monitor_manager import MonitorManager
from voice.speech import (
    SpeechRecognizer,
    build_command_grammar,
    build_wake_grammar,
)


MODEL_PATH = Path("data/models/vosk-model-small-en-us-0.15")
PHRASES = (
    "hello jarvis",
    "show monitors",
    "help",
    "status",
    "open chrome",
    "launch chrome",
    "maximize chrome",
    "minimize chrome",
    "restore chrome",
    "move chrome to monitor 2",
)


def classify(expected: str, partials: list[str], final: str) -> str:
    if not final:
        return "CASE C: no usable final result / segmentation issue"
    if expected in partials and final != expected:
        return "CASE A: partial correct, final incorrect"
    if not any(expected.startswith(partial) for partial in partials if partial):
        return "CASE B: partial incorrect from the beginning"
    return "FAIL: final differed from expected"


def command_grammar() -> list[str]:
    registry = ApplicationRegistry()
    names = [alias for app in registry.load_all() for alias in app.aliases]
    # Keep Chrome in this manual benchmark even if it was not discovered, since
    # every benchmark phrase below explicitly evaluates that spoken vocabulary.
    names.append("chrome")
    return build_command_grammar(names, MonitorManager().monitor_count())


def run() -> None:
    finals: queue.Queue[str] = queue.Queue()
    partials: list[str] = []

    def on_partial(text: str) -> None:
        if text and (not partials or partials[-1] != text):
            partials.append(text)

    recognizer = SpeechRecognizer(
        MODEL_PATH, device=1, on_text=finals.put, on_partial_text=on_partial
    )
    recognizer.start()
    try:
        for expected in PHRASES:
            partials.clear()
            while not finals.empty():
                finals.get_nowait()
            if expected == "hello jarvis":
                recognizer.set_grammar(build_wake_grammar("hello jarvis"))
            else:
                recognizer.set_grammar(command_grammar())
            recognizer.reset()
            print(f"\nEXPECTED: {expected}\nSpeak now...")
            try:
                final = finals.get(timeout=10.0)
            except queue.Empty:
                final = ""
            print(f"PARTIAL: {partials[-1] if partials else '(none)'}")
            print(f"FINAL: {final or '(none)'}")
            if final == expected:
                print("PASS")
            else:
                print(f"FAIL\n{classify(expected, partials, final)}")
            time.sleep(0.5)
    finally:
        recognizer.stop()


if __name__ == "__main__":
    run()
