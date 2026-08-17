from unittest.mock import MagicMock, patch

import pytest

from voice.audio import AudioCapture


def test_start_closes_a_stream_when_startup_fails():
    stream = MagicMock()
    stream.start.side_effect = RuntimeError("microphone unavailable")

    with patch("voice.audio.sd.InputStream", return_value=stream):
        capture = AudioCapture(lambda samples: None)

        with pytest.raises(RuntimeError, match="microphone unavailable"):
            capture.start()

    stream.close.assert_called_once_with()
    assert capture.is_running is False


def test_stop_closes_the_stream_when_stop_raises():
    stream = MagicMock()
    stream.active = True
    stream.stop.side_effect = RuntimeError("stream stop failed")
    capture = AudioCapture(lambda samples: None)
    capture._stream = stream

    with pytest.raises(RuntimeError, match="stream stop failed"):
        capture.stop()

    stream.close.assert_called_once_with()
    assert capture.is_running is False
