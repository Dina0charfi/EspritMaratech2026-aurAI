import os
import subprocess
import wave
from pathlib import Path

import whisper


def _ensure_ffmpeg_path():
    ffmpeg_dir = Path("C:/ffmpeg/bin")
    if ffmpeg_dir.exists():
        os.environ["PATH"] = os.pathsep.join([os.environ.get("PATH", ""), str(ffmpeg_dir)])


_model_cache = {}


def convert_to_wav(input_path, output_path):
    _ensure_ffmpeg_path()
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-acodec",
        "pcm_s16le",
        "-vn",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg failed")


def wav_has_audio(file_path, min_duration_sec=0.2):
    with wave.open(str(file_path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        if frames <= 0 or rate <= 0:
            return False
        duration = frames / float(rate)
        return duration >= min_duration_sec


def transcribe_file(file_path, language="ar", model_name="tiny"):
    _ensure_ffmpeg_path()
    model = _model_cache.get(model_name)
    if model is None:
        model = whisper.load_model(model_name)
        _model_cache[model_name] = model
    result = model.transcribe(file_path, language=language)
    return result.get("text", "").strip()
