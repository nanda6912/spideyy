from pathlib import Path
from unittest.mock import MagicMock, patch

from voice.wake_service import VoiceWakeService


MODEL_PATH = Path(
    "data/models/vosk-model-small-en-us-0.15"
)


def create_service(on_wake=None):
    with patch("voice.wake_service.SpeechRecognizer") as recognizer_class:
        recognizer = MagicMock()
        recognizer.is_running = False

        recognizer_class.return_value = recognizer

        service = VoiceWakeService(
            model_path=MODEL_PATH,
            device=None,
            on_wake=on_wake,
        )

    return service


def test_non_wake_text_does_not_trigger():
    callback = MagicMock()

    service = create_service(callback)

    result = service.process_text("hello spidey")

    assert result is False
    assert service.is_awake is False
    callback.assert_not_called()


def test_service_uses_a_wake_only_grammar():
    service = create_service()

    assert service._recognizer.set_grammar.call_args.args[0] == ["hello jarvis"]
    assert "open chrome" not in service._recognizer.set_grammar.call_args.args[0]


def test_wake_phrase_triggers_callback():
    callback = MagicMock()

    service = create_service(callback)

    result = service.process_text("Hello Jarvis")

    assert result is True
    assert service.is_awake is True

    callback.assert_called_once_with("Hello Jarvis")


def test_wake_phrase_is_case_insensitive():
    callback = MagicMock()

    service = create_service(callback)

    result = service.process_text("Hello Jarvis")

    assert result is True
    callback.assert_called_once_with("Hello Jarvis")


def test_reset_returns_to_standby():
    service = create_service()

    service.process_text("Hello Jarvis")

    assert service.is_awake is True

    service.reset()

    assert service.is_awake is False


def test_stop_resets_wake_state():
    service = create_service()

    service.process_text("Hello Jarvis")

    service.stop()

    assert service.is_awake is False


def test_start_delegates_to_speech_recognizer():
    service = create_service()

    service.start()

    service._recognizer.start.assert_called_once()


def test_stop_delegates_to_speech_recognizer():
    service = create_service()

    service.stop()

    service._recognizer.stop.assert_called_once()
