# 🎬 Auto Video Generator & Editor

Hệ thống tự động tạo và biên tập video ngắn (TikTok 9:16, YouTube 16:9, Instagram 1:1) từ kịch bản, ảnh phân cảnh và giọng đọc voiceover, hỗ trợ phân tích mốc thời gian bằng trí tuệ nhân tạo (OpenAI Whisper) và đồng bộ âm thanh nâng cao.

---

## 🚀 Tính năng nổi bật

- **Phân tích Timestamps bằng AI (Whisper API):** Tự động bóc tách giọng đọc và map khớp từ khóa phân cảnh để định vị chính xác thời điểm bắt đầu/kết thúc của mỗi phân cảnh kịch bản.
- **Trình biên tập Timeline trực quan:** Chỉnh sửa trực tiếp thời lượng phân cảnh, tự động kiểm tra đè chéo thời gian thực (overlap validation), đồng bộ tức thì với bộ nhớ đệm.
- **Trình phát & Điều khiển Tốc độ Audio chuyên nghiệp:**
  - Nhúng trình phát nhạc trực tiếp để nghe thử giọng đọc (voiceover).
  - Tích hợp thanh trượt thay đổi tốc độ đọc từ `0.5x` đến `2.0x` (bước nhảy `0.1x`).
  - Tự động co giãn tuyến tính toàn bộ mốc thời gian phụ đề và kịch bản tương ứng khi thay đổi tốc độ.
  - Cơ chế tránh file lock trên Windows bằng đường dẫn động độc lập.
- **Render Video hiệu năng cao (MoviePy + FFmpeg):**
  - Hiệu ứng chuyển động hình ảnh Ken Burns tinh tế (zoom & pan chậm).
  - Tùy chỉnh hiệu ứng chuyển cảnh (transitions) và cường độ zoom.
  - Hỗ trợ đa dạng tỉ lệ khung hình (Khổ dọc 9:16 cho TikTok, Ngang 16:9 cho YouTube, Vuông 1:1 cho Instagram).
- **Màn hình Preview Video Mockup dọc:** Mô phỏng khung viền smartphone sang trọng cho video khổ dọc TikTok, không lo video bị thu nhỏ hay méo góc.
- **Giám sát Render qua SSE (Server-Sent Events):** Xuất log terminal thời gian thực và thanh tiến trình phần trăm (%) trực quan ngay trên giao diện.
- **Xuất phụ đề linh hoạt:** Hỗ trợ xuất dữ liệu phân cảnh dưới dạng file **SRT (Subtitles)**, **JSON** hoặc **CSV**.

---

## 📂 Cấu trúc Dự án

```text
video_tool/
├── core/                   # Logic lõi xử lý video & AI
│   ├── whisper_client.py   # Kết nối OpenAI Whisper & thuật toán khớp phân cảnh
│   ├── video_builder.py    # Render video bằng MoviePy, căn chỉnh hiệu ứng
│   └── utils.py            # Hàm bổ trợ: định dạng thời gian, sắp xếp ảnh, kiểm tra hợp lệ
├── frontend/               # Giao diện SPA React (Vite)
│   ├── src/
│   │   ├── App.jsx         # Giao diện chính và luồng xử lý API
│   │   ├── App.css         # CSS bổ sung cho giao diện
│   │   └── main.jsx        # Điểm khởi chạy React
│   ├── package.json        # Cấu hình thư viện frontend
│   └── vite.config.js      # Cấu hình Vite & API Proxy
├── static/                 # Tài nguyên static & File build frontend
│   └── dist/               # Thư mục chứa kết quả build từ frontend/
├── uploads/                # Thư mục lưu trữ tạm thời ảnh và âm thanh tải lên
│   ├── audio/              # Tệp âm thanh gốc và tệp âm thanh biến đổi tốc độ
│   └── images/             # Danh sách hình ảnh phân cảnh đã sắp xếp
├── app.py                  # Backend chính (FastAPI Server)
├── app_gradio.py           # Giao diện Gradio cũ (dự phòng)
├── cache_state.json        # Bộ nhớ đệm lưu trữ trạng thái phiên làm việc hiện tại
└── requirements.txt        # Các thư viện Python cần thiết
```

