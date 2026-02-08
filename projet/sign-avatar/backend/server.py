from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import random
import os
import glob

# Initialize Flask App
app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

import torch
import torch.nn as nn

# Define the Model Architecture based on the .pth file inspection
class SignLangCNN(nn.Module):
    def __init__(self):
        super(SignLangCNN, self).__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3), # Index 0
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3), # Index 3
            nn.ReLU(),
            nn.MaxPool2d(2)
        )
        self.lstm = nn.LSTM(input_size=8192, hidden_size=128, batch_first=True)
        self.fc = nn.Linear(128, 8) 

    def forward(self, x):
        batch_size, time_steps, C, H, W = x.size()
        c_in = x.view(batch_size * time_steps, C, H, W)
        c_out = self.cnn(c_in)
        r_in = c_out.view(batch_size, time_steps, -1)
        r_out, _ = self.lstm(r_in)
        out = self.fc(r_out[:, -1, :])
        return out

# Initialize and Load Model
try:
    model = SignLangCNN()
    # Load weights (map_location='cpu' ensures it works even if trained on GPU)
    model.load_state_dict(torch.load("backend/signlang_cnnlstm.pth", map_location=torch.device('cpu')))
    model.eval()
    print("SUCCESS: Model loaded successfully!")
except Exception as e:
    print(f"WARNING: Could not load model. Error: {e}")
    model = None

# Import our Motion Extractor
from extract_motion import process_video

def run_model_inference(word):
    """
    Looks for a pre-recorded JSON animation file for the given word.
    If not found, attempts to generate it from a video file.
    """
    print(f"Requesting sign for: {word}")
    
    # 1. Normalize word
    key = word.lower().strip()
    
    # 2. Check for JSON file in dataset_animations
    animations_dir = os.path.join(os.path.dirname(__file__), "dataset_animations")
    json_path = os.path.join(animations_dir, f"{key}.json")
    
    if os.path.exists(json_path):
        print(f"Found animation file: {json_path}")
        try:
            with open(json_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON: {e}")

    # 3. If JSON not found, looks for corresponding VIDEO
    print(f"JSON not found. Searching for video for '{key}'...")
    video_root = os.path.join(os.path.dirname(__file__), "dataset_videos")
    
    video_path = None
    for root, dirs, files in os.walk(video_root):
        for file in files:
            if os.path.splitext(file.lower())[0] == key and file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                 video_path = os.path.join(root, file)
                 break
        if video_path: break
    
    if video_path:
        print(f"Found video: {video_path}. Extracting motion...")
        try:
            # Run extraction (this might take a few seconds)
            animation_data = process_video(video_path)
            
            # Save it for next time
            if not os.path.exists(animations_dir):
                os.makedirs(animations_dir)
                
            with open(json_path, "w") as f:
                json.dump(animation_data, f)
            print(f"Saved generated animation to {json_path}")
            
            return animation_data
        except Exception as e:
            print(f"Error extracting motion: {e}")

    # 4. Last absolute fallback
    print(f"❌ Word '{word}' not found in animations or videos.")
    return [] 



@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    word = data.get('word', '')
    
    if not word:
        return jsonify({"error": "No word provided"}), 400

    # Get animation frames from your model
    animation_data = run_model_inference(word)
    
    return jsonify(animation_data)

@app.route('/get_video/<word>', methods=['GET'])
def get_video(word):
    video_root = os.path.join(os.path.dirname(__file__), 'dataset_videos')
    # Normalized search
    target = word.lower().strip()
    for root, dirs, files in os.walk(video_root):
        for file in files:
            # Check if filename starts with the word (e.g. "bras.mp4" matches "bras")
            if file.lower().startswith(target) and file.endswith('.mp4'):
                response = send_file(os.path.join(root, file), mimetype='video/mp4')
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response
    return jsonify({"error": "Video not found"}), 404

if __name__ == '__main__':
    print("Starting server on port 5000...")
    app.run(debug=True, port=5000)
