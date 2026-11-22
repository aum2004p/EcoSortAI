/* ==========================================================================
   EcoSort AI - Waste Recovery Center
   Flow: pending -> in_progress -> awaiting_review -> completed | unable
   ========================================================================== */
(function () {
    const listEl = document.getElementById('taskList');
    const toast = document.getElementById('rcToast');
    let currentStatus = '';

    const STATUS_TH = {
        pending: 'รอดำเนินการ', in_progress: 'กำลังดำเนินการ',
        awaiting_review: 'รอตรวจสอบ', completed: 'เสร็จแล้ว', unable: 'กู้คืนไม่ได้',
    };
    const QUALITY_TH = { clean: 'สะอาด', contaminated: 'ปนเปื้อน' };
    const CAT_TH = {
        plastic: 'พลาสติก', paper: 'กระดาษ', cardboard: 'กระดาษลัง',
        glass: 'แก้ว', metal: 'โลหะ', trash: 'ขยะทั่วไป',
    };

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function say(text, ok) {
        toast.textContent = text;
        toast.className = 'rc-toast ' + (ok ? 'ok' : 'err');
        clearTimeout(say._t);
        say._t = setTimeout(() => toast.classList.add('hidden'), 4000);
    }

    async function api(url, opts) {
        const r = await fetch(url, opts);
        let data = {};
        try { data = await r.json(); } catch (e) { /* ignore */ }
        if (r.status === 401) { window.location.href = '/login'; }
        return { ok: r.ok, data };
    }

    // Crop the task's bbox from the original scan image onto a small canvas
    function cropThumb(img) {
        const c = img.closest('.task-card').querySelector('canvas.task-crop');
        const b = JSON.parse(c.dataset.bbox || 'null');
        if (!b) return;
        const w = Math.max(1, b.x2 - b.x1), h = Math.max(1, b.y2 - b.y1);
        const scale = Math.min(1, 160 / Math.max(w, h));
        c.width = Math.round(w * scale); c.height = Math.round(h * scale);
        c.getContext('2d').drawImage(img, b.x1, b.y1, w, h, 0, 0, c.width, c.height);
    }

    function card(t) {
        const steps = t.steps.map(s => `<li>${esc(s)}</li>`).join('');
        const rescan = t.after_quality ? `
            <div class="rescan-result ${t.after_quality}">
                🔍 ผลสแกนซ้ำ: <strong>${QUALITY_TH[t.after_quality] || t.after_quality}</strong>
                (${Math.round((t.after_quality_confidence || 0) * 100)}%)
                ${t.after_image_url ? `<a href="${esc(t.after_image_url)}" target="_blank" rel="noopener">ดูภาพ</a>` : ''}
                ${t.mismatch ? '<div class="mismatch">⚠️ ผลสแกนซ้ำไม่ตรงกับที่ยืนยัน (บันทึกความต่างไว้)</div>' : ''}
            </div>` : '';

        let actions = '';
        if (t.status === 'pending') {
            actions = `<button class="btn btn-primary btn-sm" data-act="start">▶ เริ่มดำเนินการ</button>`;
        } else if (t.status === 'in_progress') {
            actions = `
                <input class="plan-input" data-role="note" maxlength="500" placeholder="หมายเหตุ (ไม่บังคับ)">
                <button class="btn btn-primary btn-sm" data-act="complete">✔ จัดการเสร็จแล้ว</button>`;
        } else if (t.status === 'awaiting_review') {
            actions = `
                <label class="btn btn-secondary btn-sm file-btn">📷 สแกนซ้ำ
                    <input type="file" accept="image/png,image/jpeg,image/webp" data-role="file" hidden>
                </label>
                <input class="plan-input" data-role="note" maxlength="500" placeholder="หมายเหตุ (ไม่บังคับ)" value="${esc(t.note)}">
                <button class="btn btn-primary btn-sm" data-act="verify-yes">✅ ยืนยัน: จัดการสำเร็จ</button>
                <button class="btn btn-secondary btn-sm" data-act="verify-no">⛔ กู้คืนไม่ได้</button>`;
        } else {
            actions = `<span class="task-final">${t.status === 'completed' ? '✅ ยืนยันแล้ว' : '⛔ กู้คืนไม่ได้'}${t.points_awarded ? ` · +${t.points_awarded} คะแนน` : ''}</span>`;
        }

        return `
        <article class="task-card st-${t.status}" data-id="${t.id}">
            <div class="task-thumb">
                <canvas class="task-crop" data-bbox='${esc(JSON.stringify(t.bbox))}' width="80" height="80"></canvas>
                <img class="task-src" src="${esc(t.image_url)}" alt="" hidden>
            </div>
            <div class="task-main">
                <header>
                    <h4>${esc(t.title)}</h4>
                    <span class="status-pill st-${t.status}">${STATUS_TH[t.status]}</span>
                </header>
                <small class="task-meta">
                    ${esc(CAT_TH[t.category] || t.category)} ·
                    ก่อนจัดการ: <strong class="q-${t.before_quality}">${QUALITY_TH[t.before_quality] || t.before_quality}</strong> ·
                    แผน: ${esc(t.plan_title)}
                </small>
                <ol class="task-steps">${steps}</ol>
                <a class="find-drop-link" href="/recycling-map?category=${esc(t.category)}" target="_blank">📍 หาจุดทิ้งใกล้ฉัน</a>
                ${rescan}
                ${t.note && t.status !== 'awaiting_review' ? `<div class="task-note">📝 ${esc(t.note)}</div>` : ''}
                <div class="task-actions">${actions}</div>
            </div>
        </article>`;
    }

    async function load() {
        const q = currentStatus ? '?status=' + currentStatus : '';
        const { ok, data } = await api('/api/recovery/tasks' + q);
        if (!ok) { listEl.innerHTML = '<div class="table-loading">โหลดข้อมูลไม่สำเร็จ</div>'; return; }
        const s = data.summary.by_status;
        document.getElementById('rcPending').textContent = s.pending;
        document.getElementById('rcProgress').textContent = s.in_progress;
        document.getElementById('rcReview').textContent = s.awaiting_review;
        document.getElementById('rcDone').textContent = s.completed;

        if (!data.tasks.length) {
            listEl.innerHTML = `<div class="table-loading">ไม่มีงานในสถานะนี้ ${currentStatus ? '' : '— <a href="/waste-planner">สร้างแผนก่อน</a>'}</div>`;
            return;
        }
        listEl.innerHTML = data.tasks.map(card).join('');
        listEl.querySelectorAll('img.task-src').forEach(img => {
            if (img.complete) cropThumb(img); else img.addEventListener('load', () => cropThumb(img));
        });
    }

    listEl.addEventListener('click', async (e) => {
        const btn = e.target.closest('button[data-act]');
        if (!btn) return;
        const cardEl = btn.closest('.task-card');
        const id = cardEl.dataset.id;
        const note = (cardEl.querySelector('[data-role=note]') || {}).value || '';
        const post = (path, body) => api(`/api/recovery/tasks/${id}/${path}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {}),
        });
        btn.disabled = true;
        let r;
        switch (btn.dataset.act) {
            case 'start': r = await post('start'); break;
            case 'complete': r = await post('complete', { note }); break;
            case 'verify-yes': r = await post('verify', { recovered: true, note }); break;
            case 'verify-no':
                if (!confirm('ยืนยันว่าขยะชิ้นนี้ไม่สามารถกู้คืนเพื่อรีไซเคิลได้?')) { btn.disabled = false; return; }
                r = await post('verify', { recovered: false, note }); break;
        }
        if (r.ok) {
            if (r.data.points_awarded) say(`🎉 ได้รับ +${r.data.points_awarded} คะแนน`, true);
            else say('บันทึกสถานะแล้ว', true);
        } else {
            say('❌ ' + (r.data.error || 'ดำเนินการไม่สำเร็จ'), false);
        }
        load();
    });

    listEl.addEventListener('change', async (e) => {
        const input = e.target.closest('input[data-role=file]');
        if (!input || !input.files.length) return;
        const id = input.closest('.task-card').dataset.id;
        const fd = new FormData();
        fd.append('image', input.files[0]);
        say('⏳ กำลังสแกนซ้ำ...', true);
        const { ok, data } = await api(`/api/recovery/tasks/${id}/rescan`, { method: 'POST', body: fd });
        if (ok) {
            say(data.task.after_quality === 'clean' ? '✅ สแกนซ้ำ: ดูสะอาดแล้ว' : '⚠️ สแกนซ้ำ: ยังดูปนเปื้อน', ok);
        } else {
            say('❌ ' + (data.error || 'สแกนซ้ำไม่สำเร็จ'), false);
        }
        load();
    });

    document.getElementById('rcFilters').addEventListener('click', (e) => {
        const b = e.target.closest('.period-tab');
        if (!b) return;
        document.querySelectorAll('#rcFilters .period-tab').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        currentStatus = b.dataset.status;
        load();
    });

    load();
})();
