from unittest.mock import MagicMock, patch

from core.models import CommandResult
from system.application_discovery import DiscoveredApplication
from voice.interaction import VoiceInteraction


def create_interaction():
    assistant = MagicMock()

    with (
        patch("voice.interaction.SpeechRecognizer") as recognizer_class,
        patch("voice.interaction.TextToSpeech") as tts_class,
    ):
        recognizer_class.return_value = MagicMock()
        tts_class.return_value = MagicMock()

        interaction = VoiceInteraction(
            assistant,
            model_path="data/models/vosk-model-small-en-us-0.15",
            device=None,
        )
        interaction._tts = tts_class.return_value

    return interaction, assistant



def test_non_wake_phrase_is_ignored():
    interaction, assistant = create_interaction()

    interaction._running = True

    interaction._process_text("hello spidey")

    assistant.begin_voice_session.assert_not_called()
    assert interaction.mode == "wake"


def test_wake_phrase_starts_voice_session():
    interaction, assistant = create_interaction()

    interaction._running = True

    interaction._process_text("hello jarvis")

    assistant.begin_voice_session.assert_called_once()
    assert interaction.mode == "command"


def test_interaction_starts_in_wake_only_grammar():
    interaction, _ = create_interaction()

    assert interaction._recognizer.set_grammar.call_args.args[0] == ["hello jarvis"]
    assert "open chrome" not in interaction._recognizer.set_grammar.call_args.args[0]


def test_wake_phrase_triggers_response():
    interaction, assistant = create_interaction()

    interaction._running = True

    interaction._process_text("hello jarvis")

    interaction._tts.speak.assert_called_once_with(
        "Hello Buddy"
    )


def test_wake_phrase_activates_grammar_from_registry_and_monitors():
    interaction, assistant = create_interaction()
    assistant.registry.load_all.return_value = [
        DiscoveredApplication.create(
            "Google Chrome", "C:/Apps/chrome.exe", source="test"
        )
    ]
    assistant.monitor_manager.monitor_count.return_value = 2
    interaction._running = True

    interaction._process_text("hello jarvis")

    grammar = interaction._recognizer.set_grammar.call_args.args[0]
    assert "open chrome" in grammar
    assert "move chrome to monitor 2" in grammar
    assert "move chrome to monitor 3" not in grammar


def test_voice_command_is_sent_to_assistant():
    interaction, assistant = create_interaction()

    interaction._running = True

    assistant.handle_voice_command.return_value = (
        CommandResult.ok("Launching Google Chrome.")
    )

    interaction._mode = "command"

    interaction._process_text("open chrome")

    assistant.handle_voice_command.assert_called_once_with(
        "open chrome"
    )

    assert interaction.mode == "wake"


def test_command_result_is_spoken():
    interaction, assistant = create_interaction()

    interaction._running = True

    assistant.handle_voice_command.return_value = (
        CommandResult.ok("Launching Google Chrome.")
    )

    interaction._mode = "command"

    interaction._process_text("open chrome")

    interaction._tts.speak.assert_called_once_with(
        "Launching Google Chrome."
    )


def test_failed_command_result_is_spoken():
    interaction, assistant = create_interaction()

    interaction._running = True

    assistant.handle_voice_command.return_value = (
        CommandResult.failure(
            "application_not_found",
            "I couldn't find that application.",
        )
    )

    interaction._mode = "command"

    interaction._process_text("open something")

    interaction._tts.speak.assert_called_once_with(
        "I couldn't find that application."
    )


def test_command_returns_to_wake_mode():
    interaction, assistant = create_interaction()

    interaction._running = True

    assistant.handle_voice_command.return_value = (
        CommandResult.ok("Launching Google Chrome.")
    )

    interaction._mode = "command"

    interaction._process_text("open chrome")

    assert interaction.mode == "wake"
    assert interaction._recognizer.set_grammar.call_args.args[0] == ["hello jarvis"]


def test_stop_resets_mode():
    interaction, _ = create_interaction()

    interaction._running = True
    interaction._mode = "command"

    interaction.stop()

    assert interaction.mode == "wake"


def test_system_information_voice_command_is_spoken_and_returns_to_wake():
    interaction, assistant = create_interaction()
    interaction._running = True

    assistant.handle_voice_command.return_value = (
        CommandResult.ok("CPU usage is 18 percent.")
    )

    interaction._mode = "command"
    interaction._process_text("cpu usage")

    assistant.handle_voice_command.assert_called_once_with("cpu usage")
    interaction._tts.speak.assert_called_once_with("CPU usage is 18 percent.")
    assert interaction.mode == "wake"
