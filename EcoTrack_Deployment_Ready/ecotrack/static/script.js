// EcoTrack Minimal JS Engine
document.addEventListener('DOMContentLoaded', () => {
    // 1. Gauge Meter SVG
    const gauge = document.getElementById('gauge-fill');
    if (gauge) {
        const pct = parseFloat(gauge.getAttribute('data-pct')) || 0;
        const circ = 2 * Math.PI * 65; // r=65
        gauge.style.strokeDasharray = circ;
        gauge.style.strokeDashoffset = circ - (Math.min(100, pct) / 100) * circ;
    }

    // 2. Calculator Live Preview
    const elec = document.getElementById('elec');
    if (elec) {
        const factors = { petrol: 0.192, diesel: 0.171, ev: 0.053, bike: 0.045, elec: 0.82, lpg: 42.5, waste: 0.52 };
        const update = () => {
            const eVal = (parseFloat(elec.value) || 0) * factors.elec;
            const tKm = parseFloat(document.getElementById('trans_km').value) || 0;
            const tType = document.getElementById('trans_type').value;
            const tVal = tKm * (factors[tType] || 0.192);
            const lpgVal = (parseFloat(document.getElementById('lpg').value) || 0) * factors.lpg;
            const wVal = (parseFloat(document.getElementById('waste').value) || 0) * factors.waste;
            
            document.getElementById('prev-co2').textContent = (eVal + tVal + lpgVal + wVal).toFixed(1) + ' kg';
        };
        ['elec', 'trans_km', 'trans_type', 'lpg', 'waste'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('input', update);
        });
        update();
    }
});

// 3. Chart.js Rendering Helper with Neon Area Gradient
function renderChart(canvasId, labels, dataVals) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    // Create gradient fill under line
    const gradient = ctx.createLinearGradient(0, 0, 0, 240);
    gradient.addColorStop(0, 'rgba(34, 197, 94, 0.4)');
    gradient.addColorStop(0.8, 'rgba(34, 197, 94, 0.02)');
    gradient.addColorStop(1, 'rgba(34, 197, 94, 0)');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.length ? labels : ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            datasets: [{
                label: 'Monthly CO₂ (kg)',
                data: dataVals.length ? dataVals : [320, 290, 310, 280, 250, 220],
                borderColor: '#22c55e',
                borderWidth: 3,
                backgroundColor: gradient,
                fill: true,
                tension: 0.35,
                pointBackgroundColor: '#22c55e',
                pointBorderColor: '#0b0f17',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#141d2c',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    titleColor: '#fff',
                    bodyColor: '#22c55e',
                    padding: 10,
                    displayColors: false
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#9ca3af', font: { size: 11 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#9ca3af', font: { size: 11 } },
                    beginAtZero: true
                }
            }
        }
    });
}

// 4. Chart.js Prediction Chart Helper (Actual vs Predicted Emissions)
function renderPredictionChart(canvasId, histLabels, histVals, predLabels, predVals) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Combine labels
    const allLabels = [...histLabels, ...predLabels];

    // Actual dataset: historical values, padded with nulls for future slots
    const actualData = [...histVals, ...Array(predVals.length).fill(null)];

    // Predicted dataset: starts at the last historical value so line connects smoothly, then predicted values
    const predPaddingCount = Math.max(0, histVals.length - 1);
    const predData = [
        ...Array(predPaddingCount).fill(null),
        histVals.length > 0 ? histVals[histVals.length - 1] : null,
        ...predVals
    ];

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: allLabels,
            datasets: [
                {
                    label: 'Actual Emissions (kg CO₂)',
                    data: actualData,
                    borderColor: '#22c55e',
                    borderWidth: 3,
                    pointBackgroundColor: '#22c55e',
                    pointBorderColor: '#0b0f17',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    fill: false,
                    tension: 0.2
                },
                {
                    label: 'Predicted Emissions (ML Estimate)',
                    data: predData,
                    borderColor: '#38bdf8',
                    borderDash: [6, 6],
                    borderWidth: 3,
                    pointBackgroundColor: '#38bdf8',
                    pointBorderColor: '#0b0f17',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointStyle: 'rectRot',
                    fill: false,
                    tension: 0.2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        color: '#9ca3af',
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: '#141d2c',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    titleColor: '#fff',
                    bodyColor: '#38bdf8',
                    padding: 10
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#9ca3af', font: { size: 11 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#9ca3af', font: { size: 11 } },
                    beginAtZero: true
                }
            }
        }
    });
}

