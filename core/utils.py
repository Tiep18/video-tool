"""
utils.py — Các hàm tiện ích dùng chung
"""

import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


# ── Text normalization ────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """Bỏ dấu, lowercase, bỏ ký tự đặc biệt — dùng để so khớp text."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_similarity(scene: str, whisper_text: str) -> float:
    """
    Recall-based: đo mức độ scene được thể hiện trong whisper_text.
    Lấy scene làm tham chiếu — không phạt whisper_text dài hơn scene.

    - Recall tập từ: bao nhiêu % từ của scene có trong whisper
    - Sequential recall: bao nhiêu từ scene xuất hiện đúng thứ tự trong whisper
    """
    scene_words  = normalize_text(scene).split()
    whisper_words = normalize_text(whisper_text).split()
    if not scene_words or not whisper_words:
        return 0.0

    # Recall tập từ (không xét thứ tự)
    scene_set   = set(scene_words)
    whisper_set = set(whisper_words)
    recall = len(scene_set & whisper_set) / len(scene_set)

    # Sequential recall: số từ scene khớp đúng thứ tự trong whisper
    matcher = SequenceMatcher(None, scene_words, whisper_words)
    matched_in_order = sum(block.size for block in matcher.get_matching_blocks())
    seq_recall = min(matched_in_order / len(scene_words), 1.0)

    # 30% recall tập từ + 70% recall theo thứ tự
    return 0.3 * recall + 0.7 * seq_recall


# ── Time formatting ───────────────────────────────────────────────────────────────────
def fmt_time(seconds: float) -> str:
    """56.92 → '00:56.92'"""
    m = int(seconds) // 60
    s = seconds % 60
    return f"{m:02d}:{s:05.2f}"


def parse_time(t: str) -> float:
    """'00:56.92' → 56.92  (ngược lại với fmt_time, dùng khi đọc bảng đã edit)."""
    try:
        parts = t.strip().split(":")
        return float(parts[0]) * 60 + float(parts[1])
    except Exception:
        return 0.0


def fmt_srt_time(seconds: float) -> str:
    """56.92 → '00:00:56,920'  (định dạng timestamp chuẩn SRT)."""
    h  = int(seconds) // 3600
    m  = (int(seconds) % 3600) // 60
    s  = int(seconds) % 60
    ms = round((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ── Image sorting ─────────────────────────────────────────────────────────────

def extract_prefix_number(filename: str) -> int:
    """
    Lấy số prefix từ tên file.
    '001_co_nhung_ngay.png' → 1
    '12_scene.jpg'          → 12
    'scene.png'             → 9999 (không có prefix → xếp cuối)
    """
    name = Path(filename).stem
    match = re.match(r"^(\d+)", name)
    return int(match.group(1)) if match else 9999


def sort_images(paths: list[str]) -> list[str]:
    """
    Sắp xếp danh sách đường dẫn ảnh theo prefix số trong tên file.
    Lọc bỏ các định dạng không được hỗ trợ.
    """
    valid = [p for p in paths if Path(p).suffix.lower() in SUPPORTED_IMAGE_EXTS]
    return sorted(valid, key=lambda p: extract_prefix_number(os.path.basename(p)))


def validate_inputs(
    image_paths: list[str],
    scenes: list[str],
) -> list[str]:
    """
    Kiểm tra tính hợp lệ của input trước khi xử lý.
    Trả về list các cảnh báo (rỗng = không có vấn đề gì).
    """
    warnings = []

    if not image_paths:
        warnings.append("❌ Không tìm thấy ảnh nào.")
        return warnings

    if not scenes:
        warnings.append("❌ Danh sách phân cảnh trống.")
        return warnings

    n_img = len(image_paths)
    n_sc  = len(scenes)

    if n_img < n_sc:
        warnings.append(
            f"⚠️ Số ảnh ({n_img}) ít hơn số phân cảnh ({n_sc}). "
            f"Ảnh cuối sẽ được lặp lại cho {n_sc - n_img} phân cảnh còn thiếu."
        )
    elif n_img > n_sc:
        warnings.append(
            f"⚠️ Số ảnh ({n_img}) nhiều hơn số phân cảnh ({n_sc}). "
            f"{n_img - n_sc} ảnh cuối sẽ bị bỏ qua."
        )

    missing = [p for p in image_paths if not os.path.isfile(p)]
    if missing:
        warnings.append(f"❌ Không tìm thấy {len(missing)} file ảnh: {missing[:3]}...")

    return warnings
