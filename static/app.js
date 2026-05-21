document.addEventListener("DOMContentLoaded", () => {
    // ── Cache State ──────────────────────────────────────────────────────────
    let cache = {
        api_key: "",
        audio_path: "",
        scenes_text: "",
        language: "Tiếng Việt",
        matched_scenes: [],
        preview_mode: false,
        image_paths: []
    };

    // ── DOM Elements ─────────────────────────────────────────────────────────
    const apiKeyInput = document.getElementById("api-key");
    const audioDropzone = document.getElementById("audio-dropzone");
    const audioFileInput = document.getElementById("audio-file");
    const audioPreviewCard = document.getElementById("audio-preview-card");
    const audioNameDisp = document.getElementById("audio-name");
    const audioSizeDisp = document.getElementById("audio-size");
    const removeAudioBtn = document.getElementById("remove-audio-btn");
    
    const scenesInput = document.getElementById("scenes-input");
    const btnAnalyze = document.getElementById("btn-analyze");
    const btnClearCache = document.getElementById("btn-clear-cache");
    
    const timelineList = document.getElementById("timeline-list");
    const timelineFooter = document.getElementById("timeline-footer");
    const btnSync = document.getElementById("btn-sync");
    const exportToolbar = document.getElementById("export-toolbar");
    
    const imagesDropzone = document.getElementById("images-dropzone");
    const imageFilesInput = document.getElementById("image-files");
    const thumbnailsGrid = document.getElementById("thumbnails-grid");
    
    const settingsToggle = document.getElementById("settings-toggle");
    const settingsCard = settingsToggle.closest(".card");
    const intensitySlider = document.getElementById("intensity");
    const intensityVal = document.getElementById("intensity-val");
    const transitionSlider = document.getElementById("transition");
    const transitionVal = document.getElementById("transition-val");
    const previewModeCheckbox = document.getElementById("preview-mode");
    
    const btnRender = document.getElementById("btn-render");
    const renderStatusCard = document.getElementById("render-status-card");
    const progressBarFill = document.getElementById("progress-bar-fill");
    const progressStepText = document.getElementById("progress-step");
    const progressPercentText = document.getElementById("progress-percent");
    const consoleLogs = document.getElementById("console-logs");
    const btnClearLogs = document.getElementById("btn-clear-logs");
    
    const videoResultCard = document.getElementById("video-result-card");
    const videoPlayer = document.getElementById("video-player");
    const btnDownloadVideo = document.getElementById("btn-download-video");

    // ── Startup Initialization ───────────────────────────────────────────────
    
    // Load local storage API Key first as fallback
    const savedApiKey = localStorage.getItem("openai_api_key");
    if (savedApiKey) {
        apiKeyInput.value = savedApiKey;
        cache.api_key = savedApiKey;
    }

    loadCache();

    // ── API Key Input Handler ────────────────────────────────────────────────
    apiKeyInput.addEventListener("change", () => {
        cache.api_key = apiKeyInput.value.trim();
        localStorage.setItem("openai_api_key", cache.api_key);
    });

    // ── Accordion Settings Toggle ────────────────────────────────────────────
    settingsToggle.addEventListener("click", () => {
        settingsCard.classList.toggle("accordion-collapsed");
    });

    // Sliders Real-time Values
    intensitySlider.addEventListener("input", () => {
        intensityVal.textContent = intensitySlider.value;
    });
    transitionSlider.addEventListener("input", () => {
        transitionVal.textContent = transitionSlider.value;
    });

    // ── Drag & Drop Audio Upload ─────────────────────────────────────────────
    setupDragDrop(audioDropzone, audioFileInput, (file) => uploadAudio(file));
    
    removeAudioBtn.addEventListener("click", () => {
        cache.audio_path = "";
        audioPreviewCard.classList.add("hidden");
        audioDropzone.classList.remove("hidden");
        audioFileInput.value = "";
    });

    // ── Drag & Drop Images Upload ────────────────────────────────────────────
    setupDragDrop(imagesDropzone, imageFilesInput, (files) => uploadImages(files), true);

    // ── Action: Analyze Timestamps ───────────────────────────────────────────
    btnAnalyze.addEventListener("click", async () => {
        const apiKey = apiKeyInput.value.trim();
        const scenesText = scenesInput.value.trim();
        const language = document.querySelector('input[name="language"]:checked').value;

        if (!apiKey) {
            alert("Vui lòng nhập OpenAI API Key.");
            apiKeyInput.focus();
            return;
        }
        if (!cache.audio_path) {
            alert("Vui lòng tải lên file Audio Voiceover trước.");
            return;
        }
        if (!scenesText) {
            alert("Vui lòng nhập nội dung phân cảnh.");
            scenesInput.focus();
            return;
        }

        setLoading(btnAnalyze, true, "🔍 Đang phân tích...");
        
        try {
            const res = await fetch("/api/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    api_key: apiKey,
                    audio_path: cache.audio_path,
                    scenes_text: scenesText,
                    language: language
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Lỗi phân tích không rõ.");
            }

            const data = await res.json();
            cache.matched_scenes = data.matched_scenes;
            cache.scenes_text = scenesText;
            cache.language = language;
            
            renderTimeline(cache.matched_scenes);
            alert("✅ Phân tích hoàn tất! Vui lòng kiểm tra và chỉnh sửa ở Bước 2.");
        } catch (error) {
            console.error(error);
            alert("❌ Lỗi: " + error.message);
        } finally {
            setLoading(btnAnalyze, false, "🔍 Phân tích Timestamps");
        }
    });

    // ── Action: Sync Changes ─────────────────────────────────────────────────
    btnSync.addEventListener("click", async () => {
        const updatedScenes = readTimelineInputs();
        const apiKey = apiKeyInput.value.trim();
        const scenesText = scenesInput.value.trim();
        const language = document.querySelector('input[name="language"]:checked').value;
        const previewMode = previewModeCheckbox.checked;

        setLoading(btnSync, true, "🔄 Đang đồng bộ...");
        
        try {
            const res = await fetch("/api/sync", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    api_key: apiKey,
                    audio_path: cache.audio_path,
                    scenes_text: scenesText,
                    language: language,
                    matched_scenes: updatedScenes,
                    preview_mode: previewMode
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Lỗi đồng bộ không rõ.");
            }

            const data = await res.json();
            cache.matched_scenes = data.matched_scenes;
            renderTimeline(cache.matched_scenes);
            
            // Show custom toast notification
            showToast("Đã cập nhật & đồng bộ timestamp thành công!");
        } catch (error) {
            console.error(error);
            alert("❌ Lỗi đồng bộ: " + error.message);
        } finally {
            setLoading(btnSync, false, "🔄 Cập nhật & Đồng bộ thay đổi");
        }
    });

    // ── Action: Clear Cache ──────────────────────────────────────────────────
    btnClearCache.addEventListener("click", async () => {
        if (!confirm("Bạn có chắc chắn muốn xóa toàn bộ cache và các tệp tải lên?")) {
            return;
        }

        try {
            const res = await fetch("/api/clear-cache", { method: "POST" });
            if (res.ok) {
                localStorage.removeItem("openai_api_key");
                apiKeyInput.value = "";
                scenesInput.value = "";
                audioPreviewCard.classList.add("hidden");
                audioDropzone.classList.remove("hidden");
                thumbnailsGrid.classList.add("hidden");
                thumbnailsGrid.innerHTML = "";
                imagesDropzone.classList.remove("hidden");
                timelineList.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">📊</div>
                        <p>Chưa có dữ liệu phân tích.</p>
                        <p class="sub">Hãy thực hiện Bước 1 để tự động tạo và điều chỉnh Timestamps.</p>
                    </div>`;
                timelineFooter.classList.add("hidden");
                exportToolbar.classList.add("hidden");
                videoResultCard.classList.add("hidden");
                renderStatusCard.classList.add("hidden");
                
                cache = {
                    api_key: "",
                    audio_path: "",
                    scenes_text: "",
                    language: "Tiếng Việt",
                    matched_scenes: [],
                    preview_mode: false,
                    image_paths: []
                };
                
                alert("🗑️ Đã xóa sạch dữ liệu cache thành công.");
            }
        } catch (error) {
            alert("Lỗi khi xóa cache: " + error.message);
        }
    });

    // ── Action: Export Subtitles ─────────────────────────────────────────────
    document.querySelectorAll(".btn-export").forEach(btn => {
        btn.addEventListener("click", () => {
            const format = btn.getAttribute("data-format");
            window.open(`/api/export?format=${format}`, "_blank");
        });
    });

    // ── Action: Render Video (SSE stream reader) ─────────────────────────────
    btnRender.addEventListener("click", async () => {
        if (!cache.audio_path) {
            alert("Vui lòng tải lên Audio trước.");
            return;
        }
        if (cache.image_paths.length === 0) {
            alert("Vui lòng tải lên ít nhất một ảnh phân cảnh.");
            return;
        }
        if (cache.matched_scenes.length === 0) {
            alert("Chưa có dữ liệu phân cảnh. Vui lòng phân tích trước.");
            return;
        }

        // Hiện trạng thái render
        renderStatusCard.classList.remove("hidden");
        videoResultCard.classList.add("hidden");
        progressBarFill.style.width = "0%";
        progressPercentText.textContent = "0%";
        progressStepText.textContent = "Khởi động tiến trình render...";
        consoleLogs.textContent = "";
        appendLog("→ Bắt đầu kết nối với render engine...");

        setLoading(btnRender, true, "🎬 Đang dựng video...");

        try {
            // Tạo request payload
            const payload = {
                audio_path: cache.audio_path,
                image_paths: cache.image_paths,
                resolution: document.querySelector('input[name="resolution"]:checked').value,
                intensity: parseFloat(intensitySlider.value),
                transition_dur: parseFloat(transitionSlider.value),
                preview_mode: previewModeCheckbox.checked
            };

            const response = await fetch("/api/render", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error("Lỗi kết nối render server.");
            }

            // Đọc SSE Stream sử dụng ReadableStream
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value);
                const lines = buffer.split("\n\n");
                buffer = lines.pop(); // Giữ lại phần dư chưa kết thúc dòng

                for (const line of lines) {
                    if (line.trim().startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.trim().slice(6));
                            handleRenderProgress(data);
                        } catch (e) {
                            console.error("Lỗi parse SSE JSON: ", e);
                        }
                    }
                }
            }

        } catch (error) {
            appendLog(`❌ Lỗi hệ thống: ${error.message}`);
            alert("Render video thất bại: " + error.message);
        } finally {
            setLoading(btnRender, false, "🎬 Bắt đầu Tạo Video");
        }
    });

    btnClearLogs.addEventListener("click", () => {
        consoleLogs.textContent = "";
    });

    // ── Helper Functions ─────────────────────────────────────────────────────

    async function loadCache() {
        try {
            const res = await fetch("/api/load-cache");
            if (!res.ok) return;
            const data = await res.json();
            
            cache = data;

            // Khôi phục form
            if (data.api_key) {
                apiKeyInput.value = data.api_key;
                localStorage.setItem("openai_api_key", data.api_key);
            }
            if (data.scenes_text) {
                scenesInput.value = data.scenes_text;
            }
            if (data.language) {
                const rad = document.querySelector(`input[name="language"][value="${data.language}"]`);
                if (rad) rad.checked = true;
            }
            if (data.preview_mode) {
                previewModeCheckbox.checked = data.preview_mode;
            }

            // Khôi phục file Audio
            if (data.audio_path && data.audio_filename) {
                audioNameDisp.textContent = data.audio_filename;
                audioSizeDisp.textContent = "Local Cached File";
                audioPreviewCard.classList.remove("hidden");
                audioDropzone.classList.add("hidden");
            }

            // Khôi phục ảnh
            if (data.image_paths && data.image_paths.length > 0) {
                renderThumbnails(data.image_paths);
            }

            // Khôi phục Timeline
            if (data.matched_scenes && data.matched_scenes.length > 0) {
                renderTimeline(data.matched_scenes);
            }

        } catch (error) {
            console.error("Lỗi tải cache: ", error);
        }
    }

    function setupDragDrop(zone, input, onUpload, isMultiple = false) {
        zone.addEventListener("click", () => input.click());

        zone.addEventListener("dragover", (e) => {
            e.preventDefault();
            zone.classList.add("dragover");
        });

        ["dragleave", "drop"].forEach(eventName => {
            zone.addEventListener(eventName, () => zone.classList.remove("dragover"));
        });

        zone.addEventListener("drop", (e) => {
            e.preventDefault();
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                if (isMultiple) {
                    onUpload(files);
                } else {
                    onUpload(files[0]);
                }
            }
        });

        input.addEventListener("change", () => {
            const files = input.files;
            if (files.length > 0) {
                if (isMultiple) {
                    onUpload(files);
                } else {
                    onUpload(files[0]);
                }
            }
        });
    }

    async function uploadAudio(file) {
        audioNameDisp.textContent = file.name;
        audioSizeDisp.textContent = (file.size / 1024 / 1024).toFixed(2) + " MB";
        audioPreviewCard.classList.remove("hidden");
        audioDropzone.classList.add("hidden");

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/upload-audio", {
                method: "POST",
                body: formData
            });
            const data = await res.json();
            if (data.status === "success") {
                cache.audio_path = data.path;
                showToast("Đã tải lên audio thành công!");
            }
        } catch (e) {
            alert("Lỗi tải lên audio: " + e.message);
            audioPreviewCard.classList.add("hidden");
            audioDropzone.classList.remove("hidden");
        }
    }

    async function uploadImages(files) {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append("files", files[i]);
        }

        thumbnailsGrid.classList.remove("hidden");
        thumbnailsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; font-size: 0.8rem; padding: 20px; color: var(--text-secondary)">Đang tải lên ${files.length} ảnh...</div>`;

        try {
            const res = await fetch("/api/upload-images", {
                method: "POST",
                body: formData
            });
            const data = await res.json();
            if (data.status === "success") {
                cache.image_paths = data.paths;
                renderThumbnails(data.paths);
                showToast(`Đã tải lên ${data.paths.length} ảnh phân cảnh!`);
            }
        } catch (e) {
            alert("Lỗi tải lên danh sách ảnh: " + e.message);
            thumbnailsGrid.classList.add("hidden");
            thumbnailsGrid.innerHTML = "";
        }
    }

    function renderThumbnails(paths) {
        thumbnailsGrid.classList.remove("hidden");
        thumbnailsGrid.innerHTML = "";
        
        paths.forEach((path, idx) => {
            const basename = path.substring(path.lastIndexOf('/') + 1);
            
            const wrapper = document.createElement("div");
            wrapper.className = "thumbnail-wrapper";
            
            // Serve từ server route /uploads
            const relativeUrl = "/uploads/images/" + encodeURIComponent(basename);
            
            wrapper.innerHTML = `
                <img src="${relativeUrl}" alt="${basename}" loading="lazy">
                <span class="thumbnail-badge">${String(idx + 1).padStart(3, '0')}</span>
            `;
            thumbnailsGrid.appendChild(wrapper);
        });
    }

    function renderTimeline(scenes) {
        if (!scenes || scenes.length === 0) {
            timelineList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📊</div>
                    <p>Chưa có dữ liệu phân tích.</p>
                    <p class="sub">Hãy thực hiện Bước 1 để tự động tạo và điều chỉnh Timestamps.</p>
                </div>`;
            timelineFooter.classList.add("hidden");
            exportToolbar.classList.add("hidden");
            return;
        }

        timelineList.innerHTML = "";
        timelineFooter.classList.remove("hidden");
        exportToolbar.classList.remove("hidden");

        scenes.forEach((scene, index) => {
            const card = document.createElement("div");
            card.className = "scene-card";
            card.dataset.index = index;

            // Đánh giá chất lượng khớp
            let matchClass = "poor";
            let matchText = "Kém";
            if (scene.match_pct >= 60) {
                matchClass = "good";
                matchText = "Tốt";
            } else if (scene.match_pct >= 30) {
                matchClass = "medium";
                matchText = "Trung bình";
            }

            card.innerHTML = `
                <div class="scene-card-header-compact">
                    <div class="scene-meta">
                        <span class="scene-badge">#${scene.screen}</span>
                        <span class="match-badge-mini ${matchClass}" title="Độ khớp: ${scene.match_pct}% (${matchText})">${scene.match_pct}%</span>
                    </div>
                    <div class="scene-time-compact">
                        <div class="time-mini-input">
                            <span class="time-prefix">In:</span>
                            <input type="number" class="time-number-input-mini time-start" value="${scene.start}" step="0.05" min="0">
                        </div>
                        <span class="time-separator">→</span>
                        <div class="time-mini-input">
                            <span class="time-prefix">Out:</span>
                            <input type="number" class="time-number-input-mini time-end" value="${scene.end}" step="0.05" min="0">
                        </div>
                        <div class="duration-badge-mini">
                            <span class="dur-value">${scene.duration.toFixed(2)}s</span>
                        </div>
                    </div>
                </div>
                <div class="scene-card-body-compact">
                    <input type="text" class="scene-text-input" value="${escapeHtml(scene.scene)}">
                </div>
            `;

            // Lắng nghe sự kiện để cập nhật thời lượng theo thời gian thực
            const inputStart = card.querySelector(".time-start");
            const inputEnd = card.querySelector(".time-end");
            const durValue = card.querySelector(".dur-value");

            const recalculateDur = () => {
                const start = parseFloat(inputStart.value) || 0;
                const end = parseFloat(inputEnd.value) || 0;
                const duration = Math.max(0, end - start);
                durValue.textContent = duration.toFixed(2) + "s";
                
                const endWrapper = inputEnd.closest(".time-mini-input");
                // Cảnh báo nếu thời gian kết thúc nhỏ hơn bắt đầu
                if (end < start) {
                    if (endWrapper) endWrapper.style.borderColor = "var(--color-poor)";
                } else {
                    if (endWrapper) endWrapper.style.borderColor = "";
                }
            };

            inputStart.addEventListener("input", recalculateDur);
            inputEnd.addEventListener("input", recalculateDur);

            timelineList.appendChild(card);
        });
    }

    function readTimelineInputs() {
        const cards = timelineList.querySelectorAll(".scene-card");
        const updatedScenes = [];
        
        cards.forEach(card => {
            const idx = parseInt(card.dataset.index);
            const textInput = card.querySelector(".scene-text-input").value.trim();
            const startVal = parseFloat(card.querySelector(".time-start").value) || 0;
            const endVal = parseFloat(card.querySelector(".time-end").value) || 0;
            
            const orig = cache.matched_scenes[idx];
            
            updatedScenes.push({
                screen: orig.screen,
                scene: textInput,
                start: startVal,
                end: endVal,
                duration: endVal - startVal,
                whisper_text: orig.whisper_text,
                match_pct: orig.match_pct
            });
        });
        
        return updatedScenes;
    }

    function handleRenderProgress(data) {
        // data dạng: { "step": "...", "pct": 80, "video_url": "..." }
        if (data.step) {
            appendLog(`[${data.pct}%] ${data.step}`);
            progressStepText.textContent = data.step;
        }
        
        if (data.pct !== undefined) {
            progressBarFill.style.width = data.pct + "%";
            progressPercentText.textContent = data.pct + "%";
        }

        if (data.video_url) {
            // Hiển thị trình phát video
            videoResultCard.classList.remove("hidden");
            videoPlayer.src = data.video_url;
            btnDownloadVideo.href = data.video_url;
            
            // Cuộn giao diện đến mục xem video
            videoResultCard.scrollIntoView({ behavior: 'smooth' });
        }
    }

    function appendLog(message) {
        consoleLogs.textContent += message + "\n";
        consoleLogs.scrollTop = consoleLogs.scrollHeight; // Tự động cuộn xuống cuối
    }

    function setLoading(button, isLoading, text) {
        button.disabled = isLoading;
        if (isLoading) {
            button.classList.add("loading");
            button.dataset.origHtml = button.innerHTML;
            button.innerHTML = `<span class="spinner"></span> ${text}`;
        } else {
            button.classList.remove("loading");
            if (button.dataset.origHtml) {
                button.innerHTML = button.dataset.origHtml;
            }
        }
    }

    function showToast(message) {
        // Toast style đơn giản
        const toast = document.createElement("div");
        toast.style.position = "fixed";
        toast.style.bottom = "20px";
        toast.style.right = "20px";
        toast.style.backgroundColor = "#10b981";
        toast.style.color = "white";
        toast.style.padding = "12px 24px";
        toast.style.borderRadius = "8px";
        toast.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
        toast.style.fontSize = "0.85rem";
        toast.style.fontWeight = "600";
        toast.style.zIndex = "1000";
        toast.style.transition = "all 0.3s ease";
        toast.style.transform = "translateY(100px)";
        toast.style.opacity = "0";

        toast.textContent = "✅ " + message;
        document.body.appendChild(toast);

        // Animation in
        setTimeout(() => {
            toast.style.transform = "translateY(0)";
            toast.style.opacity = "1";
        }, 50);

        // Dismiss after 3s
        setTimeout(() => {
            toast.style.transform = "translateY(20px)";
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    function escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
