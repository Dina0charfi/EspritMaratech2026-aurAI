from email.mime import text
from multiprocessing import context
import os
import random
import sys
from pathlib import Path
from PIL import Image

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.contrib import messages
import torch
from .models import Event, UserProfile, Reclamation, WebAuthnCredential
from .utils_sign import get_signs_for_text
from .utils import arabic_to_latin  # si tu as ta fonction de translittération
from .utils_face import compare_face_to_reference, get_enrollment_image_path


REPO_ROOT = settings.BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from speech_to_text_vosk_web import convert_to_wav, transcribe_file, wav_has_audio

from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestedCredentialData,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialType,
    PublicKeyCredentialUserEntity,
)
from fido2.cose import CoseKey
from fido2 import cbor

FACE_DISTANCE_THRESHOLD = 0.60  # Default face-match threshold (lower = stricter).


def _find_user_by_email_or_username(value):
    # Resolve login target for face verification and WebAuthn flows.
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    user_obj = User.objects.filter(email__iexact=cleaned).first()
    if user_obj is None:
        user_obj = User.objects.filter(username__iexact=cleaned).first()
    return user_obj


def _superuser_required(view_func):
    return user_passes_test(lambda user: user.is_active and user.is_superuser, login_url="/signin/")(view_func)


def home(request):
    return render(request, "index.html")


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


from django.shortcuts import render
from .utils_sign import get_sign_for_word
from .utils import arabic_to_latin

import json
from pathlib import Path

def learning(request):
    context = {"sign_image": None, "word": "", "reference_landmarks": {}}
    if request.method == "POST":
        word_input = request.POST.get("word_input").strip().lower()
        # Récupérer l'image du signe
        context["sign_image"] = get_sign_for_word(word_input)
        context["word"] = word_input

        # Charger les landmarks de référence
        landmarks_path = Path("reference_landmarks.json")
        if landmarks_path.exists():
            with open(landmarks_path, "r") as f:
                all_landmarks = json.load(f)
            context["reference_landmarks"] = all_landmarks.get(word_input, {})

    return render(request, "learning.html", context)


def submit_reclamation(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        category = request.POST.get("category", "").strip()
        message = request.POST.get("message", "").strip()

        if name and email and message and category:
            Reclamation.objects.create(
                name=name,
                email=email,
                category=category,
                message=message,
            )
            messages.success(request, "Message sent successfully.")
        else:
            messages.error(request, "Please fill in all fields.")

    return redirect(request.META.get("HTTP_REFERER", "/"))




def signin(request):
    context = {"error": ""}
    if request.method == "POST":
        email_or_username_raw = request.POST.get("email", "").strip()
        email_or_username = email_or_username_raw.lower()
        password = request.POST.get("password", "")
        next_url = request.POST.get("next") or request.GET.get("next")

        user = authenticate(request, username=email_or_username, password=password)
        if user is None:
            user_obj = User.objects.filter(email__iexact=email_or_username_raw).first()
            if user_obj is None:
                user_obj = User.objects.filter(username__iexact=email_or_username_raw).first()
            if user_obj is not None:
                user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            context["error"] = "Invalid credentials."
        else:
            login(request, user)
            if user.is_superuser:
                return redirect("/backoffice/events/")
            if next_url:
                return redirect(next_url)
            return redirect("/")

    return render(request, "signin.html", context)


def signout(request):
    logout(request)
    return redirect("/")


def profile(request):
    if not request.user.is_authenticated:
        return redirect("/signin/")
    profile_data = UserProfile.objects.filter(user=request.user).first()
    return render(request, "profile.html", {"profile": profile_data})


def _get_fido2_server(request):
    # Configure WebAuthn RP settings based on the current host.
    host = request.get_host().split(":")[0]
    origin = f"{request.scheme}://{request.get_host()}"
    rp = PublicKeyCredentialRpEntity(
        id=host,
        name=settings.WEBAUTHN_RP_NAME,
    )
    return Fido2Server(rp, verify_origin=lambda value: value == origin)


@ensure_csrf_cookie
def webauthn_register_page(request):
    if not request.user.is_authenticated:
        return redirect("/signin/")
    return render(request, "webauthn_register.html")


def webauthn_register_options(request):
    # Begin WebAuthn registration (creates publicKey options).
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method."}, status=405)

    existing_creds = WebAuthnCredential.objects.filter(user=request.user)
    exclude_credentials = [
        PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY,
            id=cred.credential_id,
        )
        for cred in existing_creds
    ]

    user_entity = PublicKeyCredentialUserEntity(
        id=str(request.user.id).encode("utf-8"),
        name=request.user.username,
        display_name=request.user.first_name or request.user.username,
    )

    server = _get_fido2_server(request)
    options, state = server.register_begin(user_entity, exclude_credentials)
    request.session["webauthn_register_state"] = state

    return JsonResponse(dict(options.public_key))


