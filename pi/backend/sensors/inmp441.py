"""INMP441 MEMS microphone reader via I2S (v3 -- sensor fusion).

Reads audio data from the AITRIP INMP441 omnidirectional microphone
via the I2S (Inter-IC Sound) interface on the Pi's GPIO.

Wiring (Pi 4B GPIO header):
  VDD  -> Pin 1 (3.3V)
  GND  -> Pin 6 (GND)
  SCK  -> Pin 12 (GPIO 18, I2S BCLK)
  WS   -> Pin 35 (GPIO 19, I2S LRCLK/Word Select)
  SD   -> Pin 38 (GPIO 20, I2S DIN)
  L/R  -> GND (left channel) or VDD (right channel)

What this enables (v3):
  - Engine sound pattern analysis (knock detection, exhaust tone changes)
  - Anomaly detection via audio spectrogram (belt squeal, bearing whine)
  - Road noise classification (highway vs city vs rough road)
  - Complements OBD RPM/load with acoustic signature data

INMP441 datasheet: TDK InvenSense INMP441
Audio processing: librosa 0.11.0 for spectral analysis
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# I2S GPIO pins (BCM numbering)
I2S_BCLK_PIN = 18   # Bit clock
I2S_LRCLK_PIN = 19  # Word select (left/right)
I2S_DIN_PIN = 20     # Data input

# Audio config
SAMPLE_RATE = 16000   # 16kHz is sufficient for engine sounds (up to 8kHz Nyquist)
CHUNK_SIZE = 1024     # Samples per read
BIT_DEPTH = 24        # INMP441 outputs 24-bit data in 32-bit frames


@dataclass
class AudioReading:
    """Audio snapshot for analysis."""
    timestamp: float = field(default_factory=time.time)
    rms_db: float | None = None          # RMS volume level (dBFS)
    peak_freq_hz: float | None = None    # Dominant frequency
    spectral_centroid_hz: float | None = None  # "Brightness" of sound
    is_recording: bool = False


class INMP441Reader:
    """Reads INMP441 microphone via I2S.

    Uses the ALSA/sounddevice interface for audio capture. Requires
    I2S overlay to be enabled in /boot/firmware/config.txt:
      dtoverlay=i2s-mems-mic

    NOT wired into the producer loop yet -- this is a v3 placeholder.
    Audio analysis will use librosa for spectral features.
    """

    def __init__(self) -> None:
        self._stream = None
        self._available = False

    async def start(self) -> None:
        """Initialize I2S audio capture.

        TODO (v3): Enable I2S overlay, open sounddevice InputStream,
        verify audio is being received (non-zero RMS).
        """
        try:
            # v3: import sounddevice, open stream
            # import sounddevice as sd
            # self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, ...)
            logger.info("INMP441 reader initialized (I2S GPIO %d/%d/%d)",
                        I2S_BCLK_PIN, I2S_LRCLK_PIN, I2S_DIN_PIN)
        except Exception as exc:
            logger.info("INMP441 not available: %s (expected on Mac dev)", exc)

    async def stop(self) -> None:
        if self._stream is not None:
            # v3: close the audio stream
            self._stream = None

    def read_snapshot(self) -> AudioReading:
        """Capture and analyze a short audio segment.

        TODO (v3): Read CHUNK_SIZE samples from I2S stream,
        compute RMS (volume), peak frequency (FFT), and spectral
        centroid (librosa.feature.spectral_centroid).
        """
        if not self._available:
            return AudioReading()
        return AudioReading()


class SimulatedINMP441Reader:
    """Mock INMP441 for desktop development."""

    async def start(self) -> None:
        logger.info("SimulatedINMP441Reader started (audio simulation)")

    async def stop(self) -> None:
        pass

    def read_snapshot(self) -> AudioReading:
        return AudioReading(
            rms_db=-35.0,                    # Normal cabin noise level
            peak_freq_hz=120.0,              # Engine idle fundamental (~120Hz at 700 RPM)
            spectral_centroid_hz=800.0,      # Typical for engine + road noise mix
            is_recording=True,
        )
