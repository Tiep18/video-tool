"""
video_builder.py — Dựng video từ ảnh + audio với Camera Motion effects và transitions.

Thuật toán: Timeline-based absolute positioning
  - Mỗi clip được đặt tại đúng vị trí timeline theo scene["start"]
  - Clip duration = scene["duration"] + gap sau scene → ảnh giữ nguyên trong lặng
  - Crossfade adaptive: nằm trong vùng lặng, duration theo gap size
  - Camera Motion: 10 preset chuyển động máy ảnh, chọn ngẫu nhiên có seed, không lặp liền kề
  - Vignette: overlay tối viền, cố định
"""

import os
import math
import random
import numpy as np
from PIL import Image
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
)
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

RESOLUTIONS = {
    "portrait_9_16":  (1080, 1920),
    "landscape_16_9": (1920, 1080),
    "square_1_1":     (1080, 1080),
}

FPS               = 25
FADE_IN_DURATION  = 0.5    # giây fade in đầu video
FADE_OUT_DURATION = 0.8    # giây fade out cuối video
MAX_CROSSFADE     = 1.5    # crossfade tối đa (giây)
MIN_CROSSFADE     = 0.15   # crossfade tối thiểu (giây)
VIGNETTE_STRENGTH = 0.55   # 0 = không vignette, 1 = rất đậm

# ── Performance (benchmark trên CPU, 1080×1920) ─────────────────────────────
# BILINEAR upscale từ source nhỏ: ~13ms/frame  (← chọn này)
# LANCZOS upscale từ source nhỏ: ~25ms/frame
# BILINEAR downscale từ source 1.5×: ~23ms/frame  (lớn hơn → chậm hơn)
# Vignette float32 mul: ~40ms/frame
# Vignette uint16 >>8:  ~20ms/frame  (← chọn này)


# ─────────────────────────────────────────────────────────────────────────────
# Math helpers
# ─────────────────────────────────────────────────────────────────────────────

def _smoothstep(x: float) -> float:
    """Easing: smooth acceleration & deceleration (0→1). Dùng cho pan/tilt."""
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _ease_out(x: float) -> float:
    """Easing: nhanh lúc đầu, chậm dần (0→1). Dùng cho zoom out."""
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 2


def _ease_in(x: float) -> float:
    """Easing: chậm lúc đầu, nhanh dần (0→1). Dùng cho zoom in."""
    x = max(0.0, min(1.0, x))
    return x * x


def _ease_in_out_cubic(x: float) -> float:
    """Easing cubic mượt mà hơn smoothstep. Dùng cho crane/dolly."""
    x = max(0.0, min(1.0, x))
    if x < 0.5:
        return 4 * x * x * x
    return 1 - (-2 * x + 2) ** 3 / 2


# ─────────────────────────────────────────────────────────────────────────────
# Vignette
# ─────────────────────────────────────────────────────────────────────────────

