"""
app.py — Gradio UI cho Audio Timestamp + Video Generator Tool
"""

import os
import json
import tempfile
import threading
from pathlib import Path

# matplotlib removed to optimize UI/UX space and performance

import gradio as gr

from core.utils import sort_images, validate_inputs, fmt_time, parse_time, fmt_srt_time
from core.whisper_client import transcribe, match_scenes, results_to_table
from core.video_builder import build_video, RESOLUTIONS


# ── State ─────────────────────────────────────────────────────────────────────

_matched_scenes: list[dict] = []
_sorted_images:  list[str]  = []
_progress_log:   list[str]  = []

CACHE_FILE = "cache_state.json"


def _save_cache(api_key, audio_path, scenes_text, language):
    global _matched_scenes
    try:
        data = {
            "api_key": api_key,
            "audio_path": audio_path,
            "scenes_text": scenes_text,
            "language": language,
            "matched_scenes": _matched_scenes
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi lưu cache: {e}")


def _clear_cache():
    global _matched_scenes
    _matched_scenes = []
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
        except Exception:
            pass
    return (
        "",          # api_key
        None,        # audio_input
        "",          # scenes_input
        "Tiếng Việt", # language
        "🗑️ Đã xóa cache thành công.", # update_log
        None,        # timestamp_table
    )


def load_cached_state():
    global _matched_scenes
    if not os.path.exists(CACHE_FILE):
        return "", None, "", "Tiếng Việt", None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        _matched_scenes = data.get("matched_scenes", [])
        api_key = data.get("api_key", "")
        audio_path = data.get("audio_path", None)
        if audio_path and not os.path.exists(audio_path):
            audio_path = None
        
        scenes_text = data.get("scenes_text", "")
        language = data.get("language", "Tiếng Việt")
        
        table = results_to_table(_matched_scenes) if _matched_scenes else None
        
        return api_key, audio_path, scenes_text, language, table
    except Exception as e:
        print(f"Lỗi load cache: {e}")
        return "", None, "", "Tiếng Việt", None


# _build_timeline_fig was removed since the timeline plot is no longer needed.


# ── Step 1: Phân tích timestamp ───────────────────────────────────────────────

def analyze_timestamps(api_key, audio_path, scenes_text, language):
    global _matched_scenes, _sorted_images

    if not api_key.strip():
        return None, "❌ Vui lòng nhập OpenAI API Key.", None
    if not audio_path:
        return None, "❌ Vui lòng upload file audio.", None

    scenes = [s.strip() for s in scenes_text.strip().splitlines() if s.strip()]
    if not scenes:
        return None, "❌ Vui lòng nhập danh sách phân cảnh.", None

    lang_map  = {"Tiếng Việt": "vi", "English": "en", "Tự động": None}
    lang_code = lang_map.get(language, "vi")

    try:
        log = "→ Gửi audio lên Whisper API...\n"
        segments, words = transcribe(audio_path, api_key.strip(), lang_code)
        log += f"✓ Whisper: {len(segments)} segments, {len(words)} từ\n"
        log += f"→ So khớp {len(scenes)} phân cảnh...\n"

        _matched_scenes = match_scenes(scenes, segments, words)
        good = sum(1 for m in _matched_scenes if m["match_pct"] >= 60)
        log += f"✓ Xong! {good}/{len(_matched_scenes)} phân cảnh khớp tốt (≥60%)\n"

        # Ghi cache cục bộ
        _save_cache(api_key, audio_path, scenes_text, language)

        table = results_to_table(_matched_scenes)
        return table, log

    except Exception as e:
        return None, f"❌ Lỗi: {str(e)}"


# ── Sync timestamp từ bảng đã edit ───────────────────────────────────────────

def sync_timestamps(table, api_key, audio_path, scenes_text, language):
    """Đọc bảng đã edit, cập nhật _matched_scenes, vẽ lại timeline và lưu cache."""
    global _matched_scenes

    if not _matched_scenes or table is None:
        return "❌ Chưa có dữ liệu phân tích.", gr.update(), gr.update()

    try:
        rows    = table.values.tolist() if hasattr(table, "values") else table
        updated = 0

        for i, row in enumerate(rows):
            if i >= len(_matched_scenes):
                break
            start = parse_time(str(row[1]))   # cột "Bắt đầu"
            end   = parse_time(str(row[2]))   # cột "Kết thúc"
            if (abs(start - _matched_scenes[i]["start"]) > 0.01
                    or abs(end - _matched_scenes[i]["end"]) > 0.01):
                _matched_scenes[i]["start"]    = round(start, 2)
                _matched_scenes[i]["end"]      = round(end,   2)
                _matched_scenes[i]["duration"] = round(end - start, 2)
                updated += 1

        # Ghi cache sau khi sync
        _save_cache(api_key, audio_path, scenes_text, language)

        new_table = results_to_table(_matched_scenes)
        return f"✅ Đã cập nhật {updated} dòng.", new_table

    except Exception as e:
        return f"❌ Lỗi: {e}", gr.update()


# ── Step 2: Render video ──────────────────────────────────────────────────────

def render_video(
    audio_path,
    image_files,
    resolution_label,
    intensity,
    transition_dur,
    progress=gr.Progress(track_tqdm=True),
):
    """Generator function — yield (video_path, log_text) từng bước để cập nhật UI real-time."""
    global _matched_scenes

    if not _matched_scenes:
        yield None, "❌ Chưa có dữ liệu timestamp. Hãy chạy 'Phân tích' trước."
        return
    if not audio_path:
        yield None, "❌ Thiếu file audio."
        return
    if not image_files:
        yield None, "❌ Chưa upload ảnh."
        return

    image_paths = sort_images([f.name for f in image_files])
    if not image_paths:
        yield None, "❌ Không tìm thấy ảnh hợp lệ (png/jpg/webp)."
        return

    warnings = validate_inputs(image_paths, _matched_scenes)
    warn_str = "\n".join(warnings) + "\n" if warnings else ""

    res_map = {
        "Dọc 9:16 (TikTok/Reels)": "portrait_9_16",
        "Ngang 16:9 (YouTube)":     "landscape_16_9",
        "Vuông 1:1 (Instagram)":    "square_1_1",
    }
    resolution  = res_map.get(resolution_label, "portrait_9_16")
    output_path = os.path.join(tempfile.gettempdir(), "video_tool_output.mp4")
    log_lines   = [warn_str + "→ Bắt đầu render video..."]

    # Dùng threading để build_video chạy song song với việc yield log
    import queue as _queue
    _q = _queue.Queue()
    _result = [None]
    _error  = [None]

    def on_progress(step, pct):
        _q.put((step, pct))
        progress(pct / 100, desc=step)

    def _worker():
        try:
            _result[0] = build_video(
                matched_scenes=_matched_scenes,
                image_paths=image_paths,
                audio_path=audio_path,
                output_path=output_path,
                resolution=resolution,
                ken_burns_intensity=float(intensity),
                transition_dur=float(transition_dur),
                progress_callback=on_progress,
            )
        except Exception as e:
            _error[0] = str(e)
        finally:
            _q.put(None)  # sentinel

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    # Stream log từng bước về UI
    while True:
        item = _q.get()
        if item is None:
            break
        step, pct = item
        log_lines.append(f"[{pct:3d}%] {step}")
        yield None, "\n".join(log_lines)

    t.join()

    if _error[0]:
        log_lines.append(f"❌ Lỗi render: {_error[0]}")
        yield None, "\n".join(log_lines)
        return

    result = _result[0]
    size_mb = os.path.getsize(result) / 1024 / 1024
    log_lines.append(f"✅ Hoàn tất! File: {result} ({size_mb:.1f} MB)")
    yield result, "\n".join(log_lines)


# ── Export helpers ────────────────────────────────────────────────────────────

def export_json():
    if not _matched_scenes:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
    json.dump(_matched_scenes, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    return tmp.name


def export_csv():
    if not _matched_scenes:
        return None
    lines = ["Screen,Start,End,Duration,Text,Match%"]
    for m in _matched_scenes:
        text = m["scene"].replace('"', '""')
        lines.append(
            f'{m["screen"]},{m["start"]},{m["end"]},{m["duration"]},"{text}",{m["match_pct"]}'
        )
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8")
    tmp.write("\n".join(lines))
    tmp.close()
    return tmp.name


def export_srt():
    """Xuất file .srt chuẩn có thể import vào TikTok, YouTube, Premiere..."""
    if not _matched_scenes:
        return None
    lines = []
    for m in _matched_scenes:
        lines.append(str(m["screen"]))
        lines.append(f"{fmt_srt_time(m['start'])} --> {fmt_srt_time(m['end'])}")
        lines.append(m["scene"])
        lines.append("")          # dòng trống giữa các cue
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".srt", mode="w", encoding="utf-8")
    tmp.write("\n".join(lines))
    tmp.close()
    return tmp.name


# ── UI ────────────────────────────────────────────────────────────────────────

DESCRIPTION = """
# 🎬 Auto Video Generator
**Tự động tạo video từ ảnh phân cảnh + audio voiceover sử dụng OpenAI Whisper**
"""

with gr.Blocks(title="Auto Video Generator", theme=gr.themes.Soft()) as demo:
    gr.Markdown(DESCRIPTION)

    with gr.Tabs():
        with gr.Tab("⚙️ Bước 1: Phân tích & Biên tập Timestamp"):
            with gr.Row():
                with gr.Column(scale=4):
                    gr.Markdown("### 📥 Cấu hình đầu vào")
                    api_key = gr.Textbox(
                        label="🔑 OpenAI API Key",
                        placeholder="sk-...",
                        type="password",
                        info="Chỉ lưu trữ trong phiên làm việc hiện tại.",
                    )
                    audio_input = gr.Audio(
                        label="🎵 File Audio Voiceover",
                        type="filepath",
                        sources=["upload"],
                    )
                    language = gr.Radio(
                        label="🌐 Ngôn ngữ nhận dạng giọng nói",
                        choices=["Tiếng Việt", "English", "Tự động"],
                        value="Tiếng Việt",
                    )
                    scenes_input = gr.Textbox(
                        label="📋 Danh sách phân cảnh (mỗi dòng 1 câu)",
                        placeholder="Nhập nội dung các phân cảnh ở đây...",
                        lines=8,
                    )
                    with gr.Row():
                        analyze_btn = gr.Button("🔍 Phân tích Timestamp", variant="primary", scale=2)
                        clear_cache_btn = gr.Button("🗑️ Xóa Cache", variant="stop", scale=1)
                    
                    analyze_log = gr.Textbox(label="Nhật ký phân tích", lines=3, interactive=False)

                with gr.Column(scale=5):
                    gr.Markdown("### 📊 Kết quả Phân cảnh & Biên tập")
                    gr.Markdown(
                        "**💡 Hướng dẫn:** Bạn có thể chỉnh sửa trực tiếp thời gian **Bắt đầu** / **Kết thúc** "
                        "trên bảng (nhập số giây hoặc định dạng `MM:SS.ss`), sau đó nhấn nút **Cập nhật** bên dưới."
                    )
                    timestamp_table = gr.Dataframe(
                        headers=["#", "Bắt đầu", "Kết thúc", "Thời lượng", "Phân cảnh", "Khớp"],
                        label="Bảng điều chỉnh timestamp",
                        wrap=True,
                        interactive=True,
                        col_count=(6, "fixed"),
                    )
                    with gr.Row():
                        update_btn = gr.Button("🔄 Cập nhật thay đổi", variant="secondary", scale=1)
                        update_log = gr.Textbox(label="", lines=1, interactive=False, placeholder="Trạng thái cập nhật", scale=2)
                    
                    with gr.Accordion("⬇️ Xuất dữ liệu cấu hình / Phụ đề", open=False):
                        with gr.Row():
                            btn_json = gr.Button("⬇️ Xuất JSON", size="sm")
                            btn_csv  = gr.Button("⬇️ Xuất CSV", size="sm")
                            btn_srt  = gr.Button("⬇️ Xuất SRT Sub", size="sm")
                        export_file = gr.File(label="Tải file đã xuất")

        with gr.Tab("🎬 Bước 2: Tạo & Render Video"):
            with gr.Row():
                with gr.Column(scale=4):
                    gr.Markdown("### 🎥 Thiết lập Render")
                    image_files = gr.File(
                        label="🖼️ Tải lên ảnh phân cảnh (tên file dạng 001_..., 002_...)",
                        file_count="multiple",
                        file_types=["image"],
                    )
                    resolution = gr.Radio(
                        label="📐 Tỉ lệ khung hình video",
                        choices=[
                            "Dọc 9:16 (TikTok/Reels)",
                            "Ngang 16:9 (YouTube)",
                            "Vuông 1:1 (Instagram)",
                        ],
                        value="Dọc 9:16 (TikTok/Reels)",
                    )
                    with gr.Accordion("⚙️ Cấu hình nâng cao (Camera & Chuyển cảnh)", open=False):
                        intensity = gr.Slider(
                            label="🎥 Cường độ Camera Motion (zoom/pan)",
                            minimum=0.0,
                            maximum=0.15,
                            value=0.08,
                            step=0.01,
                            info="0 = tĩnh, 0.15 = chuyển động mạnh",
                        )
                        transition_dur = gr.Slider(
                            label="✨ Thời gian Transition (giây)",
                            minimum=0.2,
                            maximum=1.5,
                            value=0.8,
                            step=0.1,
                            info="Crossfade tối đa giữa các phân cảnh (adaptive theo khoảng lặng)",
                        )
                    
                    render_btn  = gr.Button("🎬 Bắt đầu Tạo Video", variant="primary", size="lg")
                    
                    gr.Markdown("""
                    **💡 Các hiệu ứng được tích hợp sẵn:**
                    * **Camera Motion**: Tự động áp dụng ngẫu nhiên trong 10 kiểu chuyển động máy ảnh chuyên nghiệp.
                    * **Crossfade**: Chuyển cảnh mượt mà, tự động điều chỉnh theo khoảng lặng của giọng đọc.
                    * **Vignette**: Tạo viền tối cinematic chất lượng cao.
                    """)

                with gr.Column(scale=5):
                    gr.Markdown("### 🎞️ Kết quả Video")
                    video_output = gr.Video(label="Trình xem video kết quả", height=450)
                    render_log  = gr.Textbox(label="📋 Tiến trình Render (real-time)", lines=6, interactive=False, autoscroll=True)

    # ── Events ──────────────────────────────────────────────────────────────
    analyze_btn.click(
        fn=analyze_timestamps,
        inputs=[api_key, audio_input, scenes_input, language],
        outputs=[timestamp_table, analyze_log],
    )

    update_btn.click(
        fn=sync_timestamps,
        inputs=[timestamp_table, api_key, audio_input, scenes_input, language],
        outputs=[update_log, timestamp_table],
    )

    clear_cache_btn.click(
        fn=_clear_cache,
        inputs=[],
        outputs=[api_key, audio_input, scenes_input, language, update_log, timestamp_table],
    )

    render_btn.click(
        fn=render_video,
        inputs=[audio_input, image_files, resolution, intensity, transition_dur],
        outputs=[video_output, render_log],
        show_progress=True,
    )

    btn_json.click(fn=export_json, outputs=[export_file])
    btn_csv.click(fn=export_csv,  outputs=[export_file])
    btn_srt.click(fn=export_srt,  outputs=[export_file])

    # Tải lại cache khi load trang
    demo.load(
        fn=load_cached_state,
        inputs=[],
        outputs=[api_key, audio_input, scenes_input, language, timestamp_table],
    )


if __name__ == "__main__":
    demo.launch(inbrowser=True)

