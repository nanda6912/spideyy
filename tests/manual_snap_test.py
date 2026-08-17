import time

import numpy as np
from wake.snap_detector import SnapDetector


def on_double_snap() -> None:
    print("\n*** DOUBLE SNAP DETECTED ***\n")


def main() -> None:
    detector = SnapDetector(on_double_snap)
    original_process = detector._process_audio

    def debug_process(samples: np.ndarray) -> None:
        peak = float(np.max(np.abs(samples)))
        rms = float(np.sqrt(np.mean(samples ** 2)))
        ratio = peak / max(rms, 1e-6)

        if peak > 0.03:
            print(f"peak={peak:.4f} rms={rms:.4f} ratio={ratio:.2f}")

        original_process(samples)

    detector._audio._callback = debug_process
    print("Snap detector diagnostic")
    print("========================")
    print("Make ONE finger snap.")
    print("Then make TWO snaps about 0.3-0.6 seconds apart.")
    print("Press Ctrl+C to stop.")
    detector.start()
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        detector.stop()


if __name__ == "__main__":
    main()
