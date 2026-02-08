try:
    import cv2
    import mediapipe as mp
except ImportError as e:
    print(f"Warning: Dependencies missing in extract_motion.py: {e}")
    cv2 = None
    mp = None

import json
import numpy as np
import os
import glob
import math

# --- 1. Utilities for Math & Smoothing ---

class OneEuroFilter:
    def __init__(self, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = None
        self.dx_prev = 0
        self.t_prev = None

    def smoothing_factor(self, t_e, cutoff):
        r = 2 * math.pi * cutoff * t_e
        return r / (r + 1)

    def exponential_smoothing(self, a, x, x_prev):
        return a * x + (1 - a) * x_prev

    def filter(self, x, t=None):
        if self.t_prev is None:
            if t is None: t = 0
            self.t_prev = t
            self.x_prev = x
            self.dx_prev = 0
            return x
            
        if t is None:
            t = self.t_prev + 0.033 # Assume 30fps if no time provided

        t_e = t - self.t_prev
        if t_e <= 0: return self.x_prev # Should not happen

        dx = (x - self.x_prev) / t_e
        smoothed_dx = self.exponential_smoothing(self.smoothing_factor(t_e, self.d_cutoff), dx, self.dx_prev)

        cutoff = self.min_cutoff + self.beta * abs(smoothed_dx)
        smoothed_x = self.exponential_smoothing(self.smoothing_factor(t_e, cutoff), x, self.x_prev)

        self.x_prev = smoothed_x
        self.dx_prev = smoothed_dx
        self.t_prev = t
        return smoothed_x

# Create a filter bank
filters = {}
def smooth_bone(name, axis, val):
    key = f"{name}_{axis}"
    if key not in filters:
        filters[key] = OneEuroFilter(min_cutoff=0.1, beta=0.05) # Tuned for smoothness
    return filters[key].filter(val)

# --- 2. Vector Math for 3D Rotations ---

def normalize(v):
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v

def get_euler_from_vector(v, side="right"):
    """
    Convert a bone vector to Euler angles (x, y, z) for a T-Pose character.
    T-Pose Assumption:
    - Right Arm rests along +X axis.
    - Left Arm rests along -X axis.
    """
    v = normalize(v)
    x, y, z = v[0], v[1], v[2]
    
    # MediaPipe Coordinates (World):
    # x: Right (+), Left (-)
    # y: Top (-), Bottom (+)  <-- Note: In 3D graphics, Y is often UP. MP Y is DOWN.
    # z: Camera (+?) or Depth. MP z is usually negative = forward?
    # Actually MP World Landmarks: "y is pointing up". Wait checking docs...
    # Docs: "World landmarks are in meters. The origin is the center of hips."
    # Let's assume MP World: Y is UP? No usually Y is inverted image coords.
    # Let's infer from data: Arms down -> Y increases properly.
    
    # We want to map to Three.js T-Pose:
    # Right Arm (+X).
    
    # Calculate Yaw (rotation around Y-axis) and Pitch (rotation around Z-axis)
    # This is a simplification. Ideally use Quaternions.
    
    # Basic Spherical Coords mapping
    # Pitch (Z-rotation): Up/Down
    # Yaw (Y-rotation): Forward/Back
    
    angle_y = 0
    angle_z = 0
    angle_x = 0 # Twist - hard to infer without elbows orientation, assume 0
    
    if side == "right":
        # Vector points roughly +X
        # Yaw (Horizontal): atan2(-z, x). 
        #   If z is forward (+), and x is right (+), angle is 0.
        # Pitch (Vertical): atan2(y, sqrt(x^2 + z^2))?
        # Let's use simple logic relative to (1,0,0)
        
        # In Three.js for Right Arm:
        # +Z rot = Arm goes UP (or Front?) -> Depends on Bone Axis.
        # Mixamo RightArm: Z-axis rotation moves it Forward/Back? Y is Up/Down?
        # Usually:
        #   Z: Forward/Back (Horizontal Swing)
        #   y: Twist
        #   x: Up/Down (Vertical Swing) ?? 
        #   Wait, Mixamo bones are weird.
        #   Let's stick to standard math and let Avatar.js retarget/fix axes if needed.
        #   Let's produce pure spherical rotations relative to shoulder.
        
        # Global Vector Direction (v)
        # We need rotation R such that R * (1,0,0) = v
        
        pitch = -math.asin(v[1]) # Y component determines Up/Down angle
        yaw = math.atan2(-v[2], v[0]) # Z, X components determine Front/Back
        
        # Output: x, y, z Eulers
        # We'll map Pitch -> Z rotation, Yaw -> Y rotation?
        return 0, yaw, pitch

    elif side == "left":
        # Relative to (-1,0,0)
        pitch = math.asin(v[1]) # Sign flip?
        # If v[1] is positive (arm down), Pitch should be negative?
        
        yaw = math.atan2(v[2], -v[0]) # Relative to -X
        
        return 0, yaw, pitch
        
    return 0, 0, 0

# --- 3. Main Processing Function ---
mp_pose = None
if mp:
    try:
        mp_pose = mp.solutions.pose
    except AttributeError:
        print("Warning: mediapipe.solutions not found. Try 'pip install mediapipe' again.")
        mp_pose = None

def process_video(video_path):
    if not cv2 or not mp or mp_pose is None:
        print("Error: OpenCV or MediaPipe not functioning correctly.")
        return []

    cap = cv2.VideoCapture(video_path)

    frames_data = []
    
    # Using Holistic (or Pose) with World Landmarks (Meters)
    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=2, # Best quality
        smooth_landmarks=True, 
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as pose:
        
        global filters
        filters = {} # Reset filters
        
        while cap.isOpened():
            success, image = cap.read()
            if not success: break
            
            # Convert BGR to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = pose.process(image_rgb)
            
            if results.pose_world_landmarks:
                lm = results.pose_world_landmarks.landmark
                
                # Helper to get numpy point
                def p(idx): return np.array([lm[idx].x, lm[idx].y, lm[idx].z])
                
                # Indices:
                # 11: Left Shoulder, 12: Right Shoulder
                # 13: Left Elbow,    14: Right Elbow
                # 15: Left Wrist,    16: Right Wrist
                
                # Vectors
                # Note: MP World Y is negative-up (inverted)?
                # Usually: Y is Down.
                # So if Arm is Down, Y is positive.
                # In 3D (ThreeJS), Y is Up.
                # We need to invert Y and Z (MP Z is relative).
                
                # Remap to Standard 3D (Y-Up, Z-Front?)
                def to_space(vec):
                    return np.array([vec[0], -vec[1], -vec[2]]) 

                # Right Arm
                v_r_upper = to_space(p(14) - p(12)) # Elbow - Shoulder
                v_r_lower = to_space(p(16) - p(14)) # Wrist - Elbow
                
                # Left Arm
                v_l_upper = to_space(p(13) - p(11))
                v_l_lower = to_space(p(15) - p(13))
                
                # Calculate Rotations
                # Note: The mapping here (x,y,z output) must match what Avatar.js expects.
                # Avatar.js takes these and does: quaternion.setFromEuler(x, y, z)
                
                # Right Upper
                rx, ry, rz = get_euler_from_vector(v_r_upper, "right")
                frame_data = {}
                frame_data["RightArm"] = {
                    "x": smooth_bone("RightArm", "x", 0), # Twist ignored for now
                    "y": smooth_bone("RightArm", "y", ry),
                    "z": smooth_bone("RightArm", "z", rz)
                }
                
                # Left Upper
                lx, ly, lz = get_euler_from_vector(v_l_upper, "left")
                frame_data["LeftArm"] = {
                    "x": smooth_bone("LeftArm", "x", 0),
                    "y": smooth_bone("LeftArm", "y", ly),
                    "z": smooth_bone("LeftArm", "z", lz)
                }
                
                # Forearms (Simplified: Relative to Upper or Global?)
                # Avatar.js usually applies local rotation.
                # If we send Global orientation for Forearm, child inherits parent rotation...
                # So we need Local Rotation = Inverse(ParentRot) * ChildGlobalRot
                # That's complex math for this script. 
                # HACK: Send Forearms as 0 for now (stiff arms) or simple bend?
                # Alternative: Just set them flat to see if Shoulders track well first.
                # User wants "like the video". We need forearm bend.
                
                # Simple Elbow Bend (Hinge):
                # Angle between Upper and Lower vector.
                angle_r = calculate_angle(p(12), p(14), p(16))
                angle_l = calculate_angle(p(11), p(13), p(15))
                
                # Bend is usually around Z axis for T-pose arms?
                # 0 = straight, PI/2 = 90 deg.
                # Forearm resting is straight (0).
                # Bend reduces angle from 180 (straight in MP) to <180?
                # MP vectors: Straight arm -> angle 180 (PI). 90 deg bend -> PI/2.
                # We want rotation from 0 (straight) to X (bend).
                # bend = PI - angle.
                
                bend_r = math.pi - angle_r
                bend_l = math.pi - angle_l

                frame_data["RightForeArm"] = {"x": 0, "y": 0, "z": smooth_bone("RightForeArm", "z", bend_r)}
                frame_data["LeftForeArm"] = {"x": 0, "y": 0, "z": smooth_bone("LeftForeArm", "z", -bend_l)} # Negative for Left?
                
                frames_data.append(frame_data)

    cap.release()
    return frames_data

# Helper for Elbow Angle
def calculate_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba = a - b
    bc = c - b
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return np.arccos(np.clip(cosine, -1.0, 1.0))




if __name__ == "__main__":
    # Batch processing mode
    video_dir = os.path.join(os.path.dirname(__file__), "dataset_videos")
    output_dir = os.path.join(os.path.dirname(__file__), "dataset_animations")
    
    if not os.path.exists(video_dir):
        print(f"Creating video directory: {video_dir}")
        os.makedirs(video_dir)
        
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Walk through all subdirectories to find videos
    videos_found = []
    print(f"Scanning {video_dir}...")
    for root, dirs, files in os.walk(video_dir):
        for file in files:
            if file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                videos_found.append({
                    "path": os.path.join(root, file),
                    "name": file
                })
        
    if not videos_found:
        print(f"❌ No videos found in {video_dir} or its subfolders.")
        print("Please check your folder structure.")
    else:
        print(f"✅ Found {len(videos_found)} videos. Starting batch extraction...")
        print("This might take a minute...")
        
        count = 0
        for video_info in videos_found:
            video_name = video_info['name']
            input_path = video_info['path']
            print(f"Processing: {video_name}...")
            
            try:
                animation_data = process_video(input_path)
                
                if not animation_data:
                    print(f"⚠️ Warning: No motion detected in {video_name}")
                    continue

                # Use the filename (without extension) as the key
                # e.g., "my_video.mp4" -> "my_video"
                base_name = os.path.splitext(video_name)[0].lower().strip() 
                output_path = os.path.join(output_dir, f"{base_name}.json")
                
                with open(output_path, "w") as f:
                    json.dump(animation_data, f)
                print(f"  -> Saved: {base_name}.json ({len(animation_data)} frames)")
                count += 1
            except Exception as e:
                print(f"❌ Error processing {video_name}: {e}")
            
        print(f"Batch processing complete. Generated {count} animation files.")