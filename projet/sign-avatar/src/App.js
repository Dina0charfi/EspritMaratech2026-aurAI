import React, { useState, Suspense, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import Avatar from "./Avatar";
import "./App.css";

function App() {
  const [keypoints, setKeypoints] = useState(null);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("Ready");
  const animationTimer = useRef(null);

  const handlePlay = async () => {
    if (!inputText.trim()) return;
    
    setLoading(true);
    setStatus("Fetching animation...");
    
    try {
      const response = await fetch("http://localhost:5000/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ word: inputText }),
      });
      
      const data = await response.json();
      
      if (!data || data.length === 0) {
        setStatus(`No animation found for "${inputText}"`);
        setLoading(false);
        return;
      }
      
      setStatus(`Playing "${inputText}"...`);
      
      let index = 0;
      if (animationTimer.current) clearInterval(animationTimer.current);

      // Play at ~30 FPS
      animationTimer.current = setInterval(() => {
          if (index >= data.length) {
              clearInterval(animationTimer.current);
              setStatus("Finished");
              setLoading(false);
              return; // Keep last frame pose
          }
          setKeypoints(data[index]);
          index++;
      }, 33);

    } catch (error) {
      console.error(error);
      setStatus("Error fetching animation");
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handlePlay();
  };

  return (
    <div className="container">
      <header className="header">
        <h1 className="title">Sign Avatar AI</h1>
        <div className="controls">
          <input
            type="text"
            className="input-field"
            placeholder="Type a word (e.g. bonjour)..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button 
            className="play-button" 
            onClick={handlePlay} 
            disabled={loading}
            title="Play Animation"
          >
            {loading ? "..." : "▶"}
          </button>
        </div>
      </header>
      <div className="main-content">
        <Canvas className="avatar-canvas" camera={{ position: [0, 1.5, 3], fov: 50 }}>
          <ambientLight intensity={0.6} />
          <directionalLight position={[5, 10, 5]} intensity={1.5} castShadow />
          <pointLight position={[-5, 5, 5]} intensity={0.5} />
          <OrbitControls 
            target={[0, 1, 0]} 
            minDistance={1} 
            maxDistance={5} 
            enablePan={false} 
          />
          <Suspense fallback={<Html><div style={{color:'white'}}>Loading Model...</div></Html>}>
            <Avatar keypoints={keypoints} />
          </Suspense>
          <gridHelper args={[20, 20, 0x444444, 0x222222]} />
        </Canvas>
        <div className="status-bar">Status: {status}</div>
      </div>
    </div>
  );
}

export default App;
