"""
app.py — FastAPI Backend cho Audio Timestamp + Video Generator Tool
"""

import os
import json
import tempfile
import threading
import queue
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.utils import sort_images, validate_inputs, fmt_time, parse_time, fmt_srt_time
from core.whisper_client import transcribe, match_scenes
from core.video_builder import build_video, RESOLUTIONS


# ── Initialization ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Auto Video Generator API",
    description="Backend API for Automatic Video Editing and Rendering System",
    version="1.0.0"
)

# Thư mục uploads
UPLOAD_DIR = Path("uploads")
AUDIO_DIR = UPLOAD_DIR / "audio"
IMAGES_DIR = UPLOAD_DIR / "images"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Thư mục output video và static
OUTPUT_DIR = Path("static/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = "cache_state.json"


# ── Cache Helpers ─────────────────────────────────────────────────────────────

def _load_cache_data() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(api_key: str, audio_path: str, scenes_text: str, language: str, matched_scenes: list, preview_mode: bool = False):
    try:
        data = {
            "api_key": api_key,
            "audio_path": audio_path,
            "scenes_text": scenes_text,
            "language": language,
            "matched_scenes": matched_scenes,
            "preview_mode": preview_mode
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi lưu cache: {e}")


# ── Schemas ───────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    api_key: str
    audio_path: str
    scenes_text: str
    language: str


class SyncRequest(BaseModel):
    api_key: str
    audio_path: str
    scenes_text: str
    language: str
    matched_scenes: List[dict]
    preview_mode: bool = False


class RenderRequest(BaseModel):
    audio_path: str
    image_paths: List[str]
    resolution: str
    intensity: float
    transition_dur: float
    preview_mode: bool


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/load-cache")
async def load_cache():
    data = _load_cache_data()
    if not data:
        return JSONResponse(content={
            "api_key": "",
            "audio_path": "",
            "audio_filename": "",
            "scenes_text": "",
            "language": "Tiếng Việt",
            "matched_scenes": [],
            "preview_mode": False,
            "image_paths": []
        })
    
    # Lấy thông tin ảnh hiện có trong thư mục uploads
    image_files = []
    if IMAGES_DIR.exists():
        image_files = [str(p.absolute()).replace("\\", "/") for p in IMAGES_DIR.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}]
        image_files = sort_images(image_files)

    return {
        "api_key": data.get("api_key", ""),
        "audio_path": data.get("audio_path", ""),
        "audio_filename": os.path.basename(data.get("audio_path", "")) if data.get("audio_path") else "",
        "scenes_text": data.get("scenes_text", ""),
        "language": data.get("language", "Tiếng Việt"),
        "matched_scenes": data.get("matched_scenes", []),
        "preview_mode": data.get("preview_mode", False),
        "image_paths": image_files
    }


@app.post("/api/clear-cache")
async def clear_cache():
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
        except Exception:
            pass
    # Xóa file upload
    for folder in [AUDIO_DIR, IMAGES_DIR, OUTPUT_DIR]:
        if folder.exists():
            for f in folder.glob("*"):
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass
    return {"status": "success", "message": "Đã xóa toàn bộ cache và file tạm thành công."}


@app.post("/api/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    # Dọn dẹp file audio cũ
    for f in AUDIO_DIR.glob("*"):
        try:
            f.unlink()
        except Exception:
            pass
    
    file_path = AUDIO_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "status": "success",
        "filename": file.filename,
        "path": str(file_path.absolute()).replace("\\", "/")
    }


@app.post("/api/upload-images")
async def upload_images(files: List[UploadFile] = File(...)):
    # Dọn dẹp ảnh cũ để tránh nhầm lẫn
    for f in IMAGES_DIR.glob("*"):
        try:
            f.unlink()
        except Exception:
            pass
            
    saved_paths = []
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            file_path = IMAGES_DIR / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_paths.append(str(file_path.absolute()).replace("\\", "/"))
            
    sorted_paths = sort_images(saved_paths)
    return {
        "status": "success",
        "images": [os.path.basename(p) for p in sorted_paths],
        "paths": sorted_paths
    }


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập OpenAI API Key.")
    if not req.audio_path or not os.path.exists(req.audio_path):
        raise HTTPException(status_code=400, detail="Không tìm thấy file audio. Vui lòng tải lên trước.")
        
    scenes = [s.strip() for s in req.scenes_text.strip().splitlines() if s.strip()]
    if not scenes:
        raise HTTPException(status_code=400, detail="Vui lòng nhập danh sách phân cảnh.")
        
    lang_map = {"Tiếng Việt": "vi", "English": "en", "Tự động": None}
    lang_code = lang_map.get(req.language, "vi")
    
    try:
        segments, words = transcribe(req.audio_path, req.api_key.strip(), lang_code)
        matched_scenes = match_scenes(scenes, segments, words)
        
        # Ghi vào cache
        _save_cache(
            api_key=req.api_key,
            audio_path=req.audio_path,
            scenes_text=req.scenes_text,
            language=req.language,
            matched_scenes=matched_scenes
        )
        return {"status": "success", "matched_scenes": matched_scenes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync")
async def sync(req: SyncRequest):
    try:
        for item in req.matched_scenes:
            item["start"] = round(float(item["start"]), 2)
            item["end"] = round(float(item["end"]), 2)
            item["duration"] = round(item["end"] - item["start"], 2)
            
        _save_cache(
            api_key=req.api_key,
            audio_path=req.audio_path,
            scenes_text=req.scenes_text,
            language=req.language,
            matched_scenes=req.matched_scenes,
            preview_mode=req.preview_mode
        )
        return {"status": "success", "matched_scenes": req.matched_scenes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/render")
def render_video_endpoint(req: RenderRequest):
    q = queue.Queue()
    
    res_map = {
        "Dọc 9:16 (TikTok/Reels)": "portrait_9_16",
        "Ngang 16:9 (YouTube)":     "landscape_16_9",
        "Vuông 1:1 (Instagram)":    "square_1_1",
    }
    resolution = res_map.get(req.resolution, "portrait_9_16")
    output_path = OUTPUT_DIR / "video_output.mp4"
    
    cache_data = _load_cache_data()
    matched_scenes = cache_data.get("matched_scenes", [])
    if not matched_scenes:
        raise HTTPException(status_code=400, detail="Không tìm thấy dữ liệu phân cảnh. Vui lòng chạy phân tích trước.")
        
    def progress_cb(step, pct):
        q.put({"step": step, "pct": pct})
        
    def worker():
        try:
            # Xóa file video cũ nếu tồn tại
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
            
            # Kiểm tra dữ liệu ảnh đầu vào
            warnings = validate_inputs(req.image_paths, matched_scenes)
            if warnings:
                for w in warnings:
                    q.put({"step": f"⚠️ Cảnh báo: {w}", "pct": 0})
            
            q.put({"step": "→ Bắt đầu dựng và render video...", "pct": 1})
            
            # Gọi hàm build_video gốc từ core
            build_video(
                matched_scenes=matched_scenes,
                image_paths=req.image_paths,
                audio_path=req.audio_path,
                output_path=str(output_path),
                resolution=resolution,
                ken_burns_intensity=req.intensity,
                transition_dur=req.transition_dur,
                progress_callback=progress_cb,
                preview_mode=req.preview_mode
            )
            
            # Lưu ý: Client sẽ đọc tệp này thông qua static server của FastAPI
            q.put({
                "step": "✅ Render video thành công!", 
                "pct": 100, 
                "video_url": f"/static/outputs/video_output.mp4?t={os.path.getmtime(output_path)}"
            })
        except Exception as e:
            q.put({"step": f"❌ Lỗi render: {str(e)}", "pct": 0})
        finally:
            q.put(None)  # Sentinel để báo hiệu kết thúc generator
            
    # Chạy tác vụ nặng trên Background Thread để tránh chặn event loop chính
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    
    # Trả về StreamingResponse dạng Server-Sent Events (SSE)
    def sse_generator():
        while True:
            item = q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/export")
def export_subtitles(format: str):
    cache_data = _load_cache_data()
    matched_scenes = cache_data.get("matched_scenes", [])
    if not matched_scenes:
        raise HTTPException(status_code=400, detail="Không có dữ liệu phân cảnh để xuất.")
        
    if format == "json":
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
        json.dump(matched_scenes, tmp, ensure_ascii=False, indent=2)
        tmp.close()
        return FileResponse(tmp.name, filename="scenes.json", media_type="application/json")
        
    elif format == "csv":
        lines = ["Screen,Start,End,Duration,Text,Match%"]
        for m in matched_scenes:
            text = m["scene"].replace('"', '""')
            lines.append(f'{m["screen"]},{m["start"]},{m["end"]},{m["duration"]},"{text}",{m["match_pct"]}')
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8")
        tmp.write("\n".join(lines))
        tmp.close()
        return FileResponse(tmp.name, filename="scenes.csv", media_type="text/csv")
        
    elif format == "srt":
        lines = []
        for m in matched_scenes:
            lines.append(str(m["screen"]))
            lines.append(f"{fmt_srt_time(m['start'])} --> {fmt_srt_time(m['end'])}")
            lines.append(m["scene"])
            lines.append("")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".srt", mode="w", encoding="utf-8")
        tmp.write("\n".join(lines))
        tmp.close()
        return FileResponse(tmp.name, filename="subtitles.srt", media_type="text/plain")
        
    else:
        raise HTTPException(status_code=400, detail="Định dạng xuất không hỗ trợ.")


# ── Serve Static Files & SPA Routing ──────────────────────────────────────────

# Route chính trả về giao diện HTML
@app.get("/")
def get_index():
    index_path = Path("static/index.html")
    if not index_path.exists():
        return HTMLResponse(content="<h1>Frontend index.html is missing.</h1>", status_code=404)
    return FileResponse(index_path)


# Mount thư mục static (CSS, JS) và thư mục uploads (để trình phát video chạy cục bộ)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


if __name__ == "__main__":
    import uvicorn
    # Chạy server mặc định tại cổng 7860
    uvicorn.run("app:app", host="127.0.0.1", port=7860, reload=True)
