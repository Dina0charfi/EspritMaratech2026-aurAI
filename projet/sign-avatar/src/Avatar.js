import React, { useRef, useEffect } from "react";
import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

export default function Avatar({ keypoints }) {
  const group = useRef();
  const { scene, nodes } = useGLTF("/models/business_man.glb");
  const [boneRegistry, setBoneRegistry] = React.useState({});

  useEffect(() => {
     if (group.current) {
         group.current.rotation.y = 0; // Ensure it faces partial Z
     }

     // Build a registry of all available bones by traversing the scene
     const registry = {};
     scene.traverse((child) => {
         if (child.isBone) {
             registry[child.name] = child;
             // Also store sanitized names (remove ., _, spaces)
             const cleanName = child.name.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
             registry[cleanName] = child;
         }
     });
     console.log("Bone Registry Built:", Object.keys(registry));
     setBoneRegistry(registry);
  }, [scene]);

  const findBone = (name) => {
        // 1. Try Direct Lookup in nodes
        if (nodes[name]) return nodes[name];
        
        // Exact Map based on your GLB inspection
        // Expanded to support multiple conventions (ReadyPlayerMe, Mixamo, VRM)
        const boneMap = {
            "RightArm": ["UpperArm.R", "mixamorig:RightArm", "RightArm", "RightUpperArm", "R_Arm", "Right_Arm"],
            "LeftArm": ["UpperArm.L", "mixamorig:LeftArm", "LeftArm", "LeftUpperArm", "L_Arm", "Left_Arm"],
            "RightForeArm": ["LowerArm.R", "mixamorig:RightForeArm", "RightForeArm", "RightLowerArm", "R_ForeArm", "Right_ForeArm"],
            "LeftForeArm": ["LowerArm.L", "mixamorig:LeftForeArm", "LeftForeArm", "LeftLowerArm", "L_ForeArm", "Left_ForeArm"],
            "RightHand": ["Wrist.R", "mixamorig:RightHand", "RightHand", "RightWrist", "R_Hand", "Right_Hand"],
            "LeftHand": ["Wrist.L", "mixamorig:LeftHand", "LeftHand", "LeftWrist", "L_Hand", "Left_Hand"],
            "Head": ["Head", "mixamorig:Head", "CC_Base_Head"],
            "Neck": ["Neck", "mixamorig:Neck", "CC_Base_Neck"],
            "Spine": ["Torso", "mixamorig:Spine", "Spine", "Spine1", "Spine01"], 
            "Hips": ["Hips", "mixamorig:Hips", "Pelvis", "Root"],
            "RightUpLeg": ["UpperLeg.R", "mixamorig:RightUpLeg", "RightUpLeg", "RightThigh", "R_UpLeg"], 
            "RightLeg": ["LowerLeg.R", "mixamorig:RightLeg", "RightLeg", "RightCalf", "R_Leg"], 
            "LeftUpLeg": ["UpperLeg.L", "mixamorig:LeftUpLeg", "LeftUpLeg", "LeftThigh", "L_UpLeg"], 
            "LeftLeg": ["LowerLeg.L", "mixamorig:LeftLeg", "LeftLeg", "LeftCalf", "L_Leg"],
        };
        
        // 2. Try Map
        let targets = boneMap[name];
        if (targets) {
            // If strict value, convert to array
            if (!Array.isArray(targets)) targets = [targets];
            
            for (const target of targets) {
                if (nodes[target]) return nodes[target];
                if (boneRegistry[target]) return boneRegistry[target];
                
                // Try fuzzy
                const cleanTarget = target.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
                if (boneRegistry[cleanTarget]) return boneRegistry[cleanTarget];
            }
        }
        
        // 3. Try Fuzzy Search in Registry
        const cleanSearch = name.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
        if (boneRegistry[cleanSearch]) return boneRegistry[cleanSearch];

        // 4. Special cases
        if (name === "RightWrist") return findBone("RightHand");
        if (name === "LeftWrist") return findBone("LeftHand");

        // Fallback: Try "Little" instead of "Pinky" if standard map fails
        if (name.includes("Little") && targets) {
             const variant = targets[0].replace("Pinky", "Little");
             if (nodes[variant]) return nodes[variant];
        }

        return null;
  };

  const kpRef = useRef(keypoints);

  useEffect(() => {
    kpRef.current = keypoints;
    // Debug logging when keypoints update
    if (keypoints) {
        // console.log("Keypoints Updated:", Object.keys(keypoints));
    }
  }, [keypoints]);

  useFrame((state) => {
    const currentKeypoints = kpRef.current;
    
    // Idle Animation (Breathing) if no video data
    if (!currentKeypoints) {
        if (nodes.Neck) nodes.Neck.rotation.x = Math.sin(state.clock.elapsedTime * 2) * 0.1;
        // Optional: Force arms down in T-Pose
        return;
    }
    
    // Smooth factor (0.1 = very smooth/slow, 0.8 = responsive)
    const damp = 0.5; 
    
    // Safety check for rotation limits to prevent exploding avatar
    const limit = (v) => Math.max(-Math.PI, Math.min(Math.PI, v));
    
    for (let boneName in currentKeypoints) {
      const bone = findBone(boneName);
      if (bone) {
        const { x, y, z, position } = currentKeypoints[boneName];
        
        // Apply Rotation
        const targetEuler = new THREE.Euler(x, y, z);
        const targetQuat = new THREE.Quaternion().setFromEuler(targetEuler);
        bone.quaternion.slerp(targetQuat, damp);
        
        // Apply Position (Hips Only) to move the whole body
        if (position && boneName === "Hips") {
             // Clamped position to prevent flying away
             const clampedX = Math.max(-1, Math.min(1, position.x));
             const clampedY = Math.max(-0.5, Math.min(0.5, position.y)); 
             const clampedZ = Math.max(-1, Math.min(1, position.z));
             
             const targetPos = new THREE.Vector3(clampedX, clampedY + 0.9, clampedZ);
             bone.position.lerp(targetPos, damp);
        }
      }
    }
  });

  return (
    <group ref={group}>
      <primitive 
        object={scene} 
        position={[0, -1, 0]} 
        scale={[1.8, 1.8, 1.8]} 
      />
      {/* Floor to give context */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1, 0]}>
        <planeGeometry args={[10, 10]} />
        <meshStandardMaterial color="#333" />
      </mesh>
    </group>
  );
}
