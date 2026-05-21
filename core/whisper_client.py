"""
whisper_client.py — Gọi OpenAI Whisper API và so khớp phân cảnh
"""

import openai
from core.utils import word_similarity, normalize_text, fmt_time


# ── Whisper transcription ─────────────────────────────────────────────────────

def transcribe(
    audio_path: str,
    api_key: str,
    language: str | None = "vi",
) -> tuple[list[dict], list[dict]]:
    """
    Gửi audio lên Whisper API.
    Trả về (segments, words):
    - segments : [{start, end, text}, ...]
    - words    : [{word, start, end}, ...]  ← word-level timestamps
    """
    client = openai.OpenAI(api_key=api_key)

    with open(audio_path, "rb") as f:
        kwargs = dict(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment", "word"],
        )
        if language:
            kwargs["language"] = language

        response = client.audio.transcriptions.create(**kwargs)

    segments = [
        {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
        for s in response.segments
    ]
    words = [
        {"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
        for w in (response.words or [])
    ]
    return segments, words


# ── Scene matching ────────────────────────────────────────────────────────────

def match_scenes(
    scenes: list[str],
    segments: list[dict],
    words: list[dict] | None = None,
) -> list[dict]:
    """
    So khớp từng phân cảnh với timeline audio.
    - Nếu có words (word-level): dùng căn chỉnh theo từng từ → chính xác hơn.
    - Nếu không: fallback sang segment-level matching.
    """
    if words:
        return _match_word_level(scenes, words)
    return _match_segment_level(scenes, segments)


# ══════════════════════════════════════════════════════════════════════════════
#  Word-level alignment  (primary)
# ══════════════════════════════════════════════════════════════════════════════

def _match_word_level(scenes: list[str], words: list[dict]) -> list[dict]:
    """
    Căn chỉnh phân cảnh theo word-level timestamps.

    Thuật toán:
    1. Với mỗi scene, tìm các từ "đặc trưng" không trùng với scene kề.
    2. Tìm từ đặc trưng đầu tiên trong timeline → start time.
    3. Tìm từ đặc trưng cuối cùng trong timeline → end time.
    4. Đảm bảo timestamp tăng dần.
    """
    norm = [
        {
            "norm": normalize_text(w["word"]),
            "start": w["start"],
            "end":   w["end"],
            "orig":  w["word"],
        }
        for w in words
    ]

    results  = []
    cursor   = 0   # min word index cho scene tiếp theo

    for i, scene in enumerate(scenes):
        scene_tokens  = normalize_text(scene).split()
        start_anchors = _unique_words(scenes, i, "start", n=4)

        # Từ của scene tiếp theo (dùng để tìm từ độc đáo của scene hiện tại)
        next_adj = set(normalize_text(scenes[i + 1]).split()) if i + 1 < len(scenes) else set()

        # Tìm điểm bắt đầu: từ anchor đầu tiên sau cursor
        start_idx = _first_match(start_anchors, norm, cursor, search_range=120)

        # Tìm điểm kết thúc bằng các từ CUỐI ĐỘC ĐÁO của scene
        end_idx = _find_end_by_last_unique(scene_tokens, norm, start_idx, next_adj)

        # Fallback nếu end không tìm được
        if end_idx <= start_idx:
            end_idx = min(start_idx + len(scene_tokens), len(norm) - 1)

        start_time = norm[start_idx]["start"]
        end_time   = norm[end_idx]["end"]

        # Whisper text trong khoảng thời gian đã tìm được
        whisper_text = " ".join(
            w["orig"] for w in norm
            if w["start"] >= start_time - 0.05 and w["end"] <= end_time + 0.1
        )

        score = word_similarity(scene, whisper_text) if whisper_text else 0.0

        results.append({
            "screen":       i + 1,
            "scene":        scene,
            "start":        round(start_time, 2),
            "end":          round(end_time,   2),
            "duration":     round(end_time - start_time, 2),
            "whisper_text": whisper_text,
            "match_pct":    round(score * 100),
        })

        # Cursor tiến đến start_idx (không phải end) để scene sau có thể
        # bắt đầu gần đó nếu nội dung chồng lấp.
        cursor = max(cursor + 1, start_idx)

    return results


def _unique_words(scenes: list[str], i: int, mode: str, n: int = 4) -> list[str]:
    """
    Lấy N từ của scene i không xuất hiện trong scene kề.
    - mode='start': loại trừ từ của scene i-1 (tìm anchor bắt đầu)
    - mode='end'  : loại trừ từ của scene i+1 (tìm anchor kết thúc)
    """
    scene_words = normalize_text(scenes[i]).split()

    if mode == "start":
        if i == 0:
            return scene_words[:n]
        adj = set(normalize_text(scenes[i - 1]).split())
    else:
        if i == len(scenes) - 1:
            return scene_words[-n:]
        adj = set(normalize_text(scenes[i + 1]).split())

    if mode == "start":
        unique = [w for w in scene_words if w not in adj]
        return unique[:n] if len(unique) >= 2 else scene_words[:n]
    else:
        unique = [w for w in reversed(scene_words) if w not in adj]
        unique = list(reversed(unique))
        return unique[-n:] if len(unique) >= 2 else scene_words[-n:]


def _first_match(
    anchors: list[str],
    norm: list[dict],
    cursor: int,
    search_range: int = 120,
) -> int:
    """Tìm index đầu tiên (từ cursor) của từ khớp với bất kỳ anchor nào."""
    anchor_set = set(anchors)
    for j in range(cursor, min(len(norm), cursor + search_range)):
        if norm[j]["norm"] in anchor_set:
            return j
    return cursor  # fallback: trả về cursor nếu không tìm thấy


def _find_end_by_last_unique(
    scene_tokens: list[str],
    norm: list[dict],
    start_idx: int,
    next_adj: set[str],
    n_anchors: int = 3,
) -> int:
    """
    Tìm điểm kết thúc scene bằng cách:
    1. Lấy N từ CUỐI của scene không trùng với scene sau (từ độc đáo).
    2. Tìm lần XUẤT HIỆN ĐẦU TIÊN của mỗi từ đó sau start_idx.
    3. Trả về vị trí XA NHẤT trong số các vị trí tìm được.

    Cách này tránh bị kéo dài bởi từ phổ biến ('không', 'một', 'có'...)
    vì chỉ tìm lần xuất hiện ĐẦU TIÊN, không phải lần cuối.
    """
    # N từ cuối độc đáo (không trùng scene sau), duyệt ngược
    unique_reversed = [w for w in reversed(scene_tokens) if w not in next_adj]
    last_unique = unique_reversed[:n_anchors]

    if not last_unique:
        # Fallback: dùng N từ cuối bất kỳ
        last_unique = list(reversed(scene_tokens[-n_anchors:]))

    # Giới hạn tìm kiếm: tối đa 3x độ dài scene từ start_idx
    max_scan = min(len(norm), start_idx + int(len(scene_tokens) * 3) + 10)

    max_idx = start_idx
    for target in last_unique:
        for j in range(start_idx, max_scan):
            if norm[j]["norm"] == target:
                max_idx = max(max_idx, j)
                break  # chỉ lấy lần xuất hiện đầu tiên

    return max_idx


# ══════════════════════════════════════════════════════════════════════════════
#  Segment-level fallback  (khi không có word timestamps)
# ══════════════════════════════════════════════════════════════════════════════

def _match_segment_level(scenes: list[str], segments: list[dict]) -> list[dict]:
    """Khớp phân cảnh theo segment-level khi không có word timestamps."""
    results  = []
    seg_cursor = 0
    prev_end   = 0.0

    for i, scene in enumerate(scenes):
        best  = _best_segment(scene, segments, seg_cursor)
        start = max(round(best["start"], 2), prev_end)
        end   = round(best["end"], 2)
        if end <= start:
            end = round(start + 0.5, 2)

        results.append({
            "screen":       i + 1,
            "scene":        scene,
            "start":        start,
            "end":          end,
            "duration":     round(end - start, 2),
            "whisper_text": best["text"],
            "match_pct":    round(best["score"] * 100),
        })
        prev_end   = end
        seg_cursor = min(len(segments) - 1, best["next_cursor"])

    _fix_duplicate_timestamps(results)
    return results


def _best_segment(scene: str, segments: list[dict], cursor: int) -> dict:
    """Tìm segment (hoặc ghép 2-3 segment) khớp nhất với scene."""
    search_from = cursor
    search_to   = min(len(segments), cursor + 12)
    best_score  = -1.0
    best_start = best_end = 0.0
    best_text  = ""
    best_j     = cursor

    for j in range(search_from, search_to):
        for k in range(j, min(j + 3, len(segments))):
            combined = " ".join(segments[m]["text"] for m in range(j, k + 1))
            s = word_similarity(scene, combined)
            if s > best_score:
                best_score = s
                best_start = segments[j]["start"]
                best_end   = segments[k]["end"]
                best_text  = combined
                best_j     = k

    return {
        "start":       round(best_start, 2),
        "end":         round(best_end,   2),
        "text":        best_text.strip(),
        "score":       best_score,
        "next_cursor": best_j + 1,
    }


def _fix_duplicate_timestamps(results: list[dict]) -> None:
    """Tách hai phân cảnh liên tiếp bị khớp cùng một segment."""
    for i in range(1, len(results)):
        prev, curr = results[i - 1], results[i]
        if prev["start"] != curr["start"] or prev["end"] != curr["end"]:
            continue
        w = normalize_text(prev["whisper_text"]).split()
        if not w:
            continue
        split_ratio = 0.5
        for word in reversed(normalize_text(prev["scene"]).split()):
            try:
                idx = len(w) - 1 - list(reversed(w)).index(word)
                split_ratio = max(0.2, min(0.8, (idx + 1) / len(w)))
                break
            except ValueError:
                continue
        split_t = round(prev["start"] + (prev["end"] - prev["start"]) * split_ratio, 2)
        prev["end"]      = split_t
        prev["duration"] = round(split_t - prev["start"], 2)
        curr["start"]    = split_t
        curr["duration"] = round(curr["end"] - split_t, 2)


# ── Helpers ───────────────────────────────────────────────────────────────────

def results_to_table(results: list[dict]) -> list[list]:
    """Chuyển kết quả thành rows cho Gradio Dataframe."""
    rows = []
    for r in results:
        quality = (
            "✅ Tốt"        if r["match_pct"] >= 60 else
            "⚠️ Trung bình" if r["match_pct"] >= 30 else
            "❌ Kém"
        )
        rows.append([
            r["screen"],
            fmt_time(r["start"]),
            fmt_time(r["end"]),
            f"{r['duration']}s",
            r["scene"],
            f"{r['match_pct']}%  {quality}",
        ])
    return rows
