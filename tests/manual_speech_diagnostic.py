from __future__ import annotations

import argparse
import queue
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import sounddevice as sd

from voice.speech import SpeechDiagnostic, SpeechRecognizer


MODEL_PATH = Path("data/models/vosk-model-small-en-us-0.15")
DEFAULT_DEVICE = 1
DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_BLOCK_SIZE = 2_048
BLOCK_SIZE_CHOICES = (1_024, 2_048, 4_000)
RECOGNITION_PHRASES = (
    "hello jarvis",
    "show monitors",
    "help",
    "status",
    "open chrome",
    "launch chrome",
    "move chrome to monitor 2",
    "maximize chrome",
    "minimize chrome",
    "restore chrome",
)
KEY_PHRASES = ("hello jarvis", "show monitors", "help", "open chrome")


def parse_device(value: str) -> int | None:
    normalized = value.strip().lower()
    if normalized in {"default", "auto", "none"}:
        return None
    return int(value)


def list_input_devices() -> list[dict[str, object]]:
    devices: list[dict[str, object]] = []
    for index, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels", 0)) <= 0:
            continue
        devices.append({"index": index, **device})
    return devices


def describe_device(device_index: int | None) -> dict[str, object]:
    if device_index is None:
        default_input = sd.default.device[0]
        device_index = None if default_input is None else int(default_input)

    if device_index is None:
        return {
            "index": None,
            "name": "Default input device",
            "max_input_channels": 0,
            "default_samplerate": DEFAULT_SAMPLE_RATE,
            "supported": False,
            "native_rate": None,
        }

    info = sd.query_devices(device_index, "input")
    supported = True
    try:
        sd.check_input_settings(
            device=device_index,
            channels=1,
            samplerate=DEFAULT_SAMPLE_RATE,
            dtype="float32",
        )
    except Exception:
        supported = False

    native_rate = float(info.get("default_samplerate", DEFAULT_SAMPLE_RATE))
    return {
        "index": device_index,
        "name": str(info.get("name", f"Device {device_index}")),
        "max_input_channels": int(info.get("max_input_channels", 0)),
        "default_samplerate": native_rate,
        "supported": supported,
        "native_rate": native_rate,
    }


def classify_level(rms: float | None, peak: float | None) -> str:
    rms = 0.0 if rms is None else rms
    peak = 0.0 if peak is None else peak

    if peak >= 0.98:
        return "CLIPPING"
    if peak < 0.001 and rms < 0.0005:
        return "SILENCE"
    if peak < 0.02 and rms < 0.006:
        return "LOW INPUT"
    return "SPEECH"


def classify_failure(expected: str, partials: list[str], final_text: str) -> str:
    expected_norm = expected.casefold().strip()
    final_norm = final_text.casefold().strip()
    partial_norms = [text.casefold().strip() for text in partials]

    if expected_norm in partial_norms and final_norm != expected_norm:
        return "CASE A: finalization/model behavior"

    if final_norm and any(final_norm.startswith(partial) for partial in partial_norms if partial):
        if final_norm != expected_norm:
            return "CASE B: recognition itself is incorrect"

    if any(expected_norm.startswith(partial) for partial in partial_norms if partial) and final_norm != expected_norm:
        return "CASE C: segmentation/finalization timing"

    if not partial_norms and final_norm != expected_norm:
        return "CASE B: recognition itself is incorrect"

    return "UNCLASSIFIED FAILURE"


@dataclass
class AttemptResult:
    expected: str
    final_text: str
    partials: list[str] = field(default_factory=list)
    latency_seconds: float | None = None
    level_notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.final_text.casefold().strip() == self.expected.casefold().strip()


