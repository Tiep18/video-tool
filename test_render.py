import os
import json
import time
import wave
import struct
import math
from PIL import Image
from core.video_builder import build_video

def create_dummy_audio(filepath, duration, sample_rate=22050):
    print(f"Generating dummy audio file: {filepath} ({duration}s)")
    with wave.open(filepath, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        n_frames = int(duration * sample_rate)
        for i in range(n_frames):
            # A simple 440Hz sine wave tone at low volume
            value = int(32767.0 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate) * 0.1)
            data = struct.pack('<h', value)
            w.writeframesraw(data)

def create_dummy_images(count, w=1080, h=1920):
    print(f"Generating {count} dummy images...")
    paths = []
    colors = [
        (239, 71, 111),   # Soft pink/red
        (247, 140, 107),  # Soft orange
        (255, 209, 102),  # Soft yellow
        (6, 214, 160),    # Soft green
        (17, 138, 178),   # Soft blue
        (7, 59, 76),      # Deep navy
        (131, 56, 236),   # Violet
        (251, 86, 196),   # Bright pink
        (58, 12, 163),    # Royal purple
        (76, 201, 240),   # Cyan
        (244, 91, 105),   # Coral
        (90, 24, 154)     # Indigo
    ]
    for i in range(count):
        color = colors[i % len(colors)]
        img = Image.new("RGB", (w, h), color)
        path = f"dummy_image_{i}.jpg"
        img.save(path)
        paths.append(path)
    return paths

def main():
    # 1. Load scenes from cache_state
    if not os.path.exists("cache_state.json"):
        print("Error: cache_state.json not found in workspace.")
        return
        
    with open("cache_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    scenes = state["matched_scenes"]
    print(f"Loaded {len(scenes)} scenes from cache_state.json")
    
    # 2. Setup dummy assets
    audio_path = "dummy_audio.wav"
    create_dummy_audio(audio_path, 57.0)
    image_paths = create_dummy_images(len(scenes))
    
    # 3. Benchmark Fast Preview Mode
    output_preview = "test_output_preview.mp4"
    if os.path.exists(output_preview):
        os.remove(output_preview)
        
    print("\n--- Starting Fast Preview Mode Benchmark (360p, 15 FPS) ---")
    start_time = time.time()
    build_video(
        matched_scenes=scenes,
        image_paths=image_paths,
        audio_path=audio_path,
        output_path=output_preview,
        resolution="portrait_9_16",
        ken_burns_intensity=0.08,
        transition_dur=0.8,
        preview_mode=True,
    )
    preview_time = time.time() - start_time
    print(f"Fast Preview Render Time: {preview_time:.2f} seconds")
    
    # 4. Benchmark Full HD Mode
    output_full = "test_output_full.mp4"
    if os.path.exists(output_full):
        os.remove(output_full)
        
    print("\n--- Starting Full HD Mode Benchmark (1080p, 25 FPS) ---")
    start_time = time.time()
    build_video(
        matched_scenes=scenes,
        image_paths=image_paths,
        audio_path=audio_path,
        output_path=output_full,
        resolution="portrait_9_16",
        ken_burns_intensity=0.08,
        transition_dur=0.8,
        preview_mode=False,
    )
    full_time = time.time() - start_time
    print(f"Full HD Render Time: {full_time:.2f} seconds")
    
    print("\n--- Benchmark Summary ---")
    print(f"Fast Preview: {preview_time:.2f}s")
    print(f"Full HD:      {full_time:.2f}s")
    print(f"Speedup of Preview Mode: {full_time / preview_time:.2f}x")
    
    # 5. Clean up temporary dummy assets
    print("\nCleaning up temporary dummy assets...")
    if os.path.exists(audio_path):
        os.remove(audio_path)
    for p in image_paths:
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(output_preview):
        os.remove(output_preview)
    if os.path.exists(output_full):
        os.remove(output_full)
    print("Cleanup done.")

if __name__ == "__main__":
    main()
