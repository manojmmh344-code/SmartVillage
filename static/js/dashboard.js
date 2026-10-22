document.addEventListener("DOMContentLoaded", () => {
  const menuButton = document.querySelector(".menu-toggle");
  const sidebar = document.querySelector(".sidebar");
  if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
      const isOpen = sidebar.classList.toggle("sidebar-open");
      menuButton.setAttribute("aria-expanded", String(isOpen));
    });
  }

  document.querySelectorAll("[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll("[data-print]").forEach((button) => {
    button.addEventListener("click", () => window.print());
  });

  if (typeof Chart === "undefined") return;

  const readJson = (id, fallback = []) => {
    const element = document.getElementById(id);
    return element ? JSON.parse(element.textContent) : fallback;
  };

  const roadRatings = (statuses) =>
    statuses.map((status) => ({ Good: 100, Fair: 70, "Needs improvement": 40 })[status] || 0);

  const villageNames = readJson("village-chart-data");
  const villageChartCanvas = document.getElementById("villageChart");
  if (villageChartCanvas) {
    new Chart(villageChartCanvas, {
      type: "bar",
      data: {
        labels: villageNames,
        datasets: [
          { label: "Schools", data: readJson("village-metrics-data"), backgroundColor: "#26734d", borderRadius: 5, yAxisID: "count" },
          { label: "Healthcare centers", data: readJson("village-health-data"), backgroundColor: "#77aa87", borderRadius: 5, yAxisID: "count" },
          { label: "Water availability (%)", data: readJson("village-water-data"), backgroundColor: "#66a9bf", borderRadius: 5, yAxisID: "percent" },
          { label: "Road rating (out of 100)", data: roadRatings(readJson("village-roads-data")), backgroundColor: "#e5ad55", borderRadius: 5, yAxisID: "percent" },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          count: { type: "linear", position: "left", beginAtZero: true, title: { display: true, text: "Facilities" }, ticks: { precision: 0 } },
          percent: { type: "linear", position: "right", beginAtZero: true, max: 100, title: { display: true, text: "Rating / percent" }, grid: { drawOnChartArea: false } },
        },
      },
    });
  }

  const statusCanvas = document.getElementById("projectChart");
  if (statusCanvas) {
    new Chart(statusCanvas, {
      type: "doughnut",
      data: {
        labels: ["Completed", "In Progress", "Planned"],
        datasets: [{ data: readJson("project-status-data"), backgroundColor: ["#27835a", "#e8a33d", "#87a3b2"], borderWidth: 0 }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
    });
  }

  const analyticsCanvas = document.getElementById("analytics-village-chart");
  if (analyticsCanvas) {
    const names = readJson("analytics-data");
    const datasets = {
      schools: readJson("analytics-schools"),
      health: readJson("analytics-health"),
      roads: roadRatings(readJson("analytics-roads")),
      water: readJson("analytics-water"),
    };
    const labels = {
      schools: "Schools",
      health: "Healthcare centers",
      roads: "Road development rating (out of 100)",
      water: "Drinking water availability (%)",
    };
    const selector = document.getElementById("indicator-select");
    const chart = new Chart(analyticsCanvas, {
      type: "bar",
      data: { labels: names, datasets: [{ label: labels[selector.value], data: datasets[selector.value], backgroundColor: "#31845b", borderRadius: 6 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { beginAtZero: true, suggestedMax: selector.value === "roads" || selector.value === "water" ? 100 : undefined, ticks: { precision: 0 } } },
        plugins: { legend: { display: false } },
      },
    });
    selector.addEventListener("change", () => {
      chart.data.datasets[0].label = labels[selector.value];
      chart.data.datasets[0].data = datasets[selector.value];
      chart.options.scales.y.suggestedMax = selector.value === "roads" || selector.value === "water" ? 100 : undefined;
      chart.update();
    });
  }

  const analyticsProjectCanvas = document.getElementById("analytics-project-chart");
  if (analyticsProjectCanvas) {
    new Chart(analyticsProjectCanvas, {
      type: "doughnut",
      data: {
        labels: readJson("analytics-project-labels"),
        datasets: [{ data: readJson("analytics-project-values"), backgroundColor: ["#87a3b2", "#e8a33d", "#27835a"], borderWidth: 0 }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
    });
  }
});
