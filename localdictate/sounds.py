"""Quiet local earcons. Playback never blocks dictation or requires audio files."""
from io import BytesIO
import logging
import math
import struct
from threading import Lock, Thread
import wave
import winsound

_playing = Lock()


def _tone(kind: str) -> bytes:
    frequencies = (523.25, 659.25) if kind == "ready" else (659.25, 880.0)
    rate, duration = 22050, 0.09
    count = int(rate * duration)
    samples = bytearray()
    for frequency in frequencies:
        for i in range(count):
            # Smooth attack/release avoids clicks; peak is 6% of full scale.
            envelope = math.sin(math.pi * i / (count - 1)) ** 2
            value = int(1966 * envelope * math.sin(2 * math.pi * frequency * i / rate))
            samples.extend(struct.pack('<h', value))
    stream = BytesIO()
    with wave.open(stream, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples)
    return stream.getvalue()


def play_cue(kind: str) -> None:
    def play():
        if not _playing.acquire(blocking=False):
            return
        try:
            winsound.PlaySound(_tone(kind), winsound.SND_MEMORY | winsound.SND_NODEFAULT)
        except Exception:
            logging.getLogger('localdictate').debug('Sound cue unavailable', exc_info=True)
        finally:
            _playing.release()
    Thread(target=play, name='parrot-flow-sound', daemon=True).start()
