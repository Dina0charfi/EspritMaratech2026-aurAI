from pathlib import Path
from random import choice
import base64
from io import BytesIO
import re
from difflib import get_close_matches

import torch
import numpy as np

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "sign_model_and_images.pth"


def _load_mapping_from_file(path: Path):
	if not path.exists():
		return None
	try:
		data = torch.load(path, map_location="cpu", weights_only=False)
	except Exception:
		return None
	if not isinstance(data, dict):
		return None

	# If the .pth has a 'word_to_images' key, use it
	raw_mapping = data.get("word_to_images", data)

	normalized = {}
	for word, images in raw_mapping.items():
		if not isinstance(word, str):
			continue
		if isinstance(images, (list, tuple)) and images:
			# Keep images as they are (numpy arrays), don't convert to str
			normalized[word.lower()] = list(images)

	return normalized or None


def _scan_dataset(dataset_dir: Path):
	mapping = {}
	if not dataset_dir.exists():
		return mapping

	for category in dataset_dir.iterdir():
		if not category.is_dir():
			continue
		for word_dir in category.iterdir():
			if not word_dir.is_dir():
				continue
			images = [str(img) for img in word_dir.glob("*.jpg")]
			if images:
				mapping[word_dir.name.lower()] = images

	return mapping


def _load_word_to_images():
	mapping = _load_mapping_from_file(MODEL_PATH)
	if mapping:
		return mapping
	return {}



word_to_images = _load_word_to_images()
_normalized_index = None
FUZZY_CUTOFF = 0.70
ALIASES = {
	"mra": "mar2a",
}


def _array_to_base64(img_array):
	"""Convert numpy array to base64 data URL for HTML display."""
	if not PIL_AVAILABLE:
		print("ERROR: PIL/Pillow is not installed!")
		return None
		
	try:
		if isinstance(img_array, np.ndarray):
			# Ensure uint8 type
			if img_array.dtype != np.uint8:
				img_array = img_array.astype(np.uint8)
			
			# Convert to PIL Image
			img = Image.fromarray(img_array)
			
			# Convert to base64
			buffered = BytesIO()
			img.save(buffered, format="JPEG")
			img_str = base64.b64encode(buffered.getvalue()).decode()
			return f"data:image/jpeg;base64,{img_str}"
		elif isinstance(img_array, str):
			# Already a path or URL
			return img_array
	except Exception as e:
		print(f"ERROR in _array_to_base64: {e}")
		import traceback
		traceback.print_exc()
		return None
	return None


def _normalize_word(value: str) -> str:
	value = value.lower().strip()
	value = re.sub(r"\s+", "", value)
	value = re.sub(r"[^a-z0-9]", "", value)
	# Collapse repeated characters to tolerate small typos
	value = re.sub(r"(.)\1+", r"\1", value)
	return value


def _apply_aliases(value: str) -> str:
	normalized = _normalize_word(value)
	return ALIASES.get(normalized, value)


def _build_normalized_index():
	index = {}
	for word in word_to_images.keys():
		key = _normalize_word(word)
		if key:
			index.setdefault(key, []).append(word)
	return index


def _tokenize_words(text: str):
	# Keep latin letters + numbers (3aslema, mar2a, etc.)
	return re.findall(r"[a-z0-9]+", text.lower())


def get_sign_for_word(word: str):
	if not word:
		return None

	global _normalized_index
	if _normalized_index is None:
		_normalized_index = _build_normalized_index()

	original = word.lower()
	original = _apply_aliases(original)
	images = word_to_images.get(original)
	if not images:
		normalized = _normalize_word(original)
		# Direct match on normalized index
		if normalized in _normalized_index:
			candidate = _normalized_index[normalized][0]
			images = word_to_images.get(candidate)
		# Fuzzy match if still missing
		if not images and normalized:
			choices = list(_normalized_index.keys())
			match = get_close_matches(normalized, choices, n=1, cutoff=FUZZY_CUTOFF)
			if match:
				candidate = _normalized_index[match[0]][0]
				images = word_to_images.get(candidate)

	# Fallback: fuzzy match against raw keys
	if not images:
		match = get_close_matches(original, list(word_to_images.keys()), n=1, cutoff=FUZZY_CUTOFF)
		if match:
			images = word_to_images.get(match[0])
	if images:
		selected = choice(images)
		print(f"DEBUG: Selected image type: {type(selected)}, is ndarray: {isinstance(selected, np.ndarray)}")
		if isinstance(selected, np.ndarray):
			print(f"DEBUG: Array shape: {selected.shape}, dtype: {selected.dtype}")
		result = _array_to_base64(selected)
		print(f"DEBUG: Conversion result type: {type(result)}, is None: {result is None}")
		if result and isinstance(result, str):
			print(f"DEBUG: Result starts with 'data:': {result.startswith('data:')}")
		return result
	return None


def get_signs_for_text(text: str):
	if not text:
		return []
	results = []
	for token in _tokenize_words(text):
		img = get_sign_for_word(token)
		if img:
			results.append({"word": token, "image": img})
	return results

