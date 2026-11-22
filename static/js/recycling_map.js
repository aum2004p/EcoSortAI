/* EcoSort AI - Recycling Location Map (Leaflet + OpenStreetMap) */
(function () {
    const DEFAULT_CENTER = [13.9885, 100.6175];   // Rangsit, Pathum Thani
    const TYPES = window.POINT_TYPES || {};
    const params = new URLSearchParams(location.search);
    const category = params.get('category');       // from scanner / recovery
    let activeType = '';
    let userPos = null;
    let userMarker = null;
    let markers = [];

    const map = L.map('recMap').setView(DEFAULT_CENTER, 12);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);

    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function icon(p) {
        return L.divIcon({
            className: 'rec-pin',
            html: `<span>${p.icon}</span>`,
            iconSize: [34, 34], iconAnchor: [17, 17],
        });
    }

    async function load() {
        const q = new URLSearchParams();
        if (userPos) { q.set('lat', userPos[0]); q.set('lng', userPos[1]); }
        if (activeType) q.set('type', activeType);
        else if (category) q.set('category', category);
        const list = document.getElementById('pointList');
        try {
            const res = await fetch('/api/recycling-points?' + q.toString());
            const data = await res.json();
            render(data.points || []);
        } catch (e) {
            list.innerHTML = '<div class="table-loading">โหลดข้อมูลไม่สำเร็จ</div>';
        }
    }

    function render(points) {
        markers.forEach((m) => map.removeLayer(m));
        markers = [];
        const list = document.getElementById('pointList');
        if (!points.length) {
            list.innerHTML = '<div class="table-loading">ไม่พบจุดทิ้งที่ตรงกับตัวกรอง</div>';
            return;
        }
        list.innerHTML = '';
        const bounds = [];
        points.forEach((p) => {
            const hasXY = p.lat != null && p.lng != null;
            const dist = p.distance_km != null ? `${p.distance_km} กม.` : '';
            const mapsUrl = hasXY
                ? `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}`
                : 'https://www.google.com/maps/search/?api=1&query='
                  + encodeURIComponent(`${p.name} ${p.address}`);
            const rating = p.rating != null ? ` · ⭐ ${p.rating}` : '';

            let m = null;
            if (hasXY) {
                const popup = `<strong>${esc(p.name)}</strong><br>${esc(p.type_th)}`
                    + (p.opening_hours ? `<br>🕒 ${esc(p.opening_hours)}` : '')
                    + (p.phone ? `<br>📞 ${esc(p.phone)}` : '')
                    + `<br><a target="_blank" rel="noopener" href="${mapsUrl}">นำทาง</a>`;
                m = L.marker([p.lat, p.lng], { icon: icon(p) }).addTo(map).bindPopup(popup);
                markers.push(m);
                bounds.push([p.lat, p.lng]);
            }

            const card = document.createElement('div');
            card.className = 'point-card';
            card.innerHTML = `
                <div class="point-top"><strong>${p.icon} ${esc(p.name)}</strong>
                    <span class="point-dist">${dist}</span></div>
                <small>${esc(p.type_th)}${rating}</small>
                ${p.address ? `<small>📍 ${esc(p.address)}</small>` : ''}
                ${p.opening_hours ? `<small>🕒 ${esc(p.opening_hours)}</small>` : ''}
                ${p.phone ? `<small>📞 <a href="tel:${esc(p.phone.replace(/\s/g, ''))}">${esc(p.phone)}</a></small>` : ''}
                <a class="find-drop-link" target="_blank" rel="noopener" href="${mapsUrl}">${hasXY ? 'นำทาง' : 'เปิดใน Google Maps'}</a>`;
            card.addEventListener('click', (e) => {
                if (e.target.closest('a')) return;
                if (m) { map.setView([p.lat, p.lng], 15); m.openPopup(); }
            });
            list.appendChild(card);
        });
        if (userPos) bounds.push(userPos);
        if (bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }

    document.getElementById('typeFilters').addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        document.querySelectorAll('#typeFilters .period-tab')
            .forEach((x) => x.classList.toggle('active', x === b));
        activeType = b.dataset.type;
        load();
    });

    document.getElementById('btnLocate').addEventListener('click', () => {
        const note = document.getElementById('mapNote');
        if (!navigator.geolocation) { note.textContent = 'เบราว์เซอร์นี้ไม่รองรับการหาตำแหน่ง'; return; }
        note.textContent = 'กำลังหาตำแหน่งของคุณ...';
        navigator.geolocation.getCurrentPosition((pos) => {
            userPos = [pos.coords.latitude, pos.coords.longitude];
            if (userMarker) map.removeLayer(userMarker);
            userMarker = L.circleMarker(userPos, { radius: 9, color: '#22d3ee', fillOpacity: .8 })
                .addTo(map).bindPopup('ตำแหน่งของคุณ');
            note.textContent = 'เรียงจุดจากใกล้ไปไกลตามตำแหน่งของคุณ';
            load();
        }, () => {
            note.textContent = 'ไม่สามารถหาตำแหน่งได้ (ต้องอนุญาตตำแหน่ง และเปิดผ่าน localhost หรือ HTTPS)';
        }, { enableHighAccuracy: true, timeout: 10000 });
    });

    if (category) {
        const names = { plastic: 'พลาสติก', paper: 'กระดาษ', cardboard: 'กระดาษลัง',
                        glass: 'แก้ว', metal: 'โลหะ', trash: 'ขยะอิเล็กทรอนิกส์/ขยะทั่วไป' };
        document.getElementById('mapNote').textContent =
            `แสดงจุดที่รับ: ${names[category] || category} (กด "ทั้งหมด" เพื่อดูทุกจุด)`;
    }
    load();
})();