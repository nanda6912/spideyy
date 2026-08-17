import time

import numpy as np
import sounddevice as sd


DEVICE = 1
SAMPLE_RATE = 16000
BLOCK_SIZE = 512


def callback(indata, frames, time_info, status):
    if status:
        print(f"Audio status: {status}")

    samples = indata[:, 0]

    rms = float(np.sqrt(np.mean(samples ** 2)))
    peak = float(np.max(np.abs(samples)))

    print(f"RMS: {rms:.4f} | Peak: {peak:.4f}")


def main() -> None:
    print("Starting microphone test...")
    print("Speak normally, then snap near the microphone.")
    print("Press Ctrl+C to stop.")

    with sd.InputStream(
        device=DEVICE,
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=1,
        dtype="float32",
        callback=callback,
    ):
        while True:
            time.sleep(0.1)


if __name__ == "__main__":
    main()
