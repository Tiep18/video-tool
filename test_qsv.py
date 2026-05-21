import os
import json
import time
import wave
import struct
import math
from PIL import Image
from moviepy.editor import CompositeVideoClip, AudioFileClip
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout
from core.video_builder import RESOLUTIONS, _make_vignette, make_camera_motion_clip, FPS, FADE_IN_DURATION, FADE_OUT_DURATION

def create_dummy_audio(filepath, duration, sample_rate=22050):
    with wave.open(filepath, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        n_frames = int(duration * sample_rate)
        for i in range(n_frames):
            value = int(32767.0 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate) * 0.1)
            data = struct.pack('<h', value)
            w.writeframesraw(data)

def create_dummy_images(count, w=1080, h=1920):
    paths = []
    colors = [(239, 71, 111), (247, 140, 107), (255, 209, 102), (6, 214, 160)]
    for i in range(count):
        img = Image.new("RGB", (w, h), colors[i % len(colors)])
        path = f"dummy_image_{i}.jpg"
        img.save(path)
        paths.append(path)
    return paths

def main():
    with open("cache_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    scenes = state["matched_scenes"]
    scenes = [s for s in scenes if s["end"] <= 15.0]
    
    audio_path = "dummy_audio.wav"
    create_dummy_audio(audio_path, 15.0)
    image_paths = create_dummy_images(len(scenes))
    
    out_w, out_h = RESOLUTIONS["portrait_9_16"]
    audio = AudioFileClip(audio_path)
    vignette = _make_vignette(out_w, out_h)
    
    clips = []
    prev_preset_idx = -1
    for i, scene in enumerate(scenes):
        img_path = image_paths[i]
        clip_duration = scene["end"] - scene["start"]
        if i < len(scenes) - 1:
            clip_duration += 0.8
        
        clip, prev_preset_idx = make_camera_motion_clip(
            image_path=img_path,
            clip_duration=clip_duration,
            scene_duration=scene["duration"],
            out_w=out_w,
            out_h=out_h,
            scene_index=i,
            prev_preset_idx=prev_preset_idx,
            intensity=0.08,
            vignette=vignette,
        )
        clip = clip.set_start(scene["start"])
        if i > 0:
            clip = clip.crossfadein(0.8)
        clips.append(clip)
        
    video = CompositeVideoClip(clips, size=(out_w, out_h)).set_duration(15.0)
    video = fadein(video, FADE_IN_DURATION)
    video = fadeout(video, FADE_OUT_DURATION)
    video = video.set_audio(audio)
    
    # Test 1: CPU Encoding (libx264)
    print("Testing CPU Encoding (libx264)...")
    out_cpu = "test_cpu.mp4"
    start_t = time.time()
    video.write_videofile(
        out_cpu,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        bitrate="3500k",
        threads=0,
        verbose=False,
        logger=None,
    )
    cpu_time = time.time() - start_t
    print(f"CPU Encoding Time: {cpu_time:.2f} seconds")
    
    # Test 2: Intel QSV GPU Encoding (h264_qsv)
    print("\nTesting Intel QSV GPU Encoding (h264_qsv)...")
    out_qsv = "test_qsv.mp4"
    start_t = time.time()
    try:
        video.write_videofile(
            out_qsv,
            fps=FPS,
            codec="h264_qsv",
            audio_codec="aac",
            bitrate="3500k",
            threads=0,
            verbose=False,
            logger=None,
        )
        qsv_time = time.time() - start_t
        print(f"QSV GPU Encoding Time: {qsv_time:.2f} seconds")
        print(f"Speedup: {cpu_time / qsv_time:.2f}x")
    except Exception as e:
        print(f"QSV Encoding failed with error: {e}")
        
    # Cleanup
    video.close()
    audio.close()
    if os.path.exists(audio_path):
        os.remove(audio_path)
    for p in image_paths:
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(out_cpu):
        os.remove(out_cpu)
    if os.path.exists(out_qsv):
        os.remove(out_qsv)

if __name__ == "__main__":
    main()
