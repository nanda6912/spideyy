from __future__ import annotations

from collections.abc import Callable

import numpy as np
import sounddevice as sd


class AudioCapture:
    """Lightweight microphone capture service."""

    def __init__(
        self,
        callback: Callable[[np.ndarray], None],
        *,
        sample_rate: int = 16_000,
        block_size: int = 512,
        channels: int = 1,
        device: int | None = None,
    ) -> None:
        self._callback = callback
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._channels = channels
        self._device = device
        self._stream: sd.InputStream | None = None

    @property
    def is_running(self) -> bool:
        return self._stream is not None and self._stream.active

    def start(self) -> None:
        if self.is_running:
            return

        stream = sd.InputStream(
            samplerate=self._sample_rate,
            blocksize=self._block_size,
            channels=self._channels,
            dtype="float32",
            device=self._device,
            callback=self._audio_callback,
        )
        try:
            stream.start()
        except Exception:
            stream.close()
            raise
        self._stream = stream

    def stop(self) -> None:
        if self._stream is None:
            return

        stream = self._stream
        self._stream = None
        try:
            stream.stop()
        finally:
            stream.close()

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            return

        samples = indata[:, 0].copy()

        try:
            self._callback(samples)
        except Exception:
            # Never allow an application exception to kill
            # the PortAudio callback thread.
            return
