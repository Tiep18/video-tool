"""
video_builder.py — Dựng video từ ảnh + audio với Ken Burns effect và transitions
"""

import os
import math
import numpy as np
from pathlib import Path
from PIL import Image
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout


# ── Constants ─────────────────────────────────────────────────────────────────

RESOLUTIONS = {
    "portrait_9_16":  (1080, 1920),
    "landscape_16_9": (1920, 1080),
    "square_1_1":     (1080, 1080),
}

FPS = 30
TRANSITION_DURATION = 0.5   # giây crossfade giữa các clip
FADE_IN_DURATION    = 0.4   # giây fade in đầu video
FADE_OUT_DURATION   = 0.6   # giây fade out cuối video


# ── Ken Burns helpers ─────────────────────────────────────────────────────────

def _ken_burns_frame(
    img_array: np.ndarray,
    out_w: int,
    out_h: int,
    progress: float,      # 0.0 → 1.0
    zoom_start: float,
    zoom_end: float,
    pan_x_start: float,   # -1.0 (left) .. +1.0 (right)
    pan_x_end: float,
    pan_y_start: float,   # -1.0 (top)  .. +1.0 (bottom)
    pan_y_end: float,
) -> np.ndarray:
    """
    Tạo 1 frame với hiệu ứng Ken Burns:
    - Zoom: nội suy giữa zoom_start và zoom_end
    - Pan:  nội suy vị trí crop theo trục X và Y
    """
    img_h, img_w = img_array.shape[:2]

    scale = zoom_start + (zoom_end - zoom_start) * progress

    # Kích thước vùng crop trên ảnh gốc (tỉ lệ khung output)
    crop_w = int(out_w / scale)
    crop_h = int(out_h / scale)

    # Clamp để không vượt kích thước ảnh
    crop_w = min(crop_w, img_w)
    crop_h = min(crop_h, img_h)

    # Phạm vi pan (pixel có thể dịch chuyển)
    max_x = img_w - crop_w
    max_y = img_h - crop_h

    pan_x = pan_x_start + (pan_x_end - pan_x_start) * progress
    pan_y = pan_y_start + (pan_y_end - pan_y_start) * progress

    # Chuyển [-1, 1] → [0, max_x]
    x0 = int((pan_x + 1) / 2 * max_x)
    y0 = int((pan_y + 1) / 2 * max_y)

    x0 = max(0, min(x0, max_x))
    y0 = max(0, min(y0, max_y))

    cropped = img_array[y0:y0 + crop_h, x0:x0 + crop_w]

    # Resize về kích thước output
    pil = Image.fromarray(cropped)
    pil = pil.resize((out_w, out_h), Image.LANCZOS)
    return np.array(pil)


def make_ken_burns_clip(
    image_path: str,
    duration: float,
    out_w: int,
    out_h: int,
    scene_index: int,
    intensity: float = 0.08,
) -> ImageClip:
    """
    Tạo video clip từ 1 ảnh với Ken Burns effect.

    scene_index: dùng để xen kẽ direction (chẵn zoom in, lẻ zoom out)
    intensity:   0.0 = không zoom, 0.15 = zoom nhiều
    """
    img = Image.open(image_path).convert("RGB")

    # Cover: ảnh luôn lấp đầy khung, không để lề trắng
    img = _cover_resize(img, out_w, out_h)
    img_array = np.array(img)

    # Xen kẽ direction theo scene_index
    if scene_index % 4 == 0:   # zoom in, pan right
        zoom_s, zoom_e = 1.0, 1.0 + intensity
        px_s, px_e = -0.3, 0.3
        py_s, py_e = 0.0, 0.0
    elif scene_index % 4 == 1:  # zoom out, pan left
        zoom_s, zoom_e = 1.0 + intensity, 1.0
        px_s, px_e = 0.3, -0.3
        py_s, py_e = 0.0, 0.0
    elif scene_index % 4 == 2:  # zoom in, pan up
        zoom_s, zoom_e = 1.0, 1.0 + intensity
        px_s, px_e = 0.0, 0.0
        py_s, py_e = 0.2, -0.2
    else:                        # zoom out, pan down
        zoom_s, zoom_e = 1.0 + intensity, 1.0
        px_s, px_e = 0.0, 0.0
        py_s, py_e = -0.2, 0.2

    total_frames = max(1, int(duration * FPS))

    def make_frame(t):
        progress = t / max(duration, 0.001)
        progress = max(0.0, min(1.0, progress))
        return _ken_burns_frame(
            img_array, out_w, out_h,
            progress,
            zoom_s, zoom_e,
            px_s, px_e,
            py_s, py_e,
        )

    clip = ImageClip(img_array, duration=duration)
    clip = clip.fl(lambda gf, t: make_frame(t), apply_to=["mask"])
    clip = clip.fl_time(lambda t: t)

    # Rebuild via make_frame direcly
    clip = ImageClip(make_frame(0), duration=duration)
    clip = clip.fl(lambda gf, t: make_frame(t))
    clip = clip.set_fps(FPS)

    return clip


