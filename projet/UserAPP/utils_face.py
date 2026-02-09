import base64
import io
from pathlib import Path
from typing import Optional, Tuple

try:
    # face_recognition is the core library providing face detection/encoding.
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    face_recognition = None
    FACE_RECOGNITION_AVAILABLE = False


def _decode_data_url(data_url: str) -> bytes:
    # Accept either data URLs or raw base64 strings.
    if "," in data_url:
        _, data = data_url.split(",", 1)
    else:
        data = data_url
    return base64.b64decode(data)


def get_enrollment_image_path(media_root: Path, user_id: int) -> Path:
    # Stable location for the optional enrollment selfie.
    return Path(media_root) / "face_enroll" / f"user_{user_id}.jpg"


def save_data_url_to_path(data_url: str, path: Path) -> None:
    # Persist a captured data URL as an image file.
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _decode_data_url(data_url)
    path.write_bytes(data)


def _get_single_face_encoding(image) -> Tuple[Optional[object], Optional[str]]:
    # Require exactly one face to reduce false matches.
    locations = face_recognition.face_locations(image)
    if len(locations) != 1:
        return None, f"Expected 1 face, found {len(locations)}."
    encoding = face_recognition.face_encodings(image, locations)[0]
    return encoding, None


def compare_face_to_reference(reference_path: Path, live_data_url: str, threshold: float) -> Tuple[bool, Optional[float], Optional[str]]:
    # Compare a live capture to the reference image using face embeddings.
    if not FACE_RECOGNITION_AVAILABLE:
        return False, None, "Face recognition dependencies are not installed."

    try:
        ref_image = face_recognition.load_image_file(str(reference_path))
    except Exception as exc:
        return False, None, f"Failed to load reference image: {exc}"

    ref_encoding, ref_error = _get_single_face_encoding(ref_image)
    if ref_error:
        return False, None, f"Reference image: {ref_error}"

    try:
        live_bytes = _decode_data_url(live_data_url)
        live_image = face_recognition.load_image_file(io.BytesIO(live_bytes))
    except Exception as exc:
        return False, None, f"Failed to load live image: {exc}"

    live_encoding, live_error = _get_single_face_encoding(live_image)
    if live_error:
        return False, None, f"Live image: {live_error}"

    distance = face_recognition.face_distance([ref_encoding], live_encoding)[0]
    return distance <= threshold, float(distance), None
