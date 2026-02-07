import json
import os
import subprocess
import wave
from pathlib import Path

from vosk import KaldiRecognizer, Model


def _ensure_ffmpeg_path():
    ffmpeg_dir = Path("C:/ffmpeg/bin")
    if ffmpeg_dir.exists():
        os.environ["PATH"] = os.pathsep.join([os.environ.get("PATH", ""), str(ffmpeg_dir)])


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


def transcribe_file(file_path, model_path=r"C:\vosk-model-ar"):
    if not Path(model_path).exists():
        raise RuntimeError("Vosk model path not found.")

    with wave.open(str(file_path), "rb") as wav_file:
        if wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
            raise RuntimeError("WAV must be mono 16-bit PCM.")

        model = Model(model_path)
        rec = KaldiRecognizer(model, wav_file.getframerate())

        while True:
            data = wav_file.readframes(4000)
            if len(data) == 0:
                break
            rec.AcceptWaveform(data)

        result = json.loads(rec.FinalResult())
        return result.get("text", "").strip()
