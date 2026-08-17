from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np

from voice.audio import AudioCapture


class SnapDetector:
    """Detect two short audio transients within a configurable interval."""

    def __init__(
        self,
        on_double_snap: Callable[[], None],
        *,
        threshold: float = 0.12,
        min_interval: float = 0.15,
        max_interval: float = 0.90,
        cooldown: float = 1.0,
    ) -> None:
        self._on_double_snap = on_double_snap

        self.threshold = threshold
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.cooldown = cooldown

        self._first_snap_time: float | None = None
        self._last_detection_time = 0.0

        self._audio = AudioCapture(
            self._process_audio,
            sample_rate=16_000,
            block_size=256,
            channels=1,
            device=1,
        )

    @property
    def is_running(self) -> bool:
        return self._audio.is_running

    def start(self) -> None:
        self._audio.start()

    def stop(self) -> None:
        self._audio.stop()
        self._first_snap_time = None

    def _process_audio(self, samples: np.ndarray) -> None:
        if samples.size == 0:
            return

        now = time.monotonic()

        # Prevent repeated detections immediately after a successful wake.
        if now - self._last_detection_time < self.cooldown:
            return

        absolute = np.abs(samples)

        peak = float(np.max(absolute))
        rms = float(np.sqrt(np.mean(samples ** 2)))

        # Ignore normal background noise.
        if peak < self.threshold:
            return

        # Require the signal to contain a reasonably strong transient.
        transient_ratio = peak / max(rms, 1e-6)

        if transient_ratio < 2.5:
            return

        if self._first_snap_time is None:
            self._first_snap_time = now
            return

        interval = now - self._first_snap_time

        if self.min_interval <= interval <= self.max_interval:
            self._first_snap_time = None
            self._last_detection_time = now
            self._on_double_snap()

        elif interval > self.max_interval:
            # Treat this loud event as the beginning of a new pair.
            self._first_snap_time = now