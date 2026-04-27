function buildBlankChart(canvasId, label) {
    const ctx = document.getElementById(canvasId).getContext("2d");

    new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label,
                data: [],
                borderColor: "#7cefff",
                backgroundColor: "rgba(124,239,255,0.15)",
                fill: true,
                tension: 0.2,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { color: "#ffffff" }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: "Time", color: "#ffffff" },
                    grid: { color: "rgba(255,255,255,0.16)" },
                    ticks: { color: "#ffffff" }
                },
                y: {
                    title: { display: true, text: "Value", color: "#ffffff" },
                    grid: { color: "rgba(255,255,255,0.16)" },
                    ticks: { color: "#ffffff" }
                }
            }
        }
    });
}