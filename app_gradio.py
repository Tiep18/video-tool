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


def _save_cache(api_key, audio_path, scenes_text, language, preview_mode=None):
    global _matched_scenes
    try:
        old_preview = False
        if preview_mode is None and os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    old_preview = old_data.get("preview_mode", False)
            except Exception:
                pass
        elif preview_mode is not None:
            old_preview = preview_mode

        data = {
            "api_key": api_key,
            "audio_path": audio_path,
            "scenes_text": scenes_text,
            "language": language,
            "matched_scenes": _matched_scenes,
            "preview_mode": old_preview
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi lưu cache: {e}")


def _save_preview_mode_cache(preview_mode):
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["preview_mode"] = preview_mode
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Lỗi lưu cache preview_mode: {e}")
    else:
        try:
            data = {"preview_mode": preview_mode}
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Lỗi lưu cache preview_mode: {e}")


def _clear_cache():
    global _matched_scenes
    _matched_scenes = []
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
        except Exception:
            pass
    gr.Info("🗑️ Đã xóa cache thành công.")
    return (
        "",          # api_key
        None,        # audio_input
        "",          # scenes_input
        "Tiếng Việt", # language
        None,        # timestamp_table
        False,       # preview_mode
    )


def load_cached_state():
    global _matched_scenes
    if not os.path.exists(CACHE_FILE):
        return "", None, "", "Tiếng Việt", None, False
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
        preview_mode = data.get("preview_mode", False)
        
        table = results_to_table(_matched_scenes) if _matched_scenes else None
        
        return api_key, audio_path, scenes_text, language, table, preview_mode
    except Exception as e:
        print(f"Lỗi load cache: {e}")
        return "", None, "", "Tiếng Việt", None, False


# _build_timeline_fig was removed since the timeline plot is no longer needed.


# ── Step 1: Phân tích timestamp ───────────────────────────────────────────────

def analyze_timestamps(api_key, audio_path, scenes_text, language):
    global _matched_scenes, _sorted_images

    if not api_key.strip():
        raise gr.Error("Vui lòng nhập OpenAI API Key.")
    if not audio_path:
        raise gr.Error("Vui lòng upload file audio.")

    scenes = [s.strip() for s in scenes_text.strip().splitlines() if s.strip()]
    if not scenes:
        raise gr.Error("Vui lòng nhập danh sách phân cảnh.")

    lang_map  = {"Tiếng Việt": "vi", "English": "en", "Tự động": None}
    lang_code = lang_map.get(language, "vi")

    try:
        gr.Info("Đang gửi audio lên Whisper API...")
        segments, words = transcribe(audio_path, api_key.strip(), lang_code)
        
        _matched_scenes = match_scenes(scenes, segments, words)
        good = sum(1 for m in _matched_scenes if m["match_pct"] >= 60)
        gr.Info(f"Phân tích hoàn tất! Khớp {good}/{len(_matched_scenes)} phân cảnh.")

        # Ghi cache cục bộ
        _save_cache(api_key, audio_path, scenes_text, language)

        table = results_to_table(_matched_scenes)
        return table

    except Exception as e:
        raise gr.Error(f"Lỗi: {str(e)}")


# ── Sync timestamp từ bảng đã edit ───────────────────────────────────────────

def sync_timestamps(table, api_key, audio_path, scenes_text, language):
    """Đọc bảng đã edit, cập nhật _matched_scenes, vẽ lại timeline và lưu cache."""
    global _matched_scenes

    if not _matched_scenes or table is None:
        raise gr.Error("Chưa có dữ liệu phân tích.")

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
        gr.Info(f"✅ Đã cập nhật {updated} phân cảnh thành công.")
        return new_table

    except Exception as e:
        raise gr.Error(f"Lỗi cập nhật: {e}")


# ── Step 2: Render video ──────────────────────────────────────────────────────

def render_video(
    audio_path,
    image_files,
    resolution_label,
    intensity,
    transition_dur,
    preview_mode,
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
                preview_mode=preview_mode,
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

BANNER_HTML = """
<div class="banner">
    <h1>🎬 Auto Video Generator</h1>
    <p>Hệ thống tự động biên tập và tạo video phân cảnh bằng trí tuệ nhân tạo</p>
</div>
"""

CSS_THEME = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap');

:root {
    --body-background-fill: #090d16;
    --container-background-fill: #0f172a;
    --block-background-fill: #1e293b;
    --block-border-color: #334155;
    --border-color-primary: #334155;
    --background-fill-primary: #1e293b;
    --background-fill-secondary: #0f172a;
    --input-background-fill: #0f172a;
    --checkbox-background-color: #334155;
    --button-primary-background-fill: linear-gradient(135deg, #6366f1, #8b5cf6);
    --button-primary-background-fill-hover: linear-gradient(135deg, #4f46e5, #7c3aed);
    --button-primary-text-color: #ffffff;
    --button-secondary-background-fill: #334155;
    --button-secondary-background-fill-hover: #475569;
    --button-secondary-text-color: #ffffff;
    --primary-500: #6366f1;
    --primary-600: #8b5cf6;
    --secondary-500: #10b981;
}

body, .gradio-container, * {
    font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif !important;
}

.banner {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    text-align: center;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
    backdrop-filter: blur(5px);
}

.banner h1 {
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, #a5b4fc, #c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px !important;
    letter-spacing: -0.025em;
}

.banner p {
    color: #94a3b8 !important;
    font-size: 1rem !important;
    margin: 0 !important;
}

.gradio-container {
    max-width: 1400px !important;
}

/* Form inputs & boxes */
.gr-box {
    border-radius: 12px !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
}

input, textarea, select {
    border-radius: 8px !important;
    border: 1px solid #334155 !important;
    transition: all 0.2s ease !important;
}

input:focus, textarea:focus, select:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
}

/* Custom styled buttons */
.btn-primary {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3) !important;
    transition: all 0.2s ease !important;
}

.btn-primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4) !important;
}

