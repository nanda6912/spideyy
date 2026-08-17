from core.assistant import JarvisAssistant
from voice.interaction import VoiceInteraction


def main() -> None:
    print()
    print("=" * 50)
    print("SPIDEYY VOICE INTERACTION TEST")
    print("=" * 50)
    print()
    print('Say: "Hello Jarvis"')
    print('Then say: "open chrome"')
    print()
    print("Press Ctrl+C to stop.")
    print()

    assistant = JarvisAssistant()

    print("Starting application registry...")
    startup = assistant.startup()
    print(f"Startup: {startup.message}")

    interaction = VoiceInteraction(
        assistant,
        model_path="data/models/vosk-model-small-en-us-0.15",
        device=1,
    )

    try:
        interaction.start()

        print()
        print("SPIDEYY is listening...")
        print()

        while True:
            # Keep the main process alive.
            import time
            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("Stopping SPIDEYY...")

    finally:
        interaction.stop()

        print("Voice service stopped.")
        print()


if __name__ == "__main__":
    main()