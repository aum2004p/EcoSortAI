/* ==========================================================================
   EcoSort AI - Waste Action Planner
   ========================================================================== */
(function () {
    const scanList = document.getElementById('scanList');
    const planList = document.getElementById('planList');
    const createBtn = document.getElementById('createPlanBtn');
    const planMsg = document.getElementById('planMsg');
    const titleInput = document.getElementById('planTitle');

    const STATUS_TH = {
        pending: 'รอดำเนินการ', in_progress: 'กำลังดำเนินการ',
        awaiting_review: 'รอตรวจสอบ', completed: 'เสร็จแล้ว', unable: 'กู้คืนไม่ได้',
    };

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function showMsg(text, ok) {
        planMsg.textContent = text;
        planMsg.className = 'save-status ' + (ok ? 'success' : 'error');
    }

    async function api(url, opts) {
        const r = await fetch(url, opts);
        let data = {};
        try { data = await r.json(); } catch (e) { /* ignore */ }
        if (r.status === 401) { window.location.href = '/login'; }
        return { ok: r.ok, status: r.status, data };
    }

    function updateCreateBtn() {
        const n = scanList.querySelectorAll('input[type=checkbox]:checked').length;
        createBtn.disabled = n === 0;
        createBtn.textContent = n ? `✨ สร้างแผนจาก ${n} การสแกน` : '✨ สร้างแผนจากที่เลือก';
    }

    async function loadScans() {
        const { ok, data } = await api('/api/my-scans');
        if (!ok) { scanList.innerHTML = '<div class="table-loading">โหลดข้อมูลไม่สำเร็จ</div>'; return; }
        if (!data.scans.length) {
            scanList.innerHTML = '<div class="table-loading">ยังไม่มีประวัติการสแกน ไปสแกนและกด “บันทึกผลการสแกน” ก่อน</div>';
            return;
        }
        scanList.innerHTML = data.scans.map(s => {
            const disabled = s.plannable_items === 0 || s.total_items === 0;
            const d = new Date(s.created_at);
            return `
            <label class="scan-pick ${disabled ? 'disabled' : ''}">
                <input type="checkbox" value="${s.id}" ${disabled ? 'disabled' : ''}>
                <img src="${esc(s.image_url)}" alt="" loading="lazy">
                <div class="scan-pick-body">
                    <strong>สแกน #${s.id}</strong>
                    <span>${d.toLocaleString('th-TH')}</span>
                    <span>ขยะ ${s.total_items} ชิ้น · สะอาด ${s.clean_count} · ปนเปื้อน ${s.contaminated_count}</span>
                    ${disabled ? '<span class="scan-pick-note">มีงานครบแล้ว / ไม่มีวัตถุ</span>' : ''}
                </div>
            </label>`;
        }).join('');
        scanList.querySelectorAll('input').forEach(i => i.addEventListener('change', updateCreateBtn));
        updateCreateBtn();
    }

    function taskRow(t) {
        return `<li class="mini-task st-${t.status}">
            <span class="mini-task-title">${esc(t.title)}</span>
            <span class="status-pill st-${t.status}">${STATUS_TH[t.status] || t.status}</span>
        </li>`;
    }

    async function loadPlans() {
        const { ok, data } = await api('/api/plans');
        if (!ok) { planList.innerHTML = '<div class="table-loading">โหลดข้อมูลไม่สำเร็จ</div>'; return; }
        if (!data.plans.length) {
            planList.innerHTML = '<div class="table-loading">ยังไม่มีแผน เลือกการสแกนทางซ้ายแล้วกดสร้างแผน</div>';
            return;
        }
        // Fetch details so we can list tasks
        const details = await Promise.all(data.plans.map(p => api('/api/plans/' + p.id)));
        planList.innerHTML = details.map(r => {
            const p = r.data.plan;
            const pr = p.progress;
            return `
            <article class="plan-card" data-id="${p.id}">
                <header>
                    <div>
                        <h4>${esc(p.title)}</h4>
                        <small>สร้างเมื่อ ${new Date(p.created_at).toLocaleString('th-TH')} · สแกน ${p.scan_ids.map(i => '#' + i).join(', ')}</small>
                    </div>
                    <span class="status-pill ${p.status === 'done' ? 'st-completed' : 'st-in_progress'}">${p.status === 'done' ? 'เสร็จสิ้น' : 'กำลังดำเนินการ'}</span>
                </header>
                <div class="progress-bar"><div class="progress-fill" style="width:${pr.percent}%"></div></div>
                <small>${pr.closed}/${pr.total} งานปิดแล้ว (${pr.percent}%)</small>
                <ul class="mini-task-list">${p.tasks.map(taskRow).join('')}</ul>
                <footer>
                    <a class="btn btn-primary btn-sm" href="/waste-recovery">ไปที่ Recovery Center →</a>
                    <button class="btn btn-secondary btn-sm" data-act="rename">✏️ เปลี่ยนชื่อ</button>
                    <button class="btn btn-secondary btn-sm" data-act="delete" ${p.tasks.every(t => t.status === 'pending') ? '' : 'disabled'}>🗑️ ลบ</button>
                </footer>
            </article>`;
        }).join('');
    }

    async function loadOverview() {
        const { ok, data } = await api('/api/recovery/tasks');
        if (!ok) return;
        const s = data.summary;
        document.getElementById('ovTotal').textContent = s.total_tasks;
        document.getElementById('ovOpen').textContent = s.open_tasks;
        document.getElementById('ovDone').textContent = s.by_status.completed;
        document.getElementById('ovRate').textContent = s.completion_rate + '%';
    }

    function refreshAll() { return Promise.all([loadScans(), loadPlans(), loadOverview()]); }

    createBtn.addEventListener('click', async () => {
        const ids = [...scanList.querySelectorAll('input:checked')].map(i => parseInt(i.value, 10));
        if (!ids.length) return;
        createBtn.disabled = true;
        createBtn.textContent = '⏳ กำลังสร้างแผน...';
        const { ok, data } = await api('/api/plans', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scan_ids: ids, title: titleInput.value }),
        });
        if (ok) {
            const i = data.info;
            let t = `✅ สร้างแผนแล้ว ${i.created} งาน`;
            if (i.skipped_open) t += ` (ข้าม ${i.skipped_open} ชิ้นที่มีงานค้างอยู่)`;
            showMsg(t, true);
            titleInput.value = '';
        } else {
            showMsg('❌ ' + (data.error || 'สร้างแผนไม่สำเร็จ'), false);
        }
        await refreshAll();
    });

    planList.addEventListener('click', async (e) => {
        const btn = e.target.closest('button[data-act]');
        if (!btn) return;
        const id = btn.closest('.plan-card').dataset.id;
        if (btn.dataset.act === 'rename') {
            const name = prompt('ชื่อแผนใหม่');
            if (!name || !name.trim()) return;
            await api('/api/plans/' + id, {
                method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: name }),
            });
        } else if (btn.dataset.act === 'delete') {
            if (!confirm('ลบแผนนี้?')) return;
            const r = await api('/api/plans/' + id, { method: 'DELETE' });
            if (!r.ok) alert(r.data.error || 'ลบไม่สำเร็จ');
        }
        await refreshAll();
    });

    refreshAll();
})();
