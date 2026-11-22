/* ==========================================================================
   EcoSort AI - Dashboard JavaScript
   Fetches statistics and trends from the API and renders Chart.js charts.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // Chart instances (stored so we can destroy/recreate on period change)
    let charts = {};
    let currentPeriod = 'daily';

    // Category color map (must match config.py)
    const CATEGORY_COLORS = {
        plastic: '#3498db',
        paper: '#f1c40f',
        cardboard: '#e67e22',
        glass: '#1abc9c',
        metal: '#95a5a6',
        trash: '#e74c3c',
    };

    // Init
    loadStats();
    loadTrends(currentPeriod);
    loadCategoryBreakdown();
    loadRecentScans();

    // Period tabs
    document.querySelectorAll('.period-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.period-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentPeriod = tab.dataset.period;
            loadTrends(currentPeriod);
        });
    });

    // Export button
    document.getElementById('exportBtn').addEventListener('click', () => {
        window.location.href = '/api/export';
    });

    // ==================================================================
    // Load summary statistics
    // ==================================================================
    function loadStats() {
        fetch('/api/stats')
            .then(r => r.json())
            .then(data => {
                document.getElementById('statScans').textContent = formatNum(data.total_scans);
                document.getElementById('statItems').textContent = formatNum(data.total_items);
                document.getElementById('statClean').textContent = formatNum(data.total_clean);
                document.getElementById('statContaminated').textContent = formatNum(data.total_contaminated);
                document.getElementById('statRecyclable').textContent = formatNum(data.total_recyclable);
                document.getElementById('statNonRecyclable').textContent = formatNum(data.total_non_recyclable);

                // Quality doughnut chart
                renderQualityChart(data.quality);

                // Recyclable doughnut chart
                renderRecyclableChart(data.total_recyclable, data.total_non_recyclable);

                // Category pie chart
                renderCategoryPieChart(data.categories);

                // Category bar chart
                renderCategoryBarChart(data.categories);

                // Show empty state if no data
                if (data.total_scans === 0) {
                    document.getElementById('dashEmptyState').classList.remove('hidden');
                }
            })
            .catch(err => console.error('Stats load error:', err));
    }

    // ==================================================================
    // Load trend data (time series)
    // ==================================================================
    function loadTrends(period) {
        fetch(`/api/trends?period=${period}`)
            .then(r => r.json())
            .then(data => {
                renderTrendChart(data.data, period);
            })
            .catch(err => console.error('Trends load error:', err));
    }

    // ==================================================================
    // Load category quality breakdown
    // ==================================================================
    function loadCategoryBreakdown() {
        fetch('/api/category-trends')
            .then(r => r.json())
            .then(data => {
                renderCategoryQualityChart(data);
            })
            .catch(err => console.error('Category breakdown error:', err));
    }

    // ==================================================================
    // Load recent scans table
    // ==================================================================
    function loadRecentScans() {
        fetch('/api/scans?per_page=10')
            .then(r => r.json())
            .then(data => {
                const tbody = document.getElementById('recentScansBody');
                if (!data.scans || data.scans.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" class="table-loading">ยังไม่มีข้อมูลการสแกน</td></tr>';
                    return;
                }

                tbody.innerHTML = data.scans.map(s => `
                    <tr>
                        <td>${s.id}</td>
                        <td>${formatDate(s.created_at)}</td>
                        <td><strong>${s.total_items}</strong></td>
                        <td style="color: #27ae60;">${s.clean_count}</td>
                        <td style="color: #e74c3c;">${s.contaminated_count}</td>
                        <td>${s.recyclable_count}</td>
                        <td>${s.processing_time}s</td>
                    </tr>
                `).join('');
            })
            .catch(err => console.error('Scans load error:', err));
    }

    // ==================================================================
    // Chart renderers
    // ==================================================================
    function renderTrendChart(data, period) {
        destroyChart('trend');

        const labels = data.map(d => d.label);

        const datasets = [
            {
                label: 'สะอาด',
                data: data.map(d => d.clean),
                borderColor: '#27ae60',
                backgroundColor: 'rgba(39, 174, 96, 0.1)',
                fill: true,
                tension: 0.3,
            },
            {
                label: 'ปนเปื้อน',
                data: data.map(d => d.contaminated),
                borderColor: '#e74c3c',
                backgroundColor: 'rgba(231, 76, 60, 0.1)',
                fill: true,
                tension: 0.3,
            },
            {
                label: 'ทั้งหมด',
                data: data.map(d => d.total_items),
                borderColor: '#3498db',
                backgroundColor: 'rgba(52, 152, 219, 0.05)',
                fill: false,
                tension: 0.3,
                borderDash: [5, 5],
            },
        ];

        charts.trend = new Chart(document.getElementById('trendChart'), {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } },
                },
            },
        });
    }

    function renderCategoryPieChart(categories) {
        destroyChart('categoryPie');

        if (!categories || categories.length === 0) {
            showEmptyChart('categoryPieChart', 'ยังไม่มีข้อมูล');
            return;
        }

        charts.categoryPie = new Chart(document.getElementById('categoryPieChart'), {
            type: 'doughnut',
            data: {
                labels: categories.map(c => c.name_th),
                datasets: [{
                    data: categories.map(c => c.count),
                    backgroundColor: categories.map(c => c.color),
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right' },
                },
            },
        });
    }

    function renderCategoryBarChart(categories) {
        destroyChart('categoryBar');

        if (!categories || categories.length === 0) {
            showEmptyChart('categoryBarChart', 'ยังไม่มีข้อมูล');
            return;
        }

        // Sort by count descending
        const sorted = [...categories].sort((a, b) => b.count - a.count);

        charts.categoryBar = new Chart(document.getElementById('categoryBarChart'), {
            type: 'bar',
            data: {
                labels: sorted.map(c => c.name_th),
                datasets: [{
                    label: 'จำนวนชิ้น',
                    data: sorted.map(c => c.count),
                    backgroundColor: sorted.map(c => c.color),
                    borderRadius: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: { legend: { display: false } },
                scales: {
                    x: { beginAtZero: true, ticks: { precision: 0 } },
                },
            },
        });
    }

    function renderQualityChart(quality) {
        destroyChart('quality');

        const clean = quality.clean || 0;
        const contaminated = quality.contaminated || 0;

        if (clean === 0 && contaminated === 0) {
            showEmptyChart('qualityChart', 'ยังไม่มีข้อมูล');
            return;
        }

        charts.quality = new Chart(document.getElementById('qualityChart'), {
            type: 'doughnut',
            data: {
                labels: ['สะอาด', 'ปนเปื้อน'],
                datasets: [{
                    data: [clean, contaminated],
                    backgroundColor: ['#27ae60', '#e74c3c'],
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } },
            },
        });
    }

    function renderRecyclableChart(recyclable, nonRecyclable) {
        destroyChart('recyclable');

        if (recyclable === 0 && nonRecyclable === 0) {
            showEmptyChart('recyclableChart', 'ยังไม่มีข้อมูล');
            return;
        }

        charts.recyclable = new Chart(document.getElementById('recyclableChart'), {
            type: 'doughnut',
            data: {
                labels: ['รีไซเคิลได้', 'ขยะทั่วไป'],
                datasets: [{
                    data: [recyclable, nonRecyclable],
                    backgroundColor: ['#3498db', '#95a5a6'],
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } },
            },
        });
    }

    function renderCategoryQualityChart(data) {
        destroyChart('categoryQuality');

        const entries = Object.entries(data);
        if (entries.length === 0) {
            showEmptyChart('categoryQualityChart', 'ยังไม่มีข้อมูล');
            return;
        }

        // Sort by total descending
        entries.sort((a, b) => b[1].total - a[1].total);

        const labels = entries.map(([key, v]) => v.name_th);

        charts.categoryQuality = new Chart(document.getElementById('categoryQualityChart'), {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'สะอาด',
                        data: entries.map(([k, v]) => v.clean),
                        backgroundColor: '#27ae60',
                        borderRadius: 4,
                    },
                    {
                        label: 'ปนเปื้อน',
                        data: entries.map(([k, v]) => v.contaminated),
                        backgroundColor: '#e74c3c',
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
                },
                plugins: { legend: { position: 'top' } },
            },
        });
    }

    // ==================================================================
    // Helpers
    // ==================================================================
    function destroyChart(name) {
        if (charts[name]) {
            charts[name].destroy();
            delete charts[name];
        }
    }

    function showEmptyChart(canvasId, msg) {
        const canvas = document.getElementById(canvasId);
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = '14px Segoe UI, sans-serif';
        ctx.fillStyle = '#95a5a6';
        ctx.textAlign = 'center';
        ctx.fillText(msg, canvas.width / 2, canvas.height / 2);
    }
});


// ==========================================================================
// Carbon Impact
// ==========================================================================
function loadCarbonImpact() {
    fetch('/api/carbon-impact')
        .then(r => r.json())
        .then(data => {
            document.getElementById('carbonCO2').textContent = data.total_co2.toFixed(4);
            document.getElementById('carbonTrees').textContent = data.trees_equivalent.toFixed(4);
            document.getElementById('carbonKm').textContent = data.km_driven_equivalent.toFixed(1);
            document.getElementById('carbonPhones').textContent =
                (data.total_co2 / 0.005).toLocaleString();
            const textDiv = document.getElementById('carbonImpactText');
            if (textDiv && data.impact_text) {
                textDiv.textContent = data.impact_text;
            }
        })
        .catch(err => console.error('Carbon impact error:', err));
}

// ==========================================================================
// Waste Prediction (Time Series)
// ==========================================================================
let predictionChart = null;

function loadPrediction(days = 7) {
    fetch(`/api/prediction?days=${days}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                document.getElementById('predictionSummary').innerHTML =
                    `<p class="pred-no-data">${data.error}</p>`;
                if (predictionChart) {
                    predictionChart.destroy();
                    predictionChart = null;
                }
                return;
            }

            const pred = data.prediction;
            document.getElementById('predConfidence').textContent =
                `ความมั่นใจ: ${pred.confidence === 'high' ? 'สูง' :
                  pred.confidence === 'medium' ? 'ปานกลาง' : 'ต่ำ'} ` +
                `(${pred.total_data_points} วันข้อมูล)`;

            // Build chart: historical + predictions
            if (predictionChart) predictionChart.destroy();

            const histLabels = pred.historical.map(d => d.label);
            const histItems = pred.historical.map(d => d.items);
            const predLabels = pred.predictions.map(d => d.label);
            const predItems = pred.predictions.map(d => d.predicted_items);

            // Combine labels
            const allLabels = [...histLabels, ...predLabels];
            const histData = [...histItems, ...Array(predLabels.length).fill(null)];
            const predData = [
                ...Array(histLabels.length - 1).fill(null),
                histItems[histItems.length - 1],  // connect line
                ...predItems
            ];

            predictionChart = new Chart(document.getElementById('predictionChart'), {
                type: 'line',
                data: {
                    labels: allLabels,
                    datasets: [
                        {
                            label: 'ข้อมูลจริง (Historical)',
                            data: histData,
                            borderColor: '#3498db',
                            backgroundColor: 'rgba(52, 152, 219, 0.1)',
                            fill: true,
                            tension: 0.3,
                        },
                        {
                            label: 'พยากรณ์ (Predicted)',
                            data: predData,
                            borderColor: '#e67e22',
                            backgroundColor: 'rgba(230, 126, 34, 0.1)',
                            fill: true,
                            tension: 0.3,
                            borderDash: [6, 4],
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'top' } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                },
            });

            // Summary
            const trendText = pred.trend === 'increasing' ? '📈 แนวโน้มเพิ่มขึ้น' :
                              pred.trend === 'decreasing' ? '📉 แนวโน้มลดลง' :
                              '➡️ แนวโน้มคงที่';
            const summaryDiv = document.getElementById('predictionSummary');
            summaryDiv.innerHTML = `
                <div class="pred-stats">
                    <span>📊 ค่าเฉลี่ยต่อวัน: <strong>${pred.avg_daily}</strong> ชิ้น</span>
                    <span>${trendText}</span>
                    <span>🔮 คาดการณ์สัปดาห์หน้า: <strong>${
                        pred.predictions.reduce((s, p) => s + p.predicted_items, 0).toFixed(0)
                    }</strong> ชิ้น</span>
                </div>
            `;
        })
        .catch(err => console.error('Prediction error:', err));
}

// PDF report button
document.addEventListener('DOMContentLoaded', () => {
    const reportBtn = document.getElementById('reportBtn');
    if (reportBtn) {
        reportBtn.addEventListener('click', () => {
            window.location.href = '/api/report';
        });
    }

    // Prediction controls
    const predDays = document.getElementById('predDays');
    const predRefresh = document.getElementById('predRefreshBtn');
    if (predDays) {
        predDays.addEventListener('change', () => loadPrediction(predDays.value));
    }
    if (predRefresh) {
        predRefresh.addEventListener('click', () => loadPrediction(predDays.value));
    }

    // Load new data
    loadCarbonImpact();
    loadPrediction(7);
});

// ---------------------------------------------------------------------------
// Recovery progress card (Action Planner integration)
// ---------------------------------------------------------------------------
(function () {
    const el = document.getElementById('rdTotal');
    if (!el) return;
    fetch('/api/recovery/stats')
        .then(r => r.json())
        .then(s => {
            document.getElementById('rdTotal').textContent = s.total_tasks;
            document.getElementById('rdOpen').textContent = s.open_tasks;
            document.getElementById('rdDone').textContent = s.by_status.completed;
            document.getElementById('rdRecovered').textContent = s.contaminated_recovered;
            const p = document.getElementById('rdProblem');
            if (s.total_tasks === 0) {
                p.textContent = 'ยังไม่มีข้อมูลการจัดการ';
            } else {
                let t = `อัตราจัดการสำเร็จ ${s.completion_rate}%`;
                if (s.top_problem_category) {
                    t += ` · ประเภทที่เป็นปัญหามากที่สุด: ${s.top_problem_category.name_th} (${s.top_problem_category.count} งาน)`;
                }
                if (s.mismatches) t += ` · ผลสแกนซ้ำไม่ตรงกับที่ยืนยัน ${s.mismatches} งาน`;
                p.textContent = t;
            }
        })
        .catch(() => {});
})();
