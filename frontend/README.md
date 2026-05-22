# 🎨 Auto Video Generator Frontend (React + Vite)

Giao diện Single Page Application (SPA) của công cụ Biên tập & Dựng Video tự động. Được xây dựng trên nền tảng React 19, Vite 8 và Ant Design 6.

## 🚀 Các công nghệ chính
- **UI Framework:** [Ant Design (v6)](https://ant.design/) - Cung cấp hệ thống UI components hiện đại, hỗ trợ Dark Mode đồng nhất.
- **Biểu tượng:** [Lucide React](https://lucide.dev/) - Hệ thống icon tối giản, sắc nét.
- **Biên dịch:** [Vite](https://vite.dev/) - Môi trường xây dựng và đóng gói siêu nhanh với HMR (Hot Module Replacement).

## 📂 Cấu trúc thư mục
```text
frontend/
├── src/
│   ├── assets/       # Các tài nguyên tĩnh (logo, ảnh mặc định)
│   ├── App.jsx       # Component chính chứa giao diện 3 cột và toàn bộ logic xử lý API
│   ├── App.css       # Các tùy chỉnh CSS riêng (scrollbars, custom animations)
│   ├── index.css     # Cấu hình Design Tokens, Reset CSS và Device Mockups (khung điện thoại)
│   └── main.jsx      # File khởi chạy ứng dụng React
├── index.html        # File template HTML chính
├── vite.config.js    # Cấu hình Vite, Alias và Proxy chuyển tiếp các API `/api`, `/uploads` sang FastAPI
└── package.json      # Danh sách dependencies và kịch bản chạy lệnh (npm scripts)
```

## 🛠️ Hướng dẫn phát triển

### 1. Cài đặt Dependencies
Chạy lệnh sau tại thư mục `frontend/` để cài đặt các thư viện Node.js cần thiết:
```bash
npm install
```

### 2. Khởi chạy Dev Server
Chạy lệnh sau để khởi chạy React ở chế độ lập trình viên:
```bash
npm run dev
```
Ứng dụng sẽ chạy tại địa chỉ: [http://localhost:5173](http://localhost:5173).  
*Lưu ý: Bạn cần chạy song song backend FastAPI tại cổng `7860` để proxy chuyển tiếp các request API hoạt động chuẩn xác.*

### 3. Biên dịch cho Production
Để đóng gói ứng dụng React thành các file HTML/JS/CSS tĩnh cung cấp cho backend FastAPI:
```bash
npm run build
```
Đầu ra sẽ tự động được xuất vào thư mục `../static/dist/`. Backend FastAPI sẽ đọc và phân phối giao diện từ thư mục này.
