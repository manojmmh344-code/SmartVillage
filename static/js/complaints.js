document.addEventListener("DOMContentLoaded", () => {
  if (typeof Chart === "undefined") return;
  const read = (id) => {
    const element = document.getElementById(id);
    return element ? JSON.parse(element.textContent) : [];
  };
  const categoryCanvas = document.getElementById("complaint-category-chart");
  if (categoryCanvas) {
    new Chart(categoryCanvas, {
      type: "bar",
      data: {
        labels: read("complaint-category-labels"),
        datasets: [{ label: "Complaints", data: read("complaint-category-values"), backgroundColor: "#39845a", borderRadius: 5 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#edf1ee" } }, x: { ticks: { autoSkip: false, maxRotation: 50, minRotation: 30 } } },
      },
    });
  }
  const statusCanvas = document.getElementById("complaint-status-chart");
  if (statusCanvas) {
    new Chart(statusCanvas, {
      type: "doughnut",
      data: {
        labels: read("complaint-status-labels"),
        datasets: [{ data: read("complaint-status-values"), backgroundColor: ["#e8a33d", "#578eae", "#27835a", "#c9574c"], borderWidth: 0 }],
      },
      options: { responsive: true, maintainAspectRatio: false, cutout: "65%", plugins: { legend: { position: "bottom", labels: { usePointStyle: true, padding: 14 } } } },
    });
  }
});
