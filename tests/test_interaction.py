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


def test_system_control_voice_command_is_spoken_and_returns_to_wake():
    interaction, assistant = create_interaction()
    interaction._running = True

    assistant.handle_voice_command.return_value = (
        CommandResult.ok("Volume is at 50 percent.")
    )

    interaction._mode = "command"
    interaction._process_text("set volume to 50")

    assistant.handle_voice_command.assert_called_once_with("set volume to 50")
    interaction._tts.speak.assert_called_once_with("Volume is at 50 percent.")
    assert interaction.mode == "wake"


def test_power_command_voice_confirmation_flow():
    interaction, assistant = create_interaction()
    interaction._running = True

    assistant.handle_voice_command.side_effect = [
        CommandResult.ok(
            "Are you sure you want to shut down the computer?",
            pending_confirmation="shutdown_computer",
            requires_confirmation=True,
        ),
        CommandResult.ok("Shutdown cancelled."),
    ]

    interaction._mode = "command"
    interaction._process_text("shutdown computer")

    assistant.handle_voice_command.assert_called_with("shutdown computer")
    interaction._tts.speak.assert_called_with("Are you sure you want to shut down the computer?")

    interaction._mode = "command"
    interaction._process_text("no")

    assistant.handle_voice_command.assert_called_with("no")
    interaction._tts.speak.assert_called_with("Shutdown cancelled.")
    assert interaction.mode == "wake"


def test_phase5b_context_voice_commands():
    interaction, assistant = create_interaction()
    interaction._running = True

    commands_and_responses = [
        ("what window is active", "The active window is Google Chrome."),
        ("what application is active", "Google Chrome is the active application."),
        ("which monitor is this window on", "The active window is on monitor 1."),
        ("is chrome open", "Yes, Google Chrome is running."),
        ("what applications are open", "Open applications are Google Chrome and Visual Studio Code."),
        ("where is chrome", "Google Chrome is on monitor 1."),
    ]

    for command, response in commands_and_responses:
        assistant.handle_voice_command.return_value = CommandResult.ok(response)
        interaction._mode = "command"
        interaction._process_text(command)

        assistant.handle_voice_command.assert_called_with(command)
        interaction._tts.speak.assert_called_with(response)
        assert interaction.mode == "wake"


def test_phase5c1_focus_voice_command():
    interaction, assistant = create_interaction()
    interaction._running = True

    assistant.handle_voice_command.return_value = CommandResult.ok(
        "Focusing Google Chrome.", application="Google Chrome", hwnd=100
    )

    interaction._mode = "command"
    interaction._process_text("focus chrome")

    assistant.handle_voice_command.assert_called_once_with("focus chrome")
    interaction._tts.speak.assert_called_once_with("Focusing Google Chrome.")
    assert interaction.mode == "wake"


def test_phase5c1_close_application_voice_confirmation_flow():
    interaction, assistant = create_interaction()
    interaction._running = True

    # 1. User says "close chrome" -> assistant prompts for confirmation -> returns to wake
    assistant.handle_voice_command.return_value = CommandResult.ok(
        "Are you sure you want to close the Google Chrome window?",
        pending_confirmation="close_application",
        requires_confirmation=True,
        application="Google Chrome",
        hwnd=100,
    )
    interaction._mode = "command"
    interaction._process_text("close chrome")

    assistant.handle_voice_command.assert_called_with("close chrome")
    interaction._tts.speak.assert_called_with(
        "Are you sure you want to close the Google Chrome window?"
    )
    assert interaction.mode == "wake"

    # 2. User wakes and confirms with "yes" -> window closed -> returns to wake
    assistant.handle_voice_command.return_value = CommandResult.ok(
        "Google Chrome window closed.", application="Google Chrome", hwnd=100
    )
    interaction._mode = "command"
    interaction._process_text("yes")

    assistant.handle_voice_command.assert_called_with("yes")
    interaction._tts.speak.assert_called_with("Google Chrome window closed.")
    assert interaction.mode == "wake"


def test_phase5c1_close_active_window_voice_confirmation_flow():
    interaction, assistant = create_interaction()
    interaction._running = True

    # 1. User says "close this window" -> assistant prompts -> returns to wake
    assistant.handle_voice_command.return_value = CommandResult.ok(
        "Are you sure you want to close the active window?",
        pending_confirmation="close_active_window",
        requires_confirmation=True,
        hwnd=100,
    )
    interaction._mode = "command"
    interaction._process_text("close this window")

    assistant.handle_voice_command.assert_called_with("close this window")
    interaction._tts.speak.assert_called_with(
        "Are you sure you want to close the active window?"
    )
    assert interaction.mode == "wake"

    # 2. User wakes and cancels with "no" -> cancelled -> returns to wake
    assistant.handle_voice_command.return_value = CommandResult.ok(
        "Closing active window cancelled.", cancelled_action="close_active_window"
    )
    interaction._mode = "command"
    interaction._process_text("no")

    assistant.handle_voice_command.assert_called_with("no")
    interaction._tts.speak.assert_called_with("Closing active window cancelled.")
    assert interaction.mode == "wake"