.btn-secondary {
    background-color: #334155 !important;
    border: 1px solid #475569 !important;
    color: #f8fafc !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}

.btn-secondary:hover {
    background-color: #475569 !important;
    border-color: #64748b !important;
}

.btn-stop {
    background-color: #ef4444 !important;
    border: none !important;
    color: white !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 10px rgba(239, 68, 68, 0.2) !important;
}

.btn-stop:hover {
    background-color: #dc2626 !important;
    box-shadow: 0 6px 14px rgba(239, 68, 68, 0.3) !important;
}

/* Custom styled DataFrame */
.gr-table-container {
    border-radius: 12px !important;
    border: 1px solid #334155 !important;
    overflow: hidden !important;
}

/* Terminal styled log */
.console-log textarea {
    font-family: 'Fira Code', 'Courier New', Courier, monospace !important;
    background-color: #020617 !important;
    color: #22d3ee !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px !important;
    font-size: 0.9rem !important;
    line-height: 1.5 !important;
    padding: 12px !important;
}

/* Section title headers */
.column-title {
    font-size: 1.25rem !important;
    font-weight: 600 !important;
    color: #f1f5f9 !important;
    margin-bottom: 16px !important;
    border-left: 4px solid #6366f1;
    padding-left: 10px;
}

/* Custom styled accordion */
.gr-accordion {
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    background-color: #0f172a !important;
    margin-bottom: 12px !important;
}
"""

with gr.Blocks(title="Auto Video Generator", css=CSS_THEME, theme=gr.themes.Soft()) as demo:
    gr.HTML(BANNER_HTML)

    with gr.Row():
        # ── Cột trái: Phân tích & Biên tập Timestamp (Step 1) ─────────────────
        with gr.Column(scale=1):
            gr.HTML("<div class='column-title'>⚙️ BƯỚC 1: PHÂN TÍCH & BIÊN TẬP</div>")
            
            with gr.Accordion("🔑 Cấu hình OpenAI API Key", open=True, elem_classes=["gr-accordion"]):
                api_key = gr.Textbox(
                    label="OpenAI API Key",
                    placeholder="sk-...",
                    type="password",
                    info="Nhập API Key để chạy nhận dạng Whisper.",
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
                lines=6,
            )
            
            with gr.Row():
                analyze_btn = gr.Button("🔍 Phân tích Timestamp", variant="primary", elem_classes=["btn-primary"])
                clear_cache_btn = gr.Button("🗑️ Xóa Cache", variant="stop", elem_classes=["btn-stop"])

            gr.HTML("<div style='margin-top: 24px; margin-bottom: 8px; font-weight: 500; color: #e2e8f0;'>📊 Bảng Điều Chỉnh Phân Phối Timestamp</div>")
            timestamp_table = gr.Dataframe(
                headers=["#", "Bắt đầu", "Kết thúc", "Thời lượng", "Phân cảnh", "Khớp"],
                label=None,
                wrap=True,
                interactive=True,
                col_count=(6, "fixed"),
            )
            
            update_btn = gr.Button("🔄 Cập nhật thay đổi", variant="secondary", elem_classes=["btn-secondary"])
            
            with gr.Accordion("⬇️ Xuất dữ liệu cấu hình / Phụ đề", open=False, elem_classes=["gr-accordion"]):
                with gr.Row():
                    btn_json = gr.Button("⬇️ JSON", size="sm", elem_classes=["btn-secondary"])
                    btn_csv  = gr.Button("⬇️ CSV", size="sm", elem_classes=["btn-secondary"])
                    btn_srt  = gr.Button("⬇️ SRT", size="sm", elem_classes=["btn-secondary"])
                export_file = gr.File(label="Tải file đã xuất")

        # ── Cột phải: Tạo & Render Video (Step 2) ──────────────────────────
        with gr.Column(scale=1):
            gr.HTML("<div class='column-title'>🎬 BƯỚC 2: DỰNG & RENDER VIDEO</div>")
            
            image_files = gr.File(
                label="🖼️ Tải lên ảnh phân cảnh (tên file dạng 001_..., 002_...)",
                file_count="multiple",
                file_types=["image"],
                height=150,
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
            
            preview_mode = gr.Checkbox(
                label="⚡ Chế độ Preview Nhanh (Render ~15s, 360p, 15 FPS)",
                value=False,
            )
            
            with gr.Accordion("⚙️ Cấu hình nâng cao (Camera & Chuyển cảnh)", open=False, elem_classes=["gr-accordion"]):
                intensity = gr.Slider(
                    label="🎥 Cường độ Camera Motion (zoom/pan)",
                    minimum=0.0,
                    maximum=0.15,
                    value=0.08,
                    step=0.01,
                )
                transition_dur = gr.Slider(
                    label="✨ Thời gian Transition (giây)",
                    minimum=0.2,
                    maximum=1.5,
                    value=0.8,
                    step=0.1,
                )
            
            render_btn = gr.Button("🎬 Bắt đầu Tạo Video", variant="primary", elem_classes=["btn-primary"], size="lg")
            
            gr.HTML("<div style='margin-top: 24px; margin-bottom: 8px; font-weight: 500; color: #e2e8f0;'>🎞️ Kết quả Video & Tiến trình</div>")
            video_output = gr.Video(label=None, height=350)
            render_log = gr.Textbox(
                label="📋 Tiến trình Render (real-time console)",
                lines=5,
                interactive=False,
                autoscroll=True,
                elem_classes=["console-log"],
            )

    # ── Events ──────────────────────────────────────────────────────────────
    analyze_btn.click(
        fn=analyze_timestamps,
        inputs=[api_key, audio_input, scenes_input, language],
        outputs=[timestamp_table],
    )

    update_btn.click(
        fn=sync_timestamps,
        inputs=[timestamp_table, api_key, audio_input, scenes_input, language],
        outputs=[timestamp_table],
    )

    preview_mode.change(
        fn=_save_preview_mode_cache,
        inputs=[preview_mode],
        outputs=[],
    )

    clear_cache_btn.click(
        fn=_clear_cache,
        inputs=[],
        outputs=[api_key, audio_input, scenes_input, language, timestamp_table, preview_mode],
    )

    render_btn.click(
        fn=render_video,
        inputs=[audio_input, image_files, resolution, intensity, transition_dur, preview_mode],
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
        outputs=[api_key, audio_input, scenes_input, language, timestamp_table, preview_mode],
    )


if __name__ == "__main__":
    demo.launch(inbrowser=True)