def webauthn_register_verify(request):
    # Complete WebAuthn registration and store credential.
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method."}, status=405)

    state = request.session.get("webauthn_register_state")
    if not state:
        return JsonResponse({"error": "Registration session expired."}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    server = _get_fido2_server(request)
    auth_data = server.register_complete(state, data)
    credential_data = auth_data.credential_data
    if credential_data is None:
        return JsonResponse({"error": "Missing credential data."}, status=400)

    WebAuthnCredential.objects.create(
        user=request.user,
        credential_id=credential_data.credential_id,
        public_key=cbor.encode(credential_data.public_key),
        aaguid=credential_data.aaguid,
        sign_count=auth_data.counter,
    )

    return JsonResponse({"status": "ok"})


def webauthn_authenticate_options(request):
    # Begin WebAuthn authentication for a user (allowCredentials).
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method."}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    email_or_username = (data.get("email") or "").strip()
    if not email_or_username:
        return JsonResponse({"error": "Email is required."}, status=400)

    user_obj = User.objects.filter(email__iexact=email_or_username).first()
    if user_obj is None:
        user_obj = User.objects.filter(username__iexact=email_or_username).first()
    if user_obj is None:
        return JsonResponse({"error": "Account not found."}, status=404)

    credentials = WebAuthnCredential.objects.filter(user=user_obj)
    if not credentials.exists():
        return JsonResponse({"error": "No Face ID registered for this account."}, status=404)

    allow_credentials = [
        PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY,
            id=cred.credential_id,
        )
        for cred in credentials
    ]

    server = _get_fido2_server(request)
    options, state = server.authenticate_begin(allow_credentials)
    request.session["webauthn_auth_state"] = state
    request.session["webauthn_auth_user_id"] = user_obj.id

    return JsonResponse(dict(options.public_key))


