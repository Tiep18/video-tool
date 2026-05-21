import os
import json
import time
import wave
import struct
import math
from PIL import Image
from core.video_builder import build_video

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
    # Render only a 15-second subclip of the 12 scenes to keep profiling fast (15s * 25 FPS = 375 frames)
    with open("cache_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    scenes = state["matched_scenes"]
    
    # We only take the first 4 scenes to fit in 15 seconds
    scenes = [s for s in scenes if s["end"] <= 15.0]
    print(f"Loaded {len(scenes)} scenes for 15s test clip")

    audio_path = "dummy_audio.wav"
    create_dummy_audio(audio_path, 15.0)
    image_paths = create_dummy_images(len(scenes))
    
    # Test different thread options
    options = [1, 2, 4, 0]
    for opt in options:
        # Monkey patch build_video or write a custom version inside here
        from moviepy.editor import CompositeVideoClip, AudioFileClip
        from moviepy.video.fx.fadein import fadein
        from moviepy.video.fx.fadeout import fadeout
        from core.video_builder import RESOLUTIONS, _make_vignette, make_camera_motion_clip, FPS, FADE_IN_DURATION, FADE_OUT_DURATION
        
        # Simple rendering function with variable threads
        def custom_build(threads_val):
            out_w, out_h = RESOLUTIONS["portrait_9_16"]
            audio = AudioFileClip(audio_path)
            vignette = _make_vignette(out_w, out_h)
            
            clips = []
            prev_preset_idx = -1
            for i, scene in enumerate(scenes):
                img_path = image_paths[i]
                clip_duration = scene["end"] - scene["start"]
                if i < len(scenes) - 1:
                    clip_duration += 0.8  # transition overlap
                
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
            
            out_name = f"test_threads_{threads_val}.mp4"
            start_t = time.time()
            video.write_videofile(
                out_name,
                fps=FPS,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                bitrate="3500k",
                threads=threads_val,
                verbose=False,
                logger=None,
            )
            elapsed = time.time() - start_t
            print(f"Threads={threads_val}: {elapsed:.2f} seconds")
            video.close()
            audio.close()
            if os.path.exists(out_name):
                os.remove(out_name)
                
        custom_build(opt)
        
    # Cleanup
    if os.path.exists(audio_path):
        os.remove(audio_path)
    for p in image_paths:
        if os.path.exists(p):
            os.remove(p)

if __name__ == "__main__":
    main()