---

## 🛠️ Hướng dẫn Cài đặt & Khởi chạy

### 1. Yêu cầu hệ thống
- **Python 3.10+**
- **Node.js** (để quản lý & biên dịch frontend)
- **FFmpeg** (đã được cấu hình trong biến môi trường PATH của hệ thống)

### 2. Cài đặt và Chạy Backend
```bash
# 1. Tạo môi trường ảo Python
python -m venv venv
venv\Scripts\activate      # Trên Windows
source venv/bin/activate    # Trên macOS/Linux

# 2. Cài đặt các thư viện Python cần thiết
pip install -r requirements.txt

# 3. Khởi chạy Server FastAPI
python app.py
```
Server chạy mặc định tại cổng `7860`: [http://127.0.0.1:7860](http://127.0.0.1:7860).

### 3. Cài đặt và Biên dịch Frontend (Dành cho Lập trình viên)
Nếu muốn phát triển hoặc thay đổi giao diện:
```bash
# Di chuyển vào thư mục frontend
cd frontend

# Cài đặt thư viện Node.js
npm install

# Khởi chạy môi trường Dev Server (chạy song song với Backend)
npm run dev

# Biên dịch ra phiên bản Production (khi muốn chạy chung qua server FastAPI)
npm run build
```

---

## 📖 Quy trình Sử dụng Tool

1. **Nhập API Key:** Điền OpenAI API Key của bạn để sử dụng Whisper.
2. **Tải lên Audio:** Tải lên tệp âm thanh voiceover của kịch bản. Trình phát sẽ tự động xuất hiện.
3. **Nhập kịch bản:** Dán kịch bản vào, mỗi dòng là một phân cảnh độc lập tương ứng với một hình ảnh.
4. **Phân tích Timestamps:** Bấm nút **Phân tích Timestamps**. Whisper sẽ chạy và tự động xếp khớp các phân cảnh vào timeline với mốc thời gian dự kiến.
5. **Điều chỉnh tốc độ âm thanh (Tùy chọn):** Kéo thanh trượt tốc độ. Hệ thống tự động co giãn timeline khớp với file audio mới mà không làm méo giọng.
6. **Tinh chỉnh thủ công:** Xem bảng timeline ở giữa, nếu mốc thời gian nào chưa khớp chuẩn xác theo ý muốn, bạn có thể chỉnh sửa trực tiếp.
7. **Tải lên hình ảnh:** Đặt tên ảnh theo prefix số (ví dụ: `001_hinh_anh.jpg`, `002_hinh_anh.png`...) để hệ thống tự động ánh xạ 1-1 với thứ tự phân cảnh.
8. **Thiết lập Render & Tạo Video:** Chọn tỷ lệ (ví dụ: TikTok 9:16 dọc), thời lượng chuyển cảnh, cường độ zoom và bấm **Bắt đầu Tạo Video**. Giám sát log biên dịch ở ô Log Terminal bên dưới và thưởng thức video thành phẩm tại trình phát bên phải.

---

## 🔮 Kế hoạch Phát triển Tiếp theo (Roadmap)
- [ ] **Dynamic Subtitles (Phụ đề động):** Bổ sung các tùy chọn font chữ, viền, đổ bóng và karaoke chạy chữ từng từ theo giọng nói.
- [ ] **Hiệu ứng chuyển cảnh nâng cao:** Cung cấp nhiều bộ chuyển cảnh mượt mà thay vì hiệu ứng fade cơ bản (Slide, Zoom In/Out, Cross Dissolve...).
- [ ] **Tích hợp tìm kiếm hình ảnh miễn phí:** Kết nối API Pexels/Unsplash để lấy ảnh trực tiếp từ văn bản kịch bản.
