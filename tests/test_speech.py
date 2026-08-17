from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voice.speech import (
    SpeechDiagnostic,
    SpeechRecognizer,
    build_command_grammar,
    build_wake_grammar,
)


MODEL_PATH = Path("data/models/vosk-model-small-en-us-0.15")


@contextmanager
def patched_speech_dependencies():
    with (
        patch("voice.speech.Model") as model_class,
        patch("voice.speech.KaldiRecognizer") as recognizer_class,
    ):
        model_class.return_value = MagicMock()
        created: list[MagicMock] = []

        def create_recognizer(*args, **kwargs):
            recognizer = MagicMock()
            created.append(recognizer)
            return recognizer

        recognizer_class.side_effect = create_recognizer
        yield created, recognizer_class


@contextmanager
def build_recognizer():
    with patched_speech_dependencies() as (created, recognizer_class):
        on_text = MagicMock()
        on_partial = MagicMock()
        on_diagnostic = MagicMock()
        speech_recognizer = SpeechRecognizer(
            MODEL_PATH,
            device=None,
            on_text=on_text,
            on_partial_text=on_partial,
            on_diagnostic=on_diagnostic,
        )
        first_recognizer = created[0]
        yield (
            speech_recognizer,
            first_recognizer,
            on_text,
            on_partial,
            on_diagnostic,
            created,
            recognizer_class,
        )


def test_model_path_must_exist():
    with patch("voice.speech.Model"):
        with pytest.raises(FileNotFoundError):
            SpeechRecognizer("does-not-exist")


def test_empty_audio_returns_none():
    with build_recognizer() as values:
        recognizer, *_ = values

        result = recognizer.process_audio(np.array([], dtype=np.float32))

    assert result is None


def test_audio_is_converted_to_pcm():
    with build_recognizer() as values:
        recognizer, voicerecognizer, *_ = values

        voicerecognizer.AcceptWaveform.return_value = False
        voicerecognizer.PartialResult.return_value = "{\"partial\": \"\"}"

        samples = np.array([-1.0, -0.5, 0.0, 0.5, 1.0], dtype=np.float32)

        recognizer.process_audio(samples)

    voicerecognizer.AcceptWaveform.assert_called_once()
    pcm = voicerecognizer.AcceptWaveform.call_args.args[0]

    assert isinstance(pcm, bytes)
    assert len(pcm) == len(samples) * 2
    assert pcm[:2] == (-32767).to_bytes(2, byteorder="little", signed=True)
    assert pcm[-2:] == (32767).to_bytes(2, byteorder="little", signed=True)


def test_partial_recognition_is_emitted():
    with build_recognizer() as values:
        recognizer, voicerecognizer, _, on_partial, on_diagnostic, *_ = values

        voicerecognizer.AcceptWaveform.return_value = False
        voicerecognizer.PartialResult.return_value = "{\"partial\": \"open ch\"}"

        result = recognizer.process_audio(np.array([0.1, 0.2], dtype=np.float32))

    assert result is None
    on_partial.assert_called_once_with("open ch")
    diagnostic = on_diagnostic.call_args.args[0]
    assert isinstance(diagnostic, SpeechDiagnostic)
    assert diagnostic.kind == "partial"
    assert diagnostic.text == "open ch"


def test_final_recognition_result_is_emitted():
    with build_recognizer() as values:
        recognizer, voicerecognizer, on_text, _, on_diagnostic, *_ = values

        voicerecognizer.AcceptWaveform.return_value = True
        voicerecognizer.Result.return_value = "{\"text\": \"open chrome\"}"

        result = recognizer.process_audio(np.array([0.1, 0.2], dtype=np.float32))

    assert result == "open chrome"
    on_text.assert_called_once_with("open chrome")
    diagnostic = on_diagnostic.call_args.args[0]
    assert isinstance(diagnostic, SpeechDiagnostic)
    assert diagnostic.kind == "final"
    assert diagnostic.text == "open chrome"


def test_invalid_or_empty_vosk_results_are_ignored():
    with build_recognizer() as values:
        recognizer, voicerecognizer, on_text, on_partial, on_diagnostic, *_ = values

        voicerecognizer.AcceptWaveform.return_value = True
        voicerecognizer.Result.return_value = "{\"text\": \"\"}"

        result = recognizer.process_audio(np.array([0.1, 0.2], dtype=np.float32))

    assert result is None
    on_text.assert_not_called()
    on_partial.assert_not_called()
    diagnostic = on_diagnostic.call_args.args[0]
    assert isinstance(diagnostic, SpeechDiagnostic)
    assert diagnostic.kind == "final"
    assert diagnostic.text == ""


def test_partial_result_falls_back_to_empty_when_invalid_json():
    with build_recognizer() as values:
        recognizer, voicerecognizer, _, on_partial, _, *_ = values

        voicerecognizer.AcceptWaveform.return_value = False
        voicerecognizer.PartialResult.return_value = "not-json"

        result = recognizer.process_audio(np.array([0.1, 0.2], dtype=np.float32))

    assert result is None
    on_partial.assert_not_called()


