/* ==========================================================================
   EcoSort AI - Scanner JavaScript
   Handles image upload, displays results with bounding boxes,
   and manages the save-to-database workflow.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const imageContainer = document.getElementById('imageContainer');
    const resultImage = document.getElementById('resultImage');
    const bboxCanvas = document.getElementById('bboxCanvas');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const errorMsg = document.getElementById('errorMsg');
    const reuploadBtn = document.getElementById('reuploadBtn');
    const summaryPanel = document.getElementById('summaryPanel');
    const itemList = document.getElementById('itemList');
    const itemsContainer = document.getElementById('itemsContainer');
    const saveBtn = document.getElementById('saveBtn');
    const saveStatus = document.getElementById('saveStatus');

    let currentScanData = null;

    // --- Category color map (must match config.py WASTE_CATEGORIES) ---
    const CATEGORY_COLORS = {
        plastic: '#3498db',
        paper: '#f1c40f',
        cardboard: '#e67e22',
        glass: '#1abc9c',
        metal: '#95a5a6',
        trash: '#e74c3c',
    };

    // --- Click to open file picker ---
    uploadZone.addEventListener('click', () => fileInput.click());

    // --- File selected via picker ---
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // --- Drag and drop ---
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // --- Re-upload button ---
    reuploadBtn.addEventListener('click', () => {
        uploadZone.classList.remove('hidden');
        imageContainer.classList.add('hidden');
        summaryPanel.classList.add('hidden');
        itemList.classList.add('hidden');
        currentScanData = null;
        fileInput.value = '';
    });

    // --- Save button ---
    saveBtn.addEventListener('click', saveScan);

    // ==================================================================
    // Handle file upload and call the scan API
    // ==================================================================
    function handleFile(file) {
        // Validate file type
        const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            showError('รองรับเฉพาะไฟล์ PNG, JPG, JPEG, WEBP');
            return;
        }

        // Validate file size (16 MB max)
        if (file.size > 16 * 1024 * 1024) {
            showError('ขนาดไฟล์ต้องไม่เกิน 16 MB');
            return;
        }

        hideError();
        uploadZone.classList.add('hidden');
        loadingOverlay.classList.remove('hidden');

        const formData = new FormData();
        formData.append('image', file);

        fetch('/api/scan', {
            method: 'POST',
            body: formData,
        })
            .then(res => res.json())
            .then(data => {
                loadingOverlay.classList.add('hidden');
                if (data.error) {
                    showError(data.error);
                    // If we got an image URL, still show it
                    if (data.image_url) {
                        showImage(data.image_url);
                    }
                    return;
                }
                displayResults(data);
            })
            .catch(err => {
                loadingOverlay.classList.add('hidden');
                showError('เกิดข้อผิดพลาดในการเชื่อมต่อกับเซิร์ฟเวอร์: ' + err.message);
                uploadZone.classList.remove('hidden');
            });
    }

    // ==================================================================
    // Display the uploaded image with bounding boxes
    // ==================================================================
    function showImage(imageUrl) {
        resultImage.src = imageUrl;
        imageContainer.classList.remove('hidden');
    }

    // ==================================================================
    // Display full scan results
    // ==================================================================
    function displayResults(data) {
        currentScanData = data;
        showImage(data.image_url);

        // Draw bounding boxes after image loads
        resultImage.onload = () => {
            drawBoundingBoxes(data.detections);
        };

        // Update summary
        updateSummary(data);

        // Update item list
        updateItemList(data.detections);

        summaryPanel.classList.remove('hidden');
        itemList.classList.remove('hidden');
        saveBtn.disabled = false;
    }

    // ==================================================================
    // Draw bounding boxes on the canvas
    // ==================================================================
    function drawBoundingBoxes(detections) {
        const img = resultImage;
        const naturalW = img.naturalWidth;
        const naturalH = img.naturalHeight;
        const displayW = img.clientWidth;
        const displayH = img.clientHeight;

        // Scale factors from natural to display size
        const scaleX = displayW / naturalW;
        const scaleY = displayH / naturalH;

        bboxCanvas.width = displayW;
        bboxCanvas.height = displayH;

        const ctx = bboxCanvas.getContext('2d');
        ctx.clearRect(0, 0, displayW, displayH);

        detections.forEach((det, idx) => {
            const bbox = det.bbox;
            // Handle both array and object formats
            let x1, y1, x2, y2;
            if (Array.isArray(bbox)) {
                [x1, y1, x2, y2] = bbox;
            } else {
                x1 = bbox.x1; y1 = bbox.y1; x2 = bbox.x2; y2 = bbox.y2;
            }

            const dx = x1 * scaleX;
            const dy = y1 * scaleY;
            const dw = (x2 - x1) * scaleX;
            const dh = (y2 - y1) * scaleY;

            const color = CATEGORY_COLORS[det.category] || '#999';

            // Draw box
            ctx.strokeStyle = color;
            ctx.lineWidth = 3;
            ctx.strokeRect(dx, dy, dw, dh);

            // Draw label background
            const label = `${det.category_th} (${(det.confidence * 100).toFixed(0)}%)`;
            ctx.font = 'bold 14px Segoe UI, sans-serif';
            const textW = ctx.measureText(label).width;
            const labelH = 22;
            const labelY = dy > labelH ? dy - labelH : dy;

            ctx.fillStyle = color;
            ctx.fillRect(dx, labelY, textW + 10, labelH);

            // Draw label text
            ctx.fillStyle = 'white';
            ctx.fillText(label, dx + 5, labelY + 16);

            // Draw item number
            ctx.fillStyle = 'white';
            ctx.font = 'bold 16px Segoe UI, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`#${idx + 1}`, dx + 12, dy + 20);
            ctx.textAlign = 'left';
        });
    }

    // ==================================================================
    // Update summary panel
    // ==================================================================
    function updateSummary(data) {
        document.getElementById('sumTotal').textContent = data.total_items;
        document.getElementById('sumClean').textContent = data.clean_count;
        document.getElementById('sumContaminated').textContent = data.contaminated_count;
        document.getElementById('sumRecyclable').textContent = data.recyclable_count;
        document.getElementById('sumTime').textContent = data.processing_time;

        // CO2 and points
        if (data.carbon) {
            document.getElementById('sumCO2').textContent = data.carbon.total_co2.toFixed(4);
        }
        if (data.points) {
            document.getElementById('sumPoints').textContent = data.points.points;
        }

        // Model mode display
        document.getElementById('sumDetectorMode').textContent = data.model_mode.detector;
        document.getElementById('sumClassifierMode').textContent = data.model_mode.classifier;
    }

    // ==================================================================
    // Build the item list
    // ==================================================================
    function updateItemList(detections) {
        itemsContainer.innerHTML = '';

        detections.forEach((det, idx) => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'detected-item';
            itemDiv.dataset.index = idx;

            const color = CATEGORY_COLORS[det.category] || '#999';
            const qualityClass = det.quality === 'clean' ? 'quality-clean' : 'quality-contaminated';
            const qualityText = det.quality === 'clean' ? '✨ สะอาด' : '⚠️ ปนเปื้อน';

            itemDiv.innerHTML = `
                <div class="item-header">
                    <span class="item-type">
                        <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${color};"></span>
                        #${idx + 1} ${det.category_th}
                    </span>
                    <span class="item-confidence">ความมั่นใจ: ${(det.confidence * 100).toFixed(1)}%</span>
                </div>
                <span class="quality-badge ${qualityClass}">
                    ${qualityText} ( ${(det.quality_confidence * 100).toFixed(0)}% )
                </span>
                <div class="item-bin">🗑️ ถังที่แนะนำ: ${det.suggested_bin}</div>
                <div class="item-bin">
                    ${det.recyclable ? '♻️ รีไซเคิลได้' : '🚮 ขยะทั่วไป'}
                </div>
                <div class="item-recommendation">${det.recommendation}</div>
                <a class="find-drop-link" href="/recycling-map?category=${det.recyclable ? det.category : 'trash'}" target="_blank">📍 หาจุดทิ้งใกล้ฉัน</a>
            `;

            // Highlight item on hover
            itemDiv.addEventListener('mouseenter', () => {
                highlightBox(idx);
            });
            itemDiv.addEventListener('mouseleave', () => {
                drawBoundingBoxes(detections);
            });

            itemsContainer.appendChild(itemDiv);
        });
    }

    // ==================================================================
    // Highlight a specific bounding box (on item hover)
    // ==================================================================
    function highlightBox(itemIdx) {
        if (!currentScanData) return;
        const detections = currentScanData.detections;
        const img = resultImage;
        const naturalW = img.naturalWidth;
        const naturalH = img.naturalHeight;
        const displayW = img.clientWidth;
        const displayH = img.clientHeight;
        const scaleX = displayW / naturalW;
        const scaleY = displayH / naturalH;

        bboxCanvas.width = displayW;
        bboxCanvas.height = displayH;
        const ctx = bboxCanvas.getContext('2d');
        ctx.clearRect(0, 0, displayW, displayH);

        detections.forEach((det, idx) => {
            const bbox = det.bbox;
            let x1, y1, x2, y2;
            if (Array.isArray(bbox)) {
                [x1, y1, x2, y2] = bbox;
            } else {
                x1 = bbox.x1; y1 = bbox.y1; x2 = bbox.x2; y2 = bbox.y2;
            }

            const dx = x1 * scaleX;
            const dy = y1 * scaleY;
            const dw = (x2 - x1) * scaleX;
            const dh = (y2 - y1) * scaleY;
            const color = CATEGORY_COLORS[det.category] || '#999';

            if (idx === itemIdx) {
                // Highlighted box: thicker + semi-transparent fill
                ctx.fillStyle = color + '33';
                ctx.fillRect(dx, dy, dw, dh);
                ctx.strokeStyle = color;
                ctx.lineWidth = 5;
                ctx.strokeRect(dx, dy, dw, dh);
            } else {
                // Dimmed boxes
                ctx.strokeStyle = color + '55';
                ctx.lineWidth = 1.5;
                ctx.strokeRect(dx, dy, dw, dh);
            }
        });
    }

    // ==================================================================
    // Save scan results to database
    // ==================================================================
    function saveScan() {
        if (!currentScanData) return;

        saveBtn.disabled = true;
        saveBtn.textContent = '⏳ กำลังบันทึก...';
        saveStatus.classList.add('hidden');

        fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentScanData),
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    saveStatus.textContent = '✅ บันทึกสำเร็จ (ID: ' + data.scan_id + ')';
                    saveStatus.className = 'save-status success';
                    saveBtn.textContent = '✅ บันทึกแล้ว';
                    if (data.user_points !== null && data.user_points !== undefined) {
                        const a = document.createElement('a');
                        a.href = '/waste-planner';
                        a.className = 'plan-link';
                        a.textContent = '🗂️ สร้างแผนจัดการขยะจากการสแกนนี้ →';
                        saveStatus.appendChild(a);
                    }
                } else {
                    saveStatus.textContent = '❌ ' + (data.error || 'บันทึกไม่สำเร็จ');
                    saveStatus.className = 'save-status error';
                    saveBtn.disabled = false;
                    saveBtn.textContent = '💾 บันทึกผลการสแกน';
                }
                saveStatus.classList.remove('hidden');
            })
            .catch(err => {
                saveStatus.textContent = '❌ ข้อผิดพลาด: ' + err.message;
                saveStatus.className = 'save-status error';
                saveStatus.classList.remove('hidden');
                saveBtn.disabled = false;
                saveBtn.textContent = '💾 บันทึกผลการสแกน';
            });
    }

    // ==================================================================
    // Error helpers
    // ==================================================================
    function showError(msg) {
        errorMsg.textContent = msg;
        errorMsg.classList.remove('hidden');
    }
    function hideError() {
        errorMsg.classList.add('hidden');
    }
});