def webauthn_authenticate_verify(request):
    # Complete WebAuthn authentication and sign in the user.
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method."}, status=405)

    state = request.session.get("webauthn_auth_state")
    user_id = request.session.get("webauthn_auth_user_id")
    if not state or not user_id:
        return JsonResponse({"error": "Authentication session expired."}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    user_obj = User.objects.filter(id=user_id).first()
    if user_obj is None:
        return JsonResponse({"error": "Account not found."}, status=404)

    credentials = WebAuthnCredential.objects.filter(user=user_obj)
    if not credentials.exists():
        return JsonResponse({"error": "No Face ID registered for this account."}, status=404)

    attested_credentials = []
    for cred in credentials:
        public_key = CoseKey.parse(cbor.decode(cred.public_key))
        attested_credentials.append(
            AttestedCredentialData.create(cred.aaguid, cred.credential_id, public_key)
        )

    server = _get_fido2_server(request)
    server.authenticate_complete(state, attested_credentials, data)

    login(request, user_obj)
    return JsonResponse({"status": "ok"})


@require_POST
def face_verify(request):
    # Face recognition login using live camera capture + reference image.
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    email_or_username = data.get("email")
    live_image = data.get("image")
    if not email_or_username:
        return JsonResponse({"error": "Email is required."}, status=400)
    if not live_image:
        return JsonResponse({"error": "Live image is required."}, status=400)

    user_obj = _find_user_by_email_or_username(email_or_username)
    if user_obj is None:
        return JsonResponse({"error": "Account not found."}, status=404)

    profile_data = UserProfile.objects.filter(user=user_obj).first()
    enrollment_path = get_enrollment_image_path(settings.MEDIA_ROOT, user_obj.id)
    if enrollment_path.exists():
        reference_path = enrollment_path
    elif profile_data and profile_data.profile_image:
        reference_path = Path(profile_data.profile_image.path)
    else:
        return JsonResponse({"error": "No profile photo or enrollment selfie found."}, status=400)

    is_match, distance, error = compare_face_to_reference(reference_path, live_image, FACE_DISTANCE_THRESHOLD)
    if error:
        return JsonResponse({"error": error}, status=400)

    if not is_match:
        return JsonResponse({"error": "Face did not match the reference photo.", "distance": distance}, status=401)

    login(request, user_obj)
    return JsonResponse({"status": "ok", "distance": distance})


def edit_profile(request):
    if not request.user.is_authenticated:
        return redirect("/signin/")

    profile_data = UserProfile.objects.filter(user=request.user).first()
    if profile_data is None:
        profile_data = UserProfile(user=request.user)
    context = {"profile": profile_data, "error": "", "success": ""}

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        birth_date = request.POST.get("birth_date", "").strip()
        has_disability = request.POST.get("has_disability") == "yes"
        disability_type = request.POST.get("disability_type", "").strip()
        profile_image = request.FILES.get("profile_image")

        if not full_name or not email or not phone or not birth_date:
            context["error"] = "Please fill in all required fields."
            return render(request, "edit_profile.html", context)

        existing_user = User.objects.filter(email__iexact=email).exclude(id=request.user.id).first()
        if existing_user:
            context["error"] = "This email is already used by another account."
            return render(request, "edit_profile.html", context)

        request.user.first_name = full_name
        request.user.email = email
        request.user.username = email
        request.user.save()

        profile_data.phone = phone
        profile_data.birth_date = birth_date
        profile_data.has_disability = has_disability
        profile_data.disability_type = disability_type if has_disability else ""
        if profile_image:
            profile_data.profile_image = profile_image
        profile_data.save()

        context["success"] = "Profile updated successfully."

    return render(request, "edit_profile.html", context)


def signup(request):
    context = {"error": ""}
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        profile_image = request.FILES.get("profile_image")
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
                profile_image=profile_image,
                phone=phone,
                birth_date=birth_date,
                has_disability=has_disability,
                disability_type=disability_type if has_disability else "",
            )
            login(request, user)
            return render(request, "home.html")

    return render(request, "signup.html", context)


@csrf_exempt
def get_animation(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            word = data.get('word', '').lower().strip()
            
            # Construct path to animations
            animations_dir = settings.BASE_DIR / 'sign-avatar' / 'backend' / 'dataset_animations'
            json_path = animations_dir / f"{word}.json"
            
            if json_path.exists():
                with open(json_path, "r", encoding='utf-8') as f:
                    animation_data = json.load(f)
                return JsonResponse(animation_data, safe=False)
            else:
                return JsonResponse([], safe=False) # Return empty list if not found
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

@_superuser_required
def backoffice_events(request):
    context = {"events": Event.objects.order_by("-date"), "error": "", "success": ""}
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        date = request.POST.get("date", "").strip()
        description = request.POST.get("description", "").strip()
        location = request.POST.get("location", "").strip()
        image = request.FILES.get("image")

        if not name or not date or not description:
            context["error"] = "Please fill in name, date, and description."
            return render(request, "BACKEND/events.html", context)

        Event.objects.create(
            name=name,
            date=date,
            description=description,
            location=location,
            image=image,
        )
        context["success"] = "Event created successfully."
        context["events"] = Event.objects.order_by("-date")

    return render(request, "BACKEND/events.html", context)


@_superuser_required
def backoffice_users(request):
    users = User.objects.select_related("userprofile").order_by("-date_joined")
    return render(request, "BACKEND/users.html", {"users": users})


@_superuser_required
def backoffice_reclamations(request):
    reclamations = Reclamation.objects.order_by("-created_at")
    return render(request, "BACKEND/reclamations.html", {"reclamations": reclamations})
