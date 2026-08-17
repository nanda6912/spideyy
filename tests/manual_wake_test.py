from pathlib import Path
import time

from voice.wake_service import VoiceWakeService


MODEL_PATH = Path(
    "data/models/vosk-model-small-en-us-0.15"
)


def on_wake(text: str) -> None:
    print()
    print("========================")
    print(f"WAKE DETECTED: {text}")
    print("========================")
    print()


def main() -> None:
    print("Loading JARVIS voice wake service...")
    print()
    print('Say: "hello jarvis"')
    print("Press Ctrl+C to stop.")
    print()

    service = VoiceWakeService(
        model_path=MODEL_PATH,
        device=1,
        on_wake=on_wake,
    )

    try:
        service.start()

        print("Listening...")

        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        print()
        print("Stopping...")

    finally:
        service.stop()


if __name__ == "__main__":
    main()
