from email.mime import text
from multiprocessing import context
import os
import random
import sys
from pathlib import Path
from PIL import Image

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render, redirect
import torch
from .models import UserProfile
from .utils_sign import get_signs_for_text
from .utils import arabic_to_latin  # si tu as ta fonction de translittération


REPO_ROOT = settings.BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from speech_to_text_vosk_web import convert_to_wav, transcribe_file, wav_has_audio


def home(request):
    return render(request, "home.html")


def transcribe(request):
    context = {"text": "", "error": "", "translit": "", "sign_image": None, "sign_images": []}

    if request.method == "POST":
        # Check if text input was provided
        text_input = request.POST.get("text_input")
        if text_input:
            context["text"] = text_input
            translit_word = arabic_to_latin(text_input)
            context["translit"] = translit_word
            context["sign_images"] = get_signs_for_text(translit_word)
            return render(request, "transcribe.html", context)
        
        audio_file = request.FILES.get("audio")
        if not audio_file:
            context["error"] = "No audio file received."
        elif audio_file.size == 0:
            context["error"] = "Empty audio file."
        else:
            upload_dir = settings.MEDIA_ROOT / "uploads"
            os.makedirs(upload_dir, exist_ok=True)
            storage = FileSystemStorage(location=upload_dir)
            filename = storage.save(audio_file.name, audio_file)
            file_path = storage.path(filename)
            wav_path = None
            try:
                ext = Path(file_path).suffix.lower()
                if ext != ".wav":
                    wav_path = str(Path(file_path).with_suffix(".wav"))
                    convert_to_wav(file_path, wav_path)
                    if not wav_has_audio(wav_path):
                        raise RuntimeError("Audio too short or empty.")
                    text = transcribe_file(wav_path)
                else:
                    if not wav_has_audio(file_path):
                        raise RuntimeError("Audio too short or empty.")
                    text = transcribe_file(file_path)

                context["text"] = text

                # ---- NOUVEAU : translit arabe -> latin ----
                # Après avoir transcrit et translittéré
                translit_word = arabic_to_latin(text)
                sign_image = get_sign_for_word(translit_word)

                context["translit"] = translit_word
                context["sign_images"] = get_signs_for_text(translit_word)
                context["sign_image"] = sign_image



                

            except Exception as exc:
                context["error"] = f"Transcription failed: {exc}"
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
                if wav_path and os.path.exists(wav_path):
                    os.remove(wav_path)

    return render(request, "transcribe.html", context)

def get_sign_for_word(word):
    model_path = settings.BASE_DIR / "sign_model_and_images.pth"
    package = torch.load(model_path, map_location="cpu", weights_only=False)
    images = package["word_to_images"].get(word.lower())
    if images:
        img_array = random.choice(images)
        temp_dir = settings.MEDIA_ROOT / "temp"
        os.makedirs(temp_dir, exist_ok=True)
        img_path = temp_dir / f"{word}.jpg"
        Image.fromarray(img_array).save(img_path)
        return str(img_path)
    return None


def show_avatar(request):
    context = {"sign_image": None, "word": ""}
    if request.method == "POST":
        word_input = request.POST.get("text_input")
        translit_word = arabic_to_latin(word_input)
        sign_image = get_sign_for_word(translit_word)
        context["sign_image"] = sign_image  # URL ou base64
        context["word"] = translit_word
    return render(request, "avatar.html", context)


def signin(request):
    context = {"error": ""}
    if request.method == "POST":
        email_or_username = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=email_or_username, password=password)
        if user is None:
            try:
                user_obj = User.objects.get(email=email_or_username)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            context["error"] = "Invalid credentials."
        else:
            return redirect("/signin/")

    return render(request, "signin.html", context)


def signup(request):
    context = {"error": ""}
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        birth_date = request.POST.get("birth_date", "").strip()
        has_disability = request.POST.get("has_disability") == "yes"
        disability_type = request.POST.get("disability_type", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if password != confirm_password:
            context["error"] = "Passwords do not match."
        elif not full_name or not email or not phone or not birth_date:
            context["error"] = "Please fill in all required fields."
        elif User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            context["error"] = "An account with this email already exists."
        else:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=full_name,
            )
            UserProfile.objects.create(
                user=user,
                phone=phone,
                birth_date=birth_date,
                has_disability=has_disability,
                disability_type=disability_type if has_disability else "",
            )
            login(request, user)
            return render(request, "home.html")

    return render(request, "signup.html", context)
