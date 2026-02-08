import mediapipe as mp
import sys

print(f"Python: {sys.version}")

try:
    import mediapipe.python.solutions as solutions
    print("Success: import mediapipe.python.solutions")
    print(dir(solutions))
except ImportError as e:
    print(f"Failed deep import: {e}")

try:
    # Sometimes it requires importing the specific solution
    from mediapipe.python.solutions import pose
    print("Success: from mediapipe.python.solutions import pose")
except ImportError as e:
    print(f"Failed pose import: {e}")
