"""
app.py — Gradio UI cho Audio Timestamp + Video Generator Tool
"""

import os
import json
import tempfile
import threading
from pathlib import Path

import matplotlib
matplotlib.use("Agg")           # non-interactive backend cho server
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import gradio as gr

from core.utils import sort_images, validate_inputs, fmt_time, parse_time, fmt_srt_time
from core.whisper_client import transcribe, match_scenes, results_to_table
from core.video_builder import build_video, RESOLUTIONS


# ── State ─────────────────────────────────────────────────────────────────────

_matched_scenes: list[dict] = []
_sorted_images:  list[str]  = []
_progress_log:   list[str]  = []


# ── Timeline Gantt chart ───────────────────────────────────────────────────────

def _build_timeline_fig():
    """Tạo Gantt chart từ _matched_scenes. Trả về matplotlib Figure."""
    if not _matched_scenes:
        return None

    n        = len(_matched_scenes)
    fig_h    = max(4, n * 0.6 + 1.5)
    fig, ax  = plt.subplots(figsize=(14, fig_h))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    max_time = max(s["end"] for s in _matched_scenes) * 1.04

    for i, scene in enumerate(_matched_scenes):
        pct   = scene["match_pct"]
        y     = n - 1 - i          # scene 1 ở trên cùng
        color = "#4ade80" if pct >= 60 else "#fb923c" if pct >= 30 else "#f87171"
        glow  = "#166534" if pct >= 60 else "#92400e" if pct >= 30 else "#7f1d1d"

        # Shadow / glow
        ax.barh(y, scene["duration"], left=scene["start"], height=0.75,
                color=glow, alpha=0.35, linewidth=0)
        # Main bar
        ax.barh(y, scene["duration"], left=scene["start"], height=0.6,
                color=color, alpha=0.92, edgecolor="white", linewidth=0.4)

        # Label bên trong bar
        label = f"#{scene['screen']}  {pct}%"
        ax.text(
            scene["start"] + scene["duration"] / 2, y, label,
            ha="center", va="center", fontsize=7.5,
            fontweight="bold", color="white", fontfamily="monospace",
        )

    # Axes styling
    ax.set_yticks(range(n))
    ax.set_yticklabels(
        [f"Scene {s['screen']}" for s in reversed(_matched_scenes)],
        fontsize=8, color="#cbd5e1",
    )
    ax.set_xlim(0, max_time)
    ax.set_xlabel("Thời gian (giây)", color="#94a3b8", fontsize=9)
    ax.set_title("📊 Timeline Phân Cảnh", color="white", fontsize=12,
                 fontweight="bold", pad=12)
    ax.tick_params(axis="x", colors="#94a3b8", labelsize=8)
    ax.tick_params(axis="y", colors="#cbd5e1")
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")
    ax.grid(axis="x", color="#334155", linewidth=0.5, linestyle="--", alpha=0.6)

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor="#4ade80", label="✅ Tốt (≥60%)"),
        mpatches.Patch(facecolor="#fb923c", label="⚠️ Trung bình (30-60%)"),
        mpatches.Patch(facecolor="#f87171", label="❌ Kém (<30%)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right",
              facecolor="#1e293b", edgecolor="#334155",
              labelcolor="#cbd5e1", fontsize=8)

    plt.tight_layout()
    return fig


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

        table = results_to_table(_matched_scenes)
        fig   = _build_timeline_fig()
        return table, log, fig

    except Exception as e:
        return None, f"❌ Lỗi: {str(e)}", None


# ── Sync timestamp từ bảng đã edit ───────────────────────────────────────────

def sync_timestamps(table):
    """Đọc bảng đã edit, cập nhật _matched_scenes, vẽ lại timeline."""
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

        new_table = results_to_table(_matched_scenes)
        fig       = _build_timeline_fig()
        return f"✅ Đã cập nhật {updated} dòng.", new_table, fig

    except Exception as e:
        return f"❌ Lỗi: {e}", gr.update(), gr.update()


# ── Step 2: Render video ──────────────────────────────────────────────────────

def render_video(
    audio_path,
    image_files,
    resolution_label,
    intensity,
    transition_dur,
    progress=gr.Progress(track_tqdm=True),
):
    global _matched_scenes

    if not _matched_scenes:
        return None, "❌ Chưa có dữ liệu timestamp. Hãy chạy 'Phân tích' trước."
    if not audio_path:
        return None, "❌ Thiếu file audio."
    if not image_files:
        return None, "❌ Chưa upload ảnh."

    image_paths = sort_images([f.name for f in image_files])
    if not image_paths:
        return None, "❌ Không tìm thấy ảnh hợp lệ (png/jpg/webp)."

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

    def on_progress(step, pct):
        log_lines.append(f"[{pct:3d}%] {step}")
        progress(pct / 100, desc=step)

    try:
        result  = build_video(
            matched_scenes=_matched_scenes,
            image_paths=image_paths,
            audio_path=audio_path,
            output_path=output_path,
            resolution=resolution,
            ken_burns_intensity=float(intensity),
            transition_dur=float(transition_dur),
            progress_callback=on_progress,
        )
        size_mb = os.path.getsize(result) / 1024 / 1024
        log_lines.append(f"✓ File: {result} ({size_mb:.1f} MB)")
        return result, "\n".join(log_lines)

    except Exception as e:
        log_lines.append(f"❌ Lỗi render: {str(e)}")
        return None, "\n".join(log_lines)


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
**Tự động tạo video từ ảnh phân cảnh + audio voiceover bằng OpenAI Whisper**