def _cover_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Resize ảnh kiểu 'cover': scale để lấp đầy khung, crop phần thừa ở giữa.
    """
    img_w, img_h = img.size
    scale = max(target_w / img_w, target_h / img_h)
    new_w = int(math.ceil(img_w * scale))
    new_h = int(math.ceil(img_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    img  = img.crop((left, top, left + target_w, top + target_h))
    return img


# ── Crossfade transition ──────────────────────────────────────────────────────

def crossfade_clips(clips: list, transition_dur: float) -> list:
    """
    Thêm crossfade giữa các clip bằng cách set start time overlap.
    Dùng CompositeVideoClip ở bước ghép cuối.
    """
    if not clips:
        return []
    if len(clips) == 1:
        return clips

    result = [clips[0]]
    t = clips[0].duration

    for i, clip in enumerate(clips[1:], start=1):
        clip = clip.set_start(t - transition_dur)
        clip = clip.crossfadein(transition_dur)
        result.append(clip)
        t += clip.duration - transition_dur

    return result


# ── Main build function ───────────────────────────────────────────────────────

def build_video(
    matched_scenes: list[dict],
    image_paths: list[str],
    audio_path: str,
    output_path: str,
    resolution: str = "portrait_9_16",
    ken_burns_intensity: float = 0.08,
    transition_dur: float = TRANSITION_DURATION,
    progress_callback=None,
) -> str:
    """
    Dựng video hoàn chỉnh từ danh sách phân cảnh đã match.

    matched_scenes: output của whisper_client.match_scenes()
    image_paths:    list ảnh đã sort theo thứ tự phân cảnh
    audio_path:     đường dẫn file audio gốc
    output_path:    đường dẫn file .mp4 output
    resolution:     'portrait_9_16' | 'landscape_16_9' | 'square_1_1'
    ken_burns_intensity: 0.0–0.15
    transition_dur: giây crossfade giữa các clip
    progress_callback: fn(step: str, pct: int) để cập nhật UI

    Trả về đường dẫn file output.
    """
    out_w, out_h = RESOLUTIONS.get(resolution, RESOLUTIONS["portrait_9_16"])
    n = len(matched_scenes)

    def progress(step, pct):
        if progress_callback:
            progress_callback(step, pct)

    progress("Đang tạo clip cho từng phân cảnh...", 5)

    clips = []
    for i, scene in enumerate(matched_scenes):
        img_path = image_paths[min(i, len(image_paths) - 1)]
        duration = max(scene["duration"], 0.5)  # tối thiểu 0.5s

        clip = make_ken_burns_clip(
            image_path=img_path,
            duration=duration,
            out_w=out_w,
            out_h=out_h,
            scene_index=i,
            intensity=ken_burns_intensity,
        )
        clips.append(clip)
        pct = 5 + int((i + 1) / n * 50)
        progress(f"Clip {i+1}/{n}: {scene['scene'][:30]}...", pct)

    progress("Đang ghép transition crossfade...", 57)
    clips_with_fx = crossfade_clips(clips, transition_dur)

    progress("Đang tổng hợp video...", 62)
    total_duration = sum(c.duration for c in clips) - transition_dur * (len(clips) - 1)
    video = CompositeVideoClip(clips_with_fx, size=(out_w, out_h))
    video = video.set_duration(total_duration)

    # Fade in/out toàn bộ video
    video = fadein(video, FADE_IN_DURATION)
    video = fadeout(video, FADE_OUT_DURATION)

    progress("Đang ghép audio...", 70)
    audio = AudioFileClip(audio_path)
    # Cắt audio nếu dài hơn video
    if audio.duration > video.duration:
        audio = audio.subclip(0, video.duration)
    video = video.set_audio(audio)

    progress("Đang render và export MP4 (có thể mất vài phút)...", 75)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        verbose=False,
        logger=None,
    )

    video.close()
    audio.close()

    progress("Hoàn tất!", 100)
    return output_path
