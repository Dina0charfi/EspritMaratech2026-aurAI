import sounddevice as sd
import queue
import json
import sys

import numpy as np
from vosk import Model, KaldiRecognizer
sys.stdout.reconfigure(encoding='utf-8')

# تحميل الموديل
model = Model(r"C:\vosk-model-ar")

# ضبط الصوت (يمكن تعديلها حسب الميكروفون)
INPUT_DEVICE = None  # مثال: 1 لو تحب تحدد ميكروفون معين
SAMPLE_RATE = 16000
BLOCK_SIZE = 4000
GAIN = 1.5
NOISE_GATE = 300  # كل ما زاد، يقل الضجيج لكن ممكن يقطع الكلام

q = queue.Queue()

def _process_audio(indata: bytes) -> bytes:
    audio = np.frombuffer(indata, dtype=np.int16).astype(np.float32)

    # تضخيم بسيط لتوضيح الصوت
    if GAIN != 1.0:
        audio *= GAIN

    # بوابة ضجيج بسيطة
    if NOISE_GATE > 0:
        audio[np.abs(audio) < NOISE_GATE] = 0

    audio = np.clip(audio, -32768, 32767).astype(np.int16)
    return audio.tobytes()


def callback(indata, frames, time, status):
    if status:
        print(status)
    q.put(_process_audio(bytes(indata)))

print(" تكلّم توّا... (Ctrl+C للإيقاف)")

with sd.RawInputStream(
    samplerate=SAMPLE_RATE,
    blocksize=BLOCK_SIZE,
    dtype='int16',
    channels=1,
    device=INPUT_DEVICE,
    callback=callback
):
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            print("📝:", result.get("text", ""))
