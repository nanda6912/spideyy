import json
import queue
import sys
from pathlib import Path

import sounddevice as sd
from vosk import KaldiRecognizer, Model


MODEL_PATH = Path("data/models/vosk-model-small-en-us-0.15")
DEVICE = 1
SAMPLE_RATE = 16000
BLOCK_SIZE = 4000


def main() -> None:
    audio_queue: queue.Queue[bytes] = queue.Queue()

    def audio_callback(indata, frames, time_info, status) -> None:
        if status:
            print(f"Audio status: {status}", file=sys.stderr)

        audio_queue.put(bytes(indata))

    print("Loading Vosk model...")
    model = Model(str(MODEL_PATH))
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)

    print()
    print("======================================")
    print("       JARVIS SPEECH TEST")
    print("======================================")
    print("Speak normally.")
    print()
    print('Try: "hello jarvis"')
    print()
    print("Press Ctrl+C to stop.")
    print("======================================")
    print()

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        device=DEVICE,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        try:
            while True:
                data = audio_queue.get()

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()

                    if text:
                        print(f"Recognized: {text}")

                else:
                    partial = json.loads(recognizer.PartialResult())
                    text = partial.get("partial", "").strip()

                    if text:
                        print(f"\rListening: {text:<60}", end="")

        except KeyboardInterrupt:
            print("\nStopping speech test...")


if __name__ == "__main__":
    main()
