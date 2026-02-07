import sounddevice as sd
import wavio
import os
os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"

import whisper
import sounddevice as sd
import numpy as np
import wavio

# 1) Enregistrer 5-10 secondes
duration = 10
fs = 44100
channels = 1

print("Parlez maintenant...")
recording = sd.rec(int(duration * fs), samplerate=fs, channels=channels)
sd.wait()
wavio.write("voix.wav", recording, fs, sampwidth=2)
print("Audio sauvegardé : voix.wav")
import whisper

model = whisper.load_model("tiny")  # rapide et léger
result = model.transcribe("voix.wav", language="ar")  # "ar" pour arabe / tunisien
texte = result["text"]

print("Texte reconnu :", texte)
