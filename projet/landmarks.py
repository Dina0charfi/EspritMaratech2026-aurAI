import cv2
import mediapipe as mp
import json
import os

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=True, max_num_hands=1)

dataset_dir = "sign_images"  # dossier avec tous les mots comme sous-dossiers
all_landmarks = {}

for word in os.listdir(dataset_dir):
    word_dir = os.path.join(dataset_dir, word)
    if not os.path.isdir(word_dir):
        continue
    # On prend la première image de chaque mot
    img_path = os.path.join(word_dir, os.listdir(word_dir)[0])
    image = cv2.imread(img_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)
    if results.multi_hand_landmarks:
        landmarks = [{"x": lm.x, "y": lm.y} for lm in results.multi_hand_landmarks[0].landmark]
        all_landmarks[word] = landmarks

# Sauvegarde JSON
with open("reference_landmarks.json", "w") as f:
    json.dump(all_landmarks, f)
