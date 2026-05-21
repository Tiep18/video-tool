# 🎬 Auto Video Generator

Tự động tạo video từ ảnh phân cảnh + audio voiceover bằng OpenAI Whisper API.

---

## Tính năng

- **Whisper API**: Nhận dạng audio → timestamp từng phân cảnh
- **Ken Burns Effect**: Zoom in/out + pan chậm cho từng ảnh
- **Crossfade Transition**: Chuyển cảnh mượt mà giữa các phân cảnh
- **Fade In/Out**: Hiệu ứng mờ dần đầu và cuối video
- **Hỗ trợ**: TikTok 9:16 / YouTube 16:9 / Instagram 1:1

---

## Cài đặt

**Yêu cầu:** Python 3.10+, ffmpeg

```bash
# 1. Cài ffmpeg (nếu chưa có)
# macOS:
brew install ffmpeg
# Windows: tải tại https://ffmpeg.org/download.html
# Ubuntu:
sudo apt install ffmpeg

# 2. Cài Python packages
pip install -r requirements.txt

# 3. Chạy app
python app.py
```

Mở trình duyệt tại: **http://localhost:7860**

---

## Cách dùng

### Bước 1 — Phân tích Timestamp
1. Nhập **OpenAI API Key** (bắt đầu bằng `sk-...`)
2. Upload **file audio** (mp3, wav, m4a...)
3. Dán **danh sách phân cảnh** — mỗi dòng 1 câu
4. Chọn ngôn ngữ → Bấm **Phân tích Timestamp**
5. Kiểm tra bảng kết quả (cột Khớp ≥ 60% = tốt)

### Bước 2 — Tạo Video
1. Upload **ảnh phân cảnh** (đặt tên: `001_ten.png`, `002_ten.png`...)
2. Chọn tỉ lệ video, cường độ zoom, thời gian transition
3. Bấm **Tạo Video** → đợi render → tải file `.mp4`

---

## Quy tắc đặt tên ảnh

```
001_co_nhung_ngay.png     ← phân cảnh 1
002_ban_van_di_lam.png    ← phân cảnh 2
003_nhung_khi_o_mot_minh.png
...
```

Ảnh được sort theo **số prefix** (001, 002...) và map 1-1 với phân cảnh.  
Nếu số ảnh ≠ số phân cảnh, tool sẽ cảnh báo và tự xử lý.

---

## Chi phí API

| File audio | Chi phí Whisper |
|-----------|----------------|
| 1 phút    | ~$0.006 (~150đ) |
| 5 phút    | ~$0.030 (~750đ) |

---

## Cấu trúc project

```
video_tool/
├── app.py                  # Gradio UI
├── requirements.txt
├── README.md
└── core/
    ├── __init__.py
    ├── utils.py            # Sort ảnh, normalize text, helpers
    ├── whisper_client.py   # Whisper API + scene matching
    └── video_builder.py    # Ken Burns, crossfade, export MP4
```