**Quy trình:** Upload audio + ảnh + text phân cảnh → Phân tích timestamp → Tạo video
"""

STEP1_INFO = """
### Bước 1: Phân tích Timestamp
Whisper sẽ nhận dạng audio và xác định thời điểm bắt đầu/kết thúc từng phân cảnh.
"""

STEP2_INFO = """
### Bước 2: Tạo Video
Ghép ảnh + audio theo timestamp, thêm Ken Burns effect và crossfade transition.

**Tên file ảnh:** `001_text.png`, `002_text.png`... (sort theo số prefix)
"""

with gr.Blocks(title="Auto Video Generator", theme=gr.themes.Soft()) as demo:
    gr.Markdown(DESCRIPTION)

    # ── Bước 1 ──────────────────────────────────────────────────────────────
    gr.Markdown(STEP1_INFO)

    with gr.Row():
        with gr.Column(scale=1):
            api_key = gr.Textbox(
                label="🔑 OpenAI API Key",
                placeholder="sk-...",
                type="password",
                info="Key không được lưu lại, chỉ dùng trong session này.",
            )
            audio_input = gr.Audio(
                label="🎵 File Audio",
                type="filepath",
                sources=["upload"],
            )
            language = gr.Radio(
                label="🌐 Ngôn ngữ audio",
                choices=["Tiếng Việt", "English", "Tự động"],
                value="Tiếng Việt",
            )

        with gr.Column(scale=1):
            scenes_input = gr.Textbox(
                label="📋 Danh sách phân cảnh (mỗi dòng 1 câu)",
                placeholder="Có những ngày bạn thấy mình ổn...\nBạn vẫn đi làm...",
                lines=12,
            )

    analyze_btn = gr.Button("🔍 Phân tích Timestamp", variant="primary", size="lg")
    analyze_log = gr.Textbox(label="Log phân tích", lines=4, interactive=False)

    # ── Bảng kết quả — có thể edit cột Bắt đầu / Kết thúc ──────────────────
    gr.Markdown(
        "**💡 Tip:** Bạn có thể double-click vào ô **Bắt đầu** / **Kết thúc** "
        "để sửa thủ công (định dạng `MM:SS.ss`), sau đó nhấn **Cập nhật**."
    )
    timestamp_table = gr.Dataframe(
        headers=["#", "Bắt đầu", "Kết thúc", "Thời lượng", "Phân cảnh", "Khớp"],
        label="📊 Kết quả Timestamp",
        wrap=True,
        interactive=True,
        col_count=(6, "fixed"),
    )

    with gr.Row():
        update_btn = gr.Button("🔄 Cập nhật timestamp", variant="secondary", scale=1)
        update_log = gr.Textbox(label="", lines=1, interactive=False, scale=3)

    # ── Timeline Gantt chart ─────────────────────────────────────────────────
    timeline_plot = gr.Plot(label="📈 Timeline phân cảnh")

    # ── Export ──────────────────────────────────────────────────────────────
    with gr.Row():
        btn_json = gr.Button("⬇️ Tải JSON")
        btn_csv  = gr.Button("⬇️ Tải CSV")
        btn_srt  = gr.Button("⬇️ Tải SRT")
    with gr.Row():
        dl_json = gr.File(label="JSON")
        dl_csv  = gr.File(label="CSV")
        dl_srt  = gr.File(label="SRT  (import vào TikTok / YouTube)")

    gr.Markdown("---")

    # ── Bước 2 ──────────────────────────────────────────────────────────────
    gr.Markdown(STEP2_INFO)

    with gr.Row():
        with gr.Column(scale=1):
            image_files = gr.File(
                label="🖼️ Upload ảnh phân cảnh",
                file_count="multiple",
                file_types=["image"],
            )
            resolution = gr.Radio(
                label="📐 Tỉ lệ video",
                choices=[
                    "Dọc 9:16 (TikTok/Reels)",
                    "Ngang 16:9 (YouTube)",
                    "Vuông 1:1 (Instagram)",
                ],
                value="Dọc 9:16 (TikTok/Reels)",
            )

        with gr.Column(scale=1):
            intensity = gr.Slider(
                label="🔍 Cường độ Ken Burns (zoom)",
                minimum=0.0,
                maximum=0.15,
                value=0.08,
                step=0.01,
                info="0 = không zoom, 0.15 = zoom mạnh",
            )
            transition_dur = gr.Slider(
                label="✨ Thời gian Transition (giây)",
                minimum=0.2,
                maximum=1.5,
                value=0.5,
                step=0.1,
                info="Thời gian crossfade giữa các phân cảnh",
            )
            gr.Markdown("""
**Lưu ý:**
- Render 1 phút video ≈ 2–4 phút xử lý
- File ảnh cần đặt tên: `001_...png`, `002_...png`
- Ảnh tự động scale cover theo tỉ lệ video
""")

    render_btn  = gr.Button("🎬 Tạo Video", variant="primary", size="lg")
    render_log  = gr.Textbox(label="Log render", lines=6, interactive=False)
    video_output = gr.Video(label="🎥 Video Output")

    # ── Events ──────────────────────────────────────────────────────────────
    analyze_btn.click(
        fn=analyze_timestamps,
        inputs=[api_key, audio_input, scenes_input, language],
        outputs=[timestamp_table, analyze_log, timeline_plot],
    )

    update_btn.click(
        fn=sync_timestamps,
        inputs=[timestamp_table],
        outputs=[update_log, timestamp_table, timeline_plot],
    )

    render_btn.click(
        fn=render_video,
        inputs=[audio_input, image_files, resolution, intensity, transition_dur],
        outputs=[video_output, render_log],
    )

    btn_json.click(fn=export_json, outputs=[dl_json])
    btn_csv.click(fn=export_csv,  outputs=[dl_csv])
    btn_srt.click(fn=export_srt,  outputs=[dl_srt])


if __name__ == "__main__":
    demo.launch(inbrowser=True)