def _make_vignette(w: int, h: int, strength: float = VIGNETTE_STRENGTH) -> np.ndarray:
    """
    Tạo mask vignette dưới dạng uint8 (H, W, 3).
    Lưu dạng uint8 [0-255] để dùng integer multiply thay float32 → nhanh hơn ~2×.
    """
    X = np.linspace(-1.0, 1.0, w)
    Y = np.linspace(-1.0, 1.0, h)
    Xg, Yg = np.meshgrid(X, Y)
    dist = np.sqrt(Xg ** 2 + (Yg * 0.85) ** 2)
    sigma = 1.0 - strength * 0.5
    mask = np.exp(-(dist ** 2) / (2 * sigma ** 2))
    mask = np.clip(mask, 0.0, 1.0)
    # uint8 [0-255], broadcast thành (H, W, 1) → numpy tự broadcast với frame (H, W, 3)
    return (mask[:, :, np.newaxis] * 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
# Cover resize
# ─────────────────────────────────────────────────────────────────────────────

def _cover_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize ảnh kiểu cover: lấp đầy khung, crop phần thừa ở giữa."""
    img_w, img_h = img.size
    scale = max(target_w / img_w, target_h / img_h)
    new_w = int(math.ceil(img_w * scale))
    new_h = int(math.ceil(img_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


# ─────────────────────────────────────────────────────────────────────────────
# Camera Motion Presets — 10 kiểu chuyển động máy ảnh
# ─────────────────────────────────────────────────────────────────────────────
#
# Mỗi preset là dict với các trường:
#   name        : tên hiệu ứng (để debug/log)
#   zoom_s      : scale đầu (hệ số nhân với intensity, 1.0 = không zoom)
#   zoom_e      : scale cuối
#   px_s, px_e  : pan ngang đầu/cuối  [-1 = trái, +1 = phải]
#   py_s, py_e  : pan dọc  đầu/cuối   [-1 = trên, +1 = dưới]
#   easing      : hàm easing áp dụng cho progress (string key)
#
# Quy ước zoom: zoom_s/zoom_e là OFFSET so với 1.0
#   scale_thực = 1.0 + offset * intensity
#   → offset = 0.0 : không zoom thêm (scale=1.0 khi intensity=0.08 → scale=1.0)
#   → offset = 1.0 : zoom đủ intensity (scale=1.08 khi intensity=0.08)
#   → offset = 2.0 : zoom gấp đôi intensity (scale=1.16 khi intensity=0.08)
#
_CAMERA_PRESETS = [
    # 0 — Zoom In: tiến thẳng vào trung tâm (easing ease-in: tăng tốc)
    {
        "name": "Zoom In",
        "zoom_s": 0.0, "zoom_e": 2.0,
        "px_s": 0.0,  "px_e": 0.0,
        "py_s": 0.0,  "py_e": 0.0,
        "easing": "ease_in",
    },
    # 1 — Zoom Out: lùi ra, reveal bối cảnh (easing ease-out: giảm tốc)
    {
        "name": "Zoom Out",
        "zoom_s": 2.0, "zoom_e": 0.0,
        "px_s": 0.0,  "px_e": 0.0,
        "py_s": 0.0,  "py_e": 0.0,
        "easing": "ease_out",
    },
    # 2 — Pan Left: lia máy sang trái (scale cố định nhẹ để có đủ room)
    {
        "name": "Pan Left",
        "zoom_s": 0.5, "zoom_e": 0.5,
        "px_s": 0.6,  "px_e": -0.6,
        "py_s": 0.0,  "py_e": 0.0,
        "easing": "smoothstep",
    },
    # 3 — Pan Right: lia máy sang phải
    {
        "name": "Pan Right",
        "zoom_s": 0.5, "zoom_e": 0.5,
        "px_s": -0.6, "px_e": 0.6,
        "py_s": 0.0,  "py_e": 0.0,
        "easing": "smoothstep",
    },
    # 4 — Tilt Up: ngẩng máy lên (pan dọc từ dưới → trên)
    {
        "name": "Tilt Up",
        "zoom_s": 0.5, "zoom_e": 0.5,
        "px_s": 0.0,  "px_e": 0.0,
        "py_s": 0.6,  "py_e": -0.6,
        "easing": "smoothstep",
    },
    # 5 — Tilt Down: cúi máy xuống (pan dọc từ trên → dưới)
    {
        "name": "Tilt Down",
        "zoom_s": 0.5, "zoom_e": 0.5,
        "px_s": 0.0,  "px_e": 0.0,
        "py_s": -0.6, "py_e": 0.6,
        "easing": "smoothstep",
    },
    # 6 — Push In Left: tiến vào chủ thể + lia nhẹ sang trái
    {
        "name": "Push In Left",
        "zoom_s": 0.0, "zoom_e": 1.5,
        "px_s": 0.3,  "px_e": -0.3,
        "py_s": 0.0,  "py_e": 0.0,
        "easing": "ease_in",
    },
    # 7 — Pull Out Right: lùi ra + lia nhẹ sang phải
    {
        "name": "Pull Out Right",
        "zoom_s": 1.5, "zoom_e": 0.0,
        "px_s": -0.3, "px_e": 0.3,
        "py_s": 0.0,  "py_e": 0.0,
        "easing": "ease_out",
    },
    # 8 — Dolly Zoom: zoom vào góc trên-trái (tạo cảm giác focus vào chi tiết)
    {
        "name": "Dolly Zoom",
        "zoom_s": 0.0, "zoom_e": 2.5,
        "px_s": 0.4,  "px_e": -0.2,
        "py_s": 0.4,  "py_e": -0.2,
        "easing": "ease_in_out_cubic",
    },
    # 9 — Crane Up: nâng máy từ dưới lên + zoom nhẹ ra (như crane shot)
    {
        "name": "Crane Up",
        "zoom_s": 1.0, "zoom_e": 0.2,
        "px_s": 0.0,  "px_e": 0.0,
        "py_s": 0.7,  "py_e": -0.5,
        "easing": "ease_in_out_cubic",
    },
]

_EASING_FNS = {
    "smoothstep":      _smoothstep,
    "ease_in":         _ease_in,
    "ease_out":        _ease_out,
    "ease_in_out_cubic": _ease_in_out_cubic,
}


def _pick_preset(scene_index: int, prev_preset_idx: int = -1) -> tuple[int, dict]:
    """
    Chọn ngẫu nhiên camera preset cho scene, không trùng preset liền trước.
    Dùng seed = scene_index để tái hiện kết quả nhất quán mỗi lần render.
    """
    rng = random.Random(scene_index * 31 + 7)   # seed riêng mỗi scene
    n = len(_CAMERA_PRESETS)
    candidates = [i for i in range(n) if i != prev_preset_idx]
    chosen_idx = rng.choice(candidates)
    return chosen_idx, _CAMERA_PRESETS[chosen_idx]


# ─────────────────────────────────────────────────────────────────────────────
# Core frame renderer
# ─────────────────────────────────────────────────────────────────────────────

def _camera_motion_frame(
    img_pil: Image.Image,
    out_w: int, out_h: int,
    progress: float,          # 0.0 → 1.0 (raw, chưa eased)
    preset: dict,             # camera preset dict
    intensity: float,
) -> np.ndarray:
    """
    Render một frame với camera motion theo preset đã chọn.
    Sử dụng PIL crop và resize trực tiếp để tránh overhead tạo Image từ array mỗi frame.
    """
    img_w, img_h = img_pil.size

    easing_fn = _EASING_FNS.get(preset["easing"], _smoothstep)
    p = easing_fn(progress)

    zoom_s = 1.0 + preset["zoom_s"] * intensity
    zoom_e = 1.0 + preset["zoom_e"] * intensity
    scale  = zoom_s + (zoom_e - zoom_s) * p
    scale  = max(scale, 1.0)

    # Kích thước vùng crop từ ảnh gốc (out_w × out_h)
    crop_w = int(out_w / scale)
    crop_h = int(out_h / scale)
    crop_w = min(crop_w, img_w)
    crop_h = min(crop_h, img_h)

    max_x = img_w - crop_w
    max_y = img_h - crop_h

    pan_x = preset["px_s"] + (preset["px_e"] - preset["px_s"]) * p
    pan_y = preset["py_s"] + (preset["py_e"] - preset["py_s"]) * p

    x0 = int((pan_x + 1) / 2 * max_x)
    y0 = int((pan_y + 1) / 2 * max_y)
    x0 = max(0, min(x0, max_x))
    y0 = max(0, min(y0, max_y))

    # PIL lazy crop
    cropped = img_pil.crop((x0, y0, x0 + crop_w, y0 + crop_h))
    
    # TỐI ƯU: Nếu kích thước vùng crop trùng với output size (scale = 1.0), không cần resize
    if crop_w == out_w and crop_h == out_h:
        return np.array(cropped)

    resized = cropped.resize((out_w, out_h), Image.BILINEAR)
    return np.array(resized)


# ─────────────────────────────────────────────────────────────────────────────
# Clip builder
# ─────────────────────────────────────────────────────────────────────────────

def make_camera_motion_clip(
    image_path: str,
    clip_duration: float,    # thời lượng thực tế trên timeline (bao gồm gap và chuyển cảnh)
    scene_duration: float,   # thời lượng nội dung scene (không có gap)
    out_w: int, out_h: int,
    scene_index: int,
    prev_preset_idx: int = -1,
    intensity: float = 0.08,
    vignette: np.ndarray = None,
) -> tuple["ImageClip", int]:
    """
    Tạo clip ảnh với Camera Motion effect.

    - Camera motion chạy theo `scene_duration` (chỉ phần có lời)
      rồi giữ nguyên frame cuối trong phần gap và overlap chuyển cảnh.
    - Preset được chọn ngẫu nhiên, không trùng scene liền trước.

    Returns:
        (clip, chosen_preset_idx)  — trả preset_idx để scene sau dùng làm prev
    """
    img = Image.open(image_path).convert("RGB")
    # ─ Bước 1: Pre-resize về output size với LANCZOS (1 lần, chất lượng cao)
    img = _cover_resize(img, out_w, out_h)
    img_array = np.array(img, dtype=np.uint8)

    # ─ Bước 2: Pre-bake vignette vào ảnh (1 lần) -> convert sang PIL
    if vignette is None:
        vignette = np.full((out_h, out_w, 1), 255, dtype=np.uint8)
    img_array = ((img_array.astype(np.uint16) * vignette) >> 8).astype(np.uint8)
    img_pil = Image.fromarray(img_array)

    # Chọn preset
    preset_idx, preset = _pick_preset(scene_index, prev_preset_idx)
    preset = dict(preset)  # Sao chép để tránh ghi đè cấu hình gốc toàn cục

    # TỐI ƯU: Nếu preset có tỉ lệ zoom không đổi (ví dụ Pan Left/Right, Tilt Up/Down),
    # ta có thể pre-scale ảnh ngay từ đầu, sau đó chỉ cần crop ở mỗi khung hình mà không cần resize.
    if preset["zoom_s"] == preset["zoom_e"]:
        scale = 1.0 + preset["zoom_s"] * intensity
        scale = max(scale, 1.0)
        target_scale_w = int(round(out_w * scale))
        target_scale_h = int(round(out_h * scale))
        if target_scale_w != out_w or target_scale_h != out_h:
            img_pil = img_pil.resize((target_scale_w, target_scale_h), Image.LANCZOS)
        # Thiết lập lại mức zoom bằng 0 để hàm render frame bỏ qua bước resize tiếp theo
        preset["zoom_s"] = 0.0
        preset["zoom_e"] = 0.0

    # Cache cho khung hình trùng lặp
    last_p = -1.0
    last_frame = None

    def make_frame(t: float) -> np.ndarray:
        nonlocal last_p, last_frame
        motion_t = min(t, scene_duration)
        progress = motion_t / max(scene_duration, 0.001)
        
        # Nếu progress trùng với lần gọi trước đó, trả về luôn để bỏ qua tính toán
        if last_frame is not None and abs(progress - last_p) < 0.0001:
            return last_frame

        frame = _camera_motion_frame(
            img_pil, out_w, out_h,
            progress,
            preset,
            intensity,
        )
        last_p = progress
        last_frame = frame
        return frame

    clip = ImageClip(make_frame(0), duration=clip_duration)
    clip = clip.fl(lambda gf, t: make_frame(t))
    clip = clip.set_fps(FPS)
    return clip, preset_idx


# ─────────────────────────────────────────────────────────────────────────────
# Build video — timeline-based
# ─────────────────────────────────────────────────────────────────────────────

def build_video(
    matched_scenes: list[dict],
    image_paths: list[str],
    audio_path: str,
    output_path: str,
    resolution: str = "portrait_9_16",
    ken_burns_intensity: float = 0.08,
    transition_dur: float = 0.6,
    progress_callback=None,
) -> str:
    """
    Dựng video theo thuật toán timeline-based với gối chồng (overlap) phân cảnh:
      1. Đọc audio_duration làm mốc tổng thời lượng
      2. Tính toán trước transition fade duration cho từng chuyển tiếp
      3. Mỗi clip_i kéo dài từ scene_i.start đến [scene_i+1.start + fade_durs[i+1]]
      4. Clip sau đè lên đuôi clip trước bằng crossfadein tạo hiệu ứng chuyển tiếp hoàn hảo
      5. Ghi file mp4 với FFMPEG preset ultrafast và bitrate tối ưu 3500k để render cực nhanh
    """
    out_w, out_h = RESOLUTIONS.get(resolution, RESOLUTIONS["portrait_9_16"])
    n = len(matched_scenes)
    scenes = list(matched_scenes)  # copy để tránh mutate

    def _prog(step: str, pct: int):
        if progress_callback:
            progress_callback(step, pct)

    # ── 1. Đọc audio ──────────────────────────────────────────────────────────
    _prog("Đang đọc file audio...", 2)
    audio        = AudioFileClip(audio_path)
    audio_dur    = audio.duration

    # ── 2. Chuẩn bị vignette uint8 (tạo 1 lần, dùng lại) ───────────────────
    _prog("Đang tạo vignette...", 4)
    vignette = _make_vignette(out_w, out_h)   # uint8 (H, W, 3)

    # ── 3. Tính toán transition fade duration cho từng phân cảnh ────────────────
    # fade_durs[i] là thời gian crossfade từ scene i-1 sang scene i.
    # fade_durs[0] = 0.0 (không có transition trước nó)
    _prog("Đang chuẩn bị timeline và transition...", 5)
    fade_durs = [0.0] * n
    for i in range(1, n):
        prev_end = scenes[i - 1]["end"]
        clip_start = scenes[i]["start"]
        gap = clip_start - prev_end
        if gap <= 0:
            fade_dur = MIN_CROSSFADE
        elif gap < transition_dur:
            fade_dur = max(gap * 0.9, MIN_CROSSFADE)
        else:
            fade_dur = min(transition_dur, MAX_CROSSFADE)
        fade_durs[i] = round(fade_dur, 3)

    # ── 4. Tính clip boundary cho từng scene ─────────────────────────────────
    # clip_i bắt đầu từ scenes[i]["start"]
    # clip_i kết thúc tại [scenes[i+1]["start"] + fade_durs[i+1]] để tạo phần gối chồng
    # clip cuối cùng kết thúc tại audio_dur
    boundaries = []
    for i in range(n):
        clip_start = scenes[i]["start"]
        if i < n - 1:
            clip_end = scenes[i + 1]["start"] + fade_durs[i + 1]
        else:
            clip_end = audio_dur
        boundaries.append((clip_start, clip_end))

    # ── 5. Tạo từng clip với Camera Motion ───────────────────────────────────
    clips = []
    prev_preset_idx = -1

    for i, scene in enumerate(scenes):
        img_path        = image_paths[min(i, len(image_paths) - 1)]
        clip_start, clip_end = boundaries[i]
        clip_duration   = max(clip_end - clip_start, 0.2)
        scene_duration  = max(scene["duration"], 0.2)

        clip, prev_preset_idx = make_camera_motion_clip(
            image_path=img_path,
            clip_duration=clip_duration,
            scene_duration=scene_duration,
            out_w=out_w,
            out_h=out_h,
            scene_index=i,
            prev_preset_idx=prev_preset_idx,
            intensity=ken_burns_intensity,
            vignette=vignette,
        )

        # Đặt vị trí tuyệt đối trên timeline
        clip = clip.set_start(clip_start)

        # Áp dụng crossfadein vào đầu clip sau (nó sẽ đè mượt mà lên clip trước)
        if i > 0:
            fade_dur = min(fade_durs[i], clip_duration - 0.05)
            fade_dur = max(fade_dur, 0.0)
            if fade_dur > 0:
                clip = clip.crossfadein(round(fade_dur, 3))

        clips.append(clip)

        preset_name = _CAMERA_PRESETS[prev_preset_idx]["name"]
        pct = 5 + int((i + 1) / n * 55)
        _prog(f"[{i+1}/{n}] [{preset_name}] '{scene['scene'][:28]}...'", pct)

    # ── 6. Composite & set duration ──────────────────────────────────────────
    _prog("Đang tổng hợp video...", 62)
    video = CompositeVideoClip(clips, size=(out_w, out_h))
    video = video.set_duration(audio_dur)

    # ── 7. Fade in / out toàn video ──────────────────────────────────────────
    video = fadein(video,  FADE_IN_DURATION)
    video = fadeout(video, FADE_OUT_DURATION)

    # ── 8. Ghép audio ────────────────────────────────────────────────────────
    _prog("Đang ghép audio...", 70)
    if audio.duration > video.duration:
        audio = audio.subclip(0, video.duration)
    video = video.set_audio(audio)

    # ── 9. Export ─────────────────────────────────────────────────────────────
    _prog("Đang render MP4 (sử dụng tối ưu hóa tốc độ)...", 75)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",   # ultrafast nhanh gấp 2-3x so với fast/medium
        bitrate="3500k",     # bitrate tối ưu 3500k giảm đáng kể thời gian nén ảnh
        threads=0,           # tự động phát hiện số nhân CPU
        verbose=False,
        logger=None,
    )

    video.close()
    audio.close()

    _prog("Hoàn tất!", 100)
    return output_path
