from wake.wake_phrase import WakePhraseDetector


def test_exact_wake_phrase():
    detector = WakePhraseDetector()

    assert detector.process("Hello Jarvis") is True
    assert detector.is_active is True


def test_case_insensitive():
    detector = WakePhraseDetector()

    assert detector.process("Hello Jarvis") is True


def test_unrelated_phrase_does_not_wake():
    detector = WakePhraseDetector()

    assert detector.process("hello spidey") is False
    assert detector.is_active is False


def test_reset():
    detector = WakePhraseDetector()

    detector.process("Hello Jarvis")
    detector.reset()

    assert detector.is_active is False