class DiagnosticSession:
    def __init__(self, *, device: int | None, sample_rate: int, block_size: int) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.block_size = block_size
        self._finals: queue.Queue[tuple[str, float]] = queue.Queue()
        self._partials: list[str] = []
        self._last_audio_print = 0.0
        self._last_final_text = ""
        self._latest_audio_level: str | None = None

    def make_recognizer(self) -> SpeechRecognizer:
        return SpeechRecognizer(
            MODEL_PATH,
            sample_rate=self.sample_rate,
            block_size=self.block_size,
            device=self.device,
            on_text=self._on_final_text,
            on_partial_text=self._on_partial_text,
            on_diagnostic=self._on_diagnostic,
        )

    def clear_attempt(self) -> None:
        self._partials.clear()
        self._latest_audio_level = None
        while not self._finals.empty():
            try:
                self._finals.get_nowait()
            except queue.Empty:
                break

    def wait_for_final(self, timeout: float) -> tuple[str, float] | None:
        try:
            return self._finals.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def partials(self) -> list[str]:
        return list(self._partials)

    @property
    def latest_audio_level(self) -> str | None:
        return self._latest_audio_level

    def _on_partial_text(self, text: str) -> None:
        if not text.strip():
            return
        if self._partials and self._partials[-1] == text:
            return
        self._partials.append(text)
        print(f"PARTIAL: {text}")

    def _on_final_text(self, text: str) -> None:
        self._last_final_text = text
        self._finals.put((text, time.monotonic()))
        if text.strip():
            print(f"FINAL: {text}")
        else:
            print("FINAL: (empty)")

    def _on_diagnostic(self, diagnostic: SpeechDiagnostic) -> None:
        if diagnostic.kind != "audio":
            return

        now = diagnostic.timestamp
        if now - self._last_audio_print < 0.5:
            return
        self._last_audio_print = now

        rms = 0.0 if diagnostic.rms is None else diagnostic.rms
        peak = 0.0 if diagnostic.peak is None else diagnostic.peak
        level = classify_level(diagnostic.rms, diagnostic.peak)
        self._latest_audio_level = level

        print(
            f"AUDIO: rms={rms:.4f} peak={peak:.4f} level={level} "
            f"(elapsed={_format_seconds(diagnostic.elapsed_since_previous_event)})"
        )


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}s"


def print_device_inventory(selected_device: int | None, sample_rate: int) -> None:
    print()
    print("Available input devices:")
    print()
    for device in list_input_devices():
        index = int(device["index"])
        name = str(device["name"])
        channels = int(device["max_input_channels"])
        native_rate = float(device.get("default_samplerate", 0.0))
        marker = " <selected>" if selected_device == index else ""
        print(
            f"[{index}] {name} | max_input_channels={channels} "
            f"| default_sample_rate={native_rate:g}{marker}"
        )

    selected = describe_device(selected_device)
    print()
    if selected["index"] is None:
        print("Selected device: default")
    else:
        print(f"Selected device: {selected['index']}")
    print(f"Selected name: {selected['name']}")
    print(f"Selected max input channels: {selected['max_input_channels']}")
    print(f"Selected native sample rate: {selected['native_rate']}")
    print(f"Requested sample rate: {sample_rate}")
    print(f"Exact-rate stream supported: {selected['supported']}")
    print()
    print(
        "Interpretation: if the selected device's default rate differs from the "
        "requested rate, PortAudio may be resampling. This script reports what "
        "the device advertises and whether a 16 kHz mono float32 input stream "
        "can be opened successfully."
    )


def print_audio_level_guide() -> None:
    print()
    print("Audio level guide:")
    print("  SILENCE   -> peak < 0.001 and RMS < 0.0005")
    print("  LOW INPUT -> peak < 0.02 and RMS < 0.006")
    print("  SPEECH    -> above LOW INPUT thresholds")
    print("  CLIPPING  -> peak >= 0.98")


def run_live_diagnostic(device: int | None, sample_rate: int, block_size: int) -> None:
    print()
    print("=" * 60)
    print("SPIDEYY SPEECH DIAGNOSTIC")
    print("=" * 60)
    print(f"Model: {MODEL_PATH}")
    print(f"Sample rate: {sample_rate}")
    print(f"Channels: 1")
    print(f"Block size: {block_size}")
    print_audio_level_guide()
    print_device_inventory(device, sample_rate)
    print()
    print("Speak naturally.")
    print('Try: "hello jarvis", "show monitors", "help", "open chrome"')
    print("Press Ctrl+C to stop.")

    session = DiagnosticSession(device=device, sample_rate=sample_rate, block_size=block_size)
    recognizer = session.make_recognizer()

    try:
        recognizer.start()
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print()
        print("Stopping diagnostic...")
    finally:
        recognizer.stop()
        print("Diagnostic stopped.")


