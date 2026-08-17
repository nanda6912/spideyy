from unittest.mock import MagicMock, patch

from voice.tts import TextToSpeech


@patch("voice.tts.pyttsx3.init")
def test_speak(mock_init):
    engine = MagicMock()
    mock_init.return_value = engine

    tts = TextToSpeech()

    tts.speak("Hello Buddy.")

    engine.say.assert_called_once_with(
        "Hello Buddy."
    )
    engine.runAndWait.assert_called_once()


@patch("voice.tts.pyttsx3.init")
def test_empty_text_is_ignored(mock_init):
    engine = MagicMock()
    mock_init.return_value = engine

    tts = TextToSpeech()

    tts.speak("")

    engine.say.assert_not_called()
    engine.runAndWait.assert_not_called()


@patch("voice.tts.pyttsx3.init")
def test_stop(mock_init):
    engine = MagicMock()
    mock_init.return_value = engine

    tts = TextToSpeech()

    tts.stop()

    engine.stop.assert_called_once()