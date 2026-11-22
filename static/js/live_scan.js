/* ==========================================================================
   EcoSort AI - Live Camera Scanner JavaScript
   Real-time waste detection using WebRTC + YOLO via the /api/scan-live API.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    const video       = document.getElementById('cameraVideo');
    const canvas      = document.getElementById('cameraCanvas');
    const placeholder = document.getElementById('cameraPlaceholder');
    const startBtn    = document.getElementById('startCameraBtn');
    const stopBtn     = document.getElementById('stopCameraBtn');
    const scanNowBtn  = document.getElementById('scanNowBtn');
    const autoToggle  = document.getElementById('autoScanToggle');
    const statusDiv   = document.getElementById('liveScanStatus');
    const summaryDiv  = document.getElementById('liveSummary');
    const detectionsDiv = document.getElementById('liveDetections');
    const emptyDiv    = document.getElementById('liveEmpty');
    const sessionStatsDiv = document.getElementById('sessionStats');

    let stream = null;
    let autoScanInterval = null;
    let isScanning = false;
    let lastScanData = null;   // เก็บผลสแกนล่าสุดไว้เพื่อบันทึก

    const session = { scans: 0, items: 0, co2: 0, points: 0 };

    const CATEGORY_COLORS = {
        plastic:   '#3498db',
        paper:     '#f1c40f',
        cardboard: '#e67e22',
        glass:     '#1abc9c',
        metal:     '#95a5a6',
        trash:     '#e74c3c',
    };

    // -----------------------------------------------------------------------
    // Start Camera
    // -----------------------------------------------------------------------
    startBtn.addEventListener('click', async () => {
        try {
            // Try back-facing first (mobile), fall back to any camera (laptop)
            let mediaStream;
            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'environment' },
                });
            } catch {
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    video: { width: { ideal: 640 }, height: { ideal: 480 } },
                });
            }

            stream = mediaStream;
            video.srcObject = stream;

            // Wait for video metadata so we know the real dimensions
            video.onloadedmetadata = () => {
                canvas.width  = video.videoWidth  || 640;
                canvas.height = video.videoHeight || 480;
            };

            placeholder.classList.add('hidden');
            startBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
            scanNowBtn.classList.remove('hidden');

        } catch (err) {
            alert(
                'ไม่สามารถเปิดกล้องได้: ' + err.message +
                '\n\nกรุณา:\n1. อนุญาตการเข้าถึงกล้องในเบราว์เซอร์\n2. เปิดผ่าน localhost (ไม่ใช่ไฟล์โดยตรง)'
            );
        }
    });

    // -----------------------------------------------------------------------
    // Stop Camera
    // -----------------------------------------------------------------------
    stopBtn.addEventListener('click', stopCamera);

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(t => t.stop());
            stream = null;
        }
        if (autoScanInterval) {
            clearInterval(autoScanInterval);
            autoScanInterval = null;
            autoToggle.checked = false;
        }
        video.srcObject = null;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        placeholder.classList.remove('hidden');
        startBtn.classList.remove('hidden');
        stopBtn.classList.add('hidden');
        scanNowBtn.classList.add('hidden');
    }

    // -----------------------------------------------------------------------
    // Manual scan button
    // -----------------------------------------------------------------------
    scanNowBtn.addEventListener('click', () => {
        if (!isScanning) captureAndScan();
    });

    // -----------------------------------------------------------------------
    // Auto-scan toggle
    // -----------------------------------------------------------------------
    autoToggle.addEventListener('change', () => {
        if (autoToggle.checked && stream) {
            autoScanInterval = setInterval(() => {
                if (!isScanning) captureAndScan();
            }, 3000);
        } else {
            clearInterval(autoScanInterval);
            autoScanInterval = null;
        }
    });

    // -----------------------------------------------------------------------
    // Capture one frame and call /api/scan-live
    // -----------------------------------------------------------------------
    async function captureAndScan() {
        if (!stream || isScanning) return;
        isScanning = true;
        statusDiv.classList.remove('hidden');

        // Draw current video frame onto a temp canvas
        const w = video.videoWidth  || 640;
        const h = video.videoHeight || 480;

        const tmp = document.createElement('canvas');
        tmp.width  = w;
        tmp.height = h;
        tmp.getContext('2d').drawImage(video, 0, 0, w, h);

        tmp.toBlob(async (blob) => {
            if (!blob) {
                isScanning = false;
                statusDiv.classList.add('hidden');
                return;
            }

            const formData = new FormData();
            formData.append('image', blob, 'frame.jpg');

            try {
                const res  = await fetch('/api/scan-live', { method: 'POST', body: formData });
                const data = await res.json();

                if (data.success) {
                    lastScanData = data;    // เก็บผลไว้สำหรับบันทึก
                    updateSummary(data);
                    drawBoundingBoxes(data.detections, w, h);
                    renderDetectionList(data.detections);

                    // เปิดปุ่มบันทึกทันทีที่มีผล
                    const saveBtn = document.getElementById('saveLiveScanBtn');
                    if (saveBtn) {
                        saveBtn.disabled = false;
                        saveBtn.textContent = '💾 บันทึกผลการสแกนนี้';
                    }
                    const saveStatus = document.getElementById('saveLiveStatus');
                    if (saveStatus) saveStatus.classList.add('hidden');
                }
            } catch (err) {
                console.error('Live scan error:', err);
            } finally {
                isScanning = false;
                statusDiv.classList.add('hidden');
            }
        }, 'image/jpeg', 0.85);
    }

    // -----------------------------------------------------------------------
    // Draw bounding boxes on the overlay canvas
    // -----------------------------------------------------------------------
    function drawBoundingBoxes(detections, naturalW, naturalH) {
        const ctx = canvas.getContext('2d');

        // Make sure canvas size matches video
        canvas.width  = naturalW || video.videoWidth  || 640;
        canvas.height = naturalH || video.videoHeight || 480;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!detections || detections.length === 0) return;

        // Scale factors: detection coords are on the original frame
        const scaleX = canvas.width  / (naturalW || canvas.width);
        const scaleY = canvas.height / (naturalH || canvas.height);

        detections.forEach((det) => {
            const bbox = det.bbox;
            let x1, y1, x2, y2;
            if (Array.isArray(bbox)) {
                [x1, y1, x2, y2] = bbox;
            } else {
                x1 = bbox.x1; y1 = bbox.y1; x2 = bbox.x2; y2 = bbox.y2;
            }

            x1 = x1 * scaleX;
            y1 = y1 * scaleY;
            const bw = (x2 - bbox.x1 ?? x2) * scaleX - x1 + x1;
            const bh = (y2 - bbox.y1 ?? y2) * scaleY - y1 + y1;

            // Recalculate correctly
            const dx = (Array.isArray(bbox) ? bbox[0] : bbox.x1) * scaleX;
            const dy = (Array.isArray(bbox) ? bbox[1] : bbox.y1) * scaleY;
            const dw = ((Array.isArray(bbox) ? bbox[2] : bbox.x2) - (Array.isArray(bbox) ? bbox[0] : bbox.x1)) * scaleX;
            const dh = ((Array.isArray(bbox) ? bbox[3] : bbox.y2) - (Array.isArray(bbox) ? bbox[1] : bbox.y1)) * scaleY;

            const color = CATEGORY_COLORS[det.category] || '#999999';

            // Box
            ctx.strokeStyle = color;
            ctx.lineWidth   = 3;
            ctx.strokeRect(dx, dy, dw, dh);

            // Semi-transparent fill
            ctx.fillStyle = color + '22';
            ctx.fillRect(dx, dy, dw, dh);

            // Label background
            const label = `${det.category_th} ${(det.confidence * 100).toFixed(0)}%`;
            ctx.font = 'bold 14px "Segoe UI", sans-serif';
            const textW  = ctx.measureText(label).width;
            const labelY = dy >= 26 ? dy - 26 : dy;

            ctx.fillStyle = color;
            ctx.fillRect(dx, labelY, textW + 12, 24);

            // Label text
            ctx.fillStyle = 'white';
            ctx.fillText(label, dx + 6, labelY + 17);

            // Quality badge corner
            const qIcon = det.quality === 'clean' ? '✨' : '⚠️';
            ctx.font = '14px sans-serif';
            ctx.fillText(qIcon, dx + 4, dy + 20);
        });
    }

    // -----------------------------------------------------------------------
    // Update the summary panel numbers
    // -----------------------------------------------------------------------
    function updateSummary(data) {
        const total  = data.total_items          || 0;
        const clean  = data.clean_count          || 0;
        const contam = data.contaminated_count   || 0;
        const co2    = data.co2_saved            || 0;
        // data.points อาจเป็น object {points: 5, ...} หรือ number ตรงๆ
        const points = (typeof data.points === 'object' && data.points !== null)
                        ? (data.points.points || 0)
                        : (data.points || 0);

        document.getElementById('liveTotal').textContent  = total;
        document.getElementById('liveClean').textContent  = clean;
        document.getElementById('liveContam').textContent = contam;
        document.getElementById('liveCO2').textContent    = co2.toFixed(4);
        document.getElementById('livePoints').textContent = points;

        summaryDiv.classList.remove('hidden');
        emptyDiv.classList.add('hidden');

        // Accumulate session totals
        session.scans  += 1;
        session.items  += total;
        session.co2    += co2;
        session.points += points;

        document.getElementById('sessionScans').textContent  = session.scans;
        document.getElementById('sessionItems').textContent  = session.items;
        document.getElementById('sessionCO2').textContent    = session.co2.toFixed(4);
        document.getElementById('sessionPoints').textContent = session.points;
        sessionStatsDiv.classList.remove('hidden');
    }

    // -----------------------------------------------------------------------
    // Render the list of detected items — full detail same as Scanner page
    // -----------------------------------------------------------------------
    function renderDetectionList(detections) {
        if (!detections || detections.length === 0) {
            detectionsDiv.innerHTML = '<p class="no-detection">ไม่พบวัตถุในภาพนี้</p>';
            return;
        }

        detectionsDiv.innerHTML = detections.map((det, i) => {
            const color      = CATEGORY_COLORS[det.category] || '#4ade80';
            const qClass     = det.quality === 'clean' ? 'quality-clean' : 'quality-contaminated';
            const qText      = det.quality === 'clean' ? '✨ สะอาด' : '⚠️ ปนเปื้อน';
            const qConfPct   = det.quality_confidence != null
                                 ? (det.quality_confidence * 100).toFixed(0) + '%' : '';
            const detConfPct = (det.confidence * 100).toFixed(1);
            const recycleTxt = det.recyclable
                ? '<span class="item-recycle recycle-yes">♻️ รีไซเคิลได้</span>'
                : '<span class="item-recycle recycle-no">🚮 ขยะทั่วไป</span>';

            // Preparation steps list (if available)
            let prepHtml = '';
            if (det.preparation && det.preparation.length > 0) {
                const items = det.preparation
                    .map(s => `<li>${s}</li>`)
                    .join('');
                prepHtml = `
                    <div class="item-section">
                        <div class="item-section-title">วิธีเตรียมก่อนทิ้ง</div>
                        <ul class="item-prep-list">${items}</ul>
                    </div>`;
            }

            // Full recommendation text (if available, trim to 2 lines on mobile via CSS)
            let recHtml = '';
            if (det.recommendation) {
                // Keep only the "การจัดการ:" line for a concise summary
                const lines = det.recommendation.split('\n').filter(l => l.trim());
                const mgmtLine = lines.find(l => l.startsWith('การจัดการ:'));
                if (mgmtLine) {
                    recHtml = `<div class="item-management">${mgmtLine}</div>`;
                }
            }

            return `
            <div class="live-item live-item-full">
                <!-- Header row: name + confidence -->
                <div class="live-item-header">
                    <span class="item-type">
                        <span class="item-dot" style="background:${color};"></span>
                        #${i + 1}&nbsp;&nbsp;${det.category_th}
                    </span>
                    <span class="item-conf">AI ${detConfPct}%</span>
                </div>

                <!-- Quality + bin row -->
                <div class="live-item-row">
                    <span class="quality-badge ${qClass}">${qText} ${qConfPct}</span>
                    ${recycleTxt}
                </div>
                <div class="item-bin-row">🗑️ ถัง: <strong>${det.suggested_bin || '-'}</strong></div>

                ${prepHtml}
                ${recHtml}
            </div>`;
        }).join('');
    }

    // -----------------------------------------------------------------------
    // Save latest live scan to database
    // -----------------------------------------------------------------------
    const saveLiveBtn = document.getElementById('saveLiveScanBtn');
    if (saveLiveBtn) {
        saveLiveBtn.addEventListener('click', async () => {
            if (!lastScanData) return;

            const saveStatus = document.getElementById('saveLiveStatus');
            saveLiveBtn.disabled = true;
            saveLiveBtn.textContent = 'บันทึก...';
            saveStatus.classList.add('hidden');

            const payload = {
                image_filename:       lastScanData.image_filename || '',
                total_items:          lastScanData.total_items,
                clean_count:          lastScanData.clean_count,
                contaminated_count:   lastScanData.contaminated_count,
                recyclable_count:     lastScanData.recyclable_count     || 0,
                non_recyclable_count: lastScanData.non_recyclable_count || 0,
                processing_time:      lastScanData.processing_time,
                carbon:  lastScanData.carbon  || { total_co2: lastScanData.co2_saved || 0 },
                points:  lastScanData.points  || { points: 0 },
                detections: lastScanData.detections,
            };

            try {
                const res    = await fetch('/api/save', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body:    JSON.stringify(payload),
                });
                const result = await res.json();
                if (result.success) {
                    const pts = result.points_earned ? ` +${result.points_earned} pts` : '';
                    saveStatus.textContent  = 'Saved! (ID: ' + result.scan_id + ')' + pts;
                    saveStatus.className    = 'save-status success';
                    saveLiveBtn.textContent = 'Saved';
                } else {
                    saveStatus.textContent  = 'Error: ' + (result.error || 'failed');
                    saveStatus.className    = 'save-status error';
                    saveLiveBtn.disabled    = false;
                    saveLiveBtn.textContent = 'Save this scan';
                }
                saveStatus.classList.remove('hidden');
            } catch (err) {
                saveStatus.textContent  = 'Error: ' + err.message;
                saveStatus.className    = 'save-status error';
                saveStatus.classList.remove('hidden');
                saveLiveBtn.disabled    = false;
                saveLiveBtn.textContent = 'Save this scan';
            }
        });
    }

});  // end DOMContentLoaded