def run_benchmark(
    *,
    device: int | None,
    sample_rate: int,
    block_size: int,
    phrases: Iterable[str],
    attempts: int,
    timeout_seconds: float,
) -> list[AttemptResult]:
    print()
    print("=" * 60)
    print(f"SPIDEYY RECOGNITION BENCHMARK - BLOCK SIZE {block_size}")
    print("=" * 60)
    print(f"Model: {MODEL_PATH}")
    print(f"Sample rate: {sample_rate}")
    print(f"Channels: 1")
    print(f"Block size: {block_size}")
    print_device_inventory(device, sample_rate)
    print()
    print("Speak exactly the requested phrase for each attempt.")
    print("Stop with Ctrl+C if needed.")
    print()

    session = DiagnosticSession(device=device, sample_rate=sample_rate, block_size=block_size)
    recognizer = session.make_recognizer()
    results: list[AttemptResult] = []

    try:
        recognizer.start()
        for phrase in phrases:
            for attempt in range(1, attempts + 1):
                print()
                print(f"EXPECTED:")
                print(phrase)
                print(f"ATTEMPT {attempt}/{attempts}")
                print("Speak now...")
                session.clear_attempt()
                start = time.monotonic()
                observed = session.wait_for_final(timeout_seconds)
                if observed is None:
                    result = AttemptResult(
                        expected=phrase,
                        final_text="",
                        partials=session.partials,
                        latency_seconds=None,
                        level_notes=[session.latest_audio_level or "UNKNOWN"],
                    )
                    print("FINAL: (timeout)")
                    print("RESULT: FAIL")
                    print("NOTE: no final recognition was produced before timeout")
                    results.append(result)
                    continue

                final_text, final_time = observed
                latency = final_time - start
                result = AttemptResult(
                    expected=phrase,
                    final_text=final_text,
                    partials=session.partials,
                    latency_seconds=latency,
                    level_notes=[session.latest_audio_level or "UNKNOWN"],
                )

                print("PARTIAL:")
                if session.partials:
                    for partial in session.partials:
                        print(partial)
                else:
                    print("(none)")

                print("FINAL:")
                print(final_text or "(empty)")
                print("RESULT: PASS" if result.success else "RESULT: FAIL")
                print(f"LATENCY: {latency:.3f}s")
                if not result.success:
                    print(
                        "CLASSIFICATION: "
                        + classify_failure(phrase, session.partials, final_text)
                    )

                results.append(result)
    except KeyboardInterrupt:
        print()
        print("Benchmark interrupted.")
    finally:
        recognizer.stop()

    print()
    print("Benchmark summary:")
    for phrase in phrases:
        phrase_results = [result for result in results if result.expected == phrase]
        if not phrase_results:
            continue
        correct = sum(1 for result in phrase_results if result.success)
        total = len(phrase_results)
        accuracy = (correct / total) * 100 if total else 0.0
        average_latency = (
            sum(result.latency_seconds for result in phrase_results if result.latency_seconds is not None)
            / max(1, sum(1 for result in phrase_results if result.latency_seconds is not None))
        )
        print(
            f"{phrase} | attempts={total} | correct={correct} | "
            f"accuracy={accuracy:.1f}% | avg_latency={average_latency:.3f}s"
        )

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SPIDEYY speech calibration and recognition diagnostic."
    )
    parser.add_argument(
        "--device",
        type=parse_device,
        default=DEFAULT_DEVICE,
        help="Input device id, or 'default' to use the system default input device.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
        help="Requested recognition sample rate.",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=DEFAULT_BLOCK_SIZE,
        choices=BLOCK_SIZE_CHOICES,
        help="Recognition block size.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run the recognition benchmark instead of the live diagnostic.",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=5,
        help="Benchmark attempts per phrase.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for each recognition final result in benchmark mode.",
    )
    parser.add_argument(
        "--compare-block-sizes",
        action="store_true",
        help="Run the benchmark across block sizes 1024, 2048, and 4000.",
    )
    parser.add_argument(
        "--phrases",
        nargs="*",
        default=list(RECOGNITION_PHRASES),
        help="Benchmark phrases to read in order.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.compare_block_sizes:
        for block_size in BLOCK_SIZE_CHOICES:
            run_benchmark(
                device=args.device,
                sample_rate=args.sample_rate,
                block_size=block_size,
                phrases=args.phrases,
                attempts=args.attempts,
                timeout_seconds=args.timeout,
            )
        return

    if args.benchmark:
        run_benchmark(
            device=args.device,
            sample_rate=args.sample_rate,
            block_size=args.block_size,
            phrases=args.phrases,
            attempts=args.attempts,
            timeout_seconds=args.timeout,
        )
        return

    run_live_diagnostic(
        device=args.device,
        sample_rate=args.sample_rate,
        block_size=args.block_size,
    )


if __name__ == "__main__":
    main()
