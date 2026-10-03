"""Kokoro-onnx narration synth, cached to WAV files by text+voice+speed.

python video/voice.py "some text"   # synth one line, print path + duration
"""

import hashlib
from pathlib import Path
import sys
from urllib.request import urlretrieve

import soundfile as sf

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / ".cache" / "kokoro"
VOICE_DIR = ROOT / ".cache" / "voice"
MODEL_BASE_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)
VOICE = "am_michael"
SPEED = 1.08
LANG = "en-us"

_kokoro = None


def _ensure_model_files():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        path = MODEL_DIR / name
        if not path.exists():
            urlretrieve(f"{MODEL_BASE_URL}/{name}", path)
        paths[name] = path
    return paths["kokoro-v1.0.onnx"], paths["voices-v1.0.bin"]


def _model():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro

        model_path, voices_path = _ensure_model_files()
        _kokoro = Kokoro(str(model_path), str(voices_path))
    return _kokoro


def synth(text):
    """Return (wav_path, duration_seconds) for narrating `text`, caching by content."""
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{VOICE}:{SPEED}:{text}".encode()).hexdigest()
    wav_path = VOICE_DIR / f"{key}.wav"
    if wav_path.exists():
        info = sf.info(str(wav_path))
        return wav_path, info.frames / info.samplerate
    samples, sample_rate = _model().create(text, voice=VOICE, speed=SPEED, lang=LANG)
    sf.write(str(wav_path), samples, sample_rate)
    return wav_path, len(samples) / sample_rate


def demo():
    # ponytail: smallest live check -- duration and loudness are plausible, not a listen-check
    path, duration = synth("This is a short test of the narration voice.")
    words = 8
    assert 2.0 <= words / duration <= 3.5, f"implausible pace: {duration:.2f}s for {words} words"
    import numpy as np

    samples, _ = sf.read(str(path))
    rms = float(np.sqrt(np.mean(samples.astype("float64") ** 2)))
    assert rms > 0, "synthesized audio is silent"
    print(f"demo ok: {path} {duration:.2f}s rms={rms:.4f}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        path, duration = synth(text)
        print(f"{path} {duration:.2f}s")
    else:
        demo()