def test_reset_recreates_underlying_recognizer():
    with build_recognizer() as values:
        recognizer, first_recognizer, on_text, on_partial, on_diagnostic, created, recognizer_class = values

        recognizer.reset()

    assert recognizer_class.call_count == 2
    assert len(created) == 2
    assert recognizer._recognizer is created[1]
    assert recognizer._recognizer is not first_recognizer


def test_command_grammar_contains_aliases_and_existing_monitors_only():
    grammar = build_command_grammar(["Chrome", "Visual Studio Code", "vs code"], 2)

    assert "open chrome" in grammar
    assert "launch visual studio code" in grammar
    assert "maximize vs code" in grammar
    assert "move chrome to monitor 1" in grammar
    assert "move chrome to monitor 2" in grammar
    assert "move chrome to monitor 3" not in grammar
    assert "move chrome to monitor to monitor" not in grammar


def test_wake_grammar_contains_only_the_configured_wake_phrase():
    grammar = build_wake_grammar("Hello Jarvis")

    assert grammar == ["hello jarvis"]
    assert "open chrome" not in grammar


def test_numbered_monitor_grammar_uses_vosk_words_but_emits_canonical_digits():
    with build_recognizer() as values:
        recognizer, _, on_text, _, _, _, recognizer_class = values
        recognizer.set_grammar(["move chrome to monitor 2"])
        recognizer._recognizer.AcceptWaveform.return_value = True
        recognizer._recognizer.Result.return_value = (
            '{"text": "move chrome to monitor two"}'
        )

        result = recognizer.process_audio(np.array([0.1, 0.2], dtype=np.float32))

    assert recognizer_class.call_args.args[2] == '["move chrome to monitor two"]'
    assert result == "move chrome to monitor 2"
    on_text.assert_called_once_with("move chrome to monitor 2")


def test_set_grammar_recreates_recognizer_with_vosk_grammar():
    with build_recognizer() as values:
        recognizer, _, _, _, _, created, recognizer_class = values

        recognizer.set_grammar(["Open Chrome", "show monitors"])

    assert recognizer_class.call_count == 2
    assert recognizer.grammar == ("open chrome", "show monitors")
    assert recognizer_class.call_args.args[2] == '["open chrome", "show monitors"]'
    assert recognizer._recognizer is created[1]


def test_reset_grammar_returns_to_general_recognition():
    with build_recognizer() as values:
        recognizer, _, _, _, _, _, recognizer_class = values

        recognizer.set_grammar(["open chrome"])
        recognizer.reset_grammar()

    assert recognizer.grammar is None
    assert recognizer_class.call_count == 3
    assert len(recognizer_class.call_args.args) == 2


def test_recognizer_can_switch_between_wake_general_and_command_modes():
    with build_recognizer() as values:
        recognizer, _, _, _, _, _, recognizer_class = values

        recognizer.set_grammar(build_wake_grammar("hello jarvis"))
        recognizer.reset_grammar()
        recognizer.set_grammar(["open chrome"])

    assert recognizer.grammar == ("open chrome",)
    assert recognizer_class.call_count == 4


def test_command_results_are_emitted_with_active_grammar():
    with build_recognizer() as values:
        recognizer, _, on_text, _, _, _, _ = values
        recognizer.set_grammar(["open chrome"])
        recognizer._recognizer.AcceptWaveform.return_value = True
        recognizer._recognizer.Result.return_value = '{"text": "open chrome"}'

        result = recognizer.process_audio(np.array([0.1, 0.2], dtype=np.float32))

    assert result == "open chrome"
    on_text.assert_called_once_with("open chrome")


def test_empty_grammar_preserves_general_recognition_mode():
    with build_recognizer() as values:
        recognizer, first_recognizer, *_ = values

        recognizer.set_grammar([])

    assert recognizer.grammar is None
    assert recognizer._recognizer is first_recognizer


@pytest.mark.parametrize("commands", ["open chrome", [""], ["open chrome", 3], None])
def test_invalid_grammar_input_is_rejected(commands):
    with build_recognizer() as values:
        recognizer, *_ = values

        with pytest.raises((TypeError, ValueError)):
            recognizer.set_grammar(commands)  # type: ignore[arg-type]


def test_diagnostic_timing_is_reported():
    with build_recognizer() as values:
        recognizer, voicerecognizer, _, _, on_diagnostic, *_ = values

        voicerecognizer.AcceptWaveform.side_effect = [True, True]
        voicerecognizer.Result.side_effect = [
            "{\"text\": \"hello jarvis\"}",
            "{\"text\": \"open chrome\"}",
        ]

        recognizer.process_audio(np.array([0.1, 0.2], dtype=np.float32))
        recognizer.process_audio(np.array([0.1, 0.2], dtype=np.float32))

    kinds = [call.args[0].kind for call in on_diagnostic.call_args_list]
    assert kinds[-1] == "final"
    final_events = [
        diagnostic
        for diagnostic in (call.args[0] for call in on_diagnostic.call_args_list)
        if diagnostic.kind == "final"
    ]
    assert final_events[0].elapsed_since_previous_result is None
    assert final_events[1].elapsed_since_previous_result is not None
