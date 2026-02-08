from pygltflib import GLTF2
import sys

def inspect_glb(path):
    try:
        gltf = GLTF2().load(path)
        print(f"Loaded {path}")
        print("Nodes/Bones found:")
        for i, node in enumerate(gltf.nodes):
            if node.name:
                print(f"{i}: {node.name}")
    except Exception as e:
        print(f"Error loading GLB: {e}")

if __name__ == "__main__":
    inspect_glb("public/models/business_man.glb")