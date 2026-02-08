
try:
    import mediapipe as mp
    print(f"Direct: {dir(mp)}")
    try:
        print(f"Solutions: {mp.solutions}")
    except AttributeError:
        print("mp.solutions missing")
except ImportError:
    print("Import failed")
