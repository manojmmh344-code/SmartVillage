document.addEventListener("DOMContentLoaded", () => {
  const menuButton = document.querySelector(".menu-toggle");
  const sidebar = document.querySelector(".sidebar");
  const sidebarBackdrop = document.querySelector(".sidebar-backdrop");
  const closeSidebar = () => {
    if (!menuButton || !sidebar) return;
    sidebar.classList.remove("sidebar-open");
    menuButton.setAttribute("aria-expanded", "false");
    sidebarBackdrop?.classList.remove("backdrop-visible");
  };

  if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
      const isOpen = sidebar.classList.toggle("sidebar-open");
      menuButton.setAttribute("aria-expanded", String(isOpen));
      sidebarBackdrop?.classList.toggle("backdrop-visible", isOpen);
    });
  }

  sidebarBackdrop?.addEventListener("click", closeSidebar);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSidebar();
  });
  sidebar?.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeSidebar));

  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
        event.preventDefault();
        return;
      }

      if (form.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }
      form.dataset.submitting = "true";
      form.querySelectorAll('button[type="submit"], button:not([type])').forEach((button) => {
        if (button.disabled) return;
        button.disabled = true;
        button.classList.add("is-loading");
        const spinner = document.createElement("span");
        spinner.className = "button-spinner";
        spinner.setAttribute("aria-hidden", "true");
        button.prepend(spinner);
        button.setAttribute("aria-busy", "true");
      });
    });
  });

  document.querySelectorAll("img[data-fallback]").forEach((image) => {
    image.addEventListener("error", () => {
      const fallback = image.dataset.fallback;
      if (fallback && image.src !== new URL(fallback, window.location.href).href) image.src = fallback;
    }, { once: true });
  });

  document.querySelectorAll("[data-print]").forEach((button) => {
    button.addEventListener("click", () => window.print());
  });

  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const revealItems = document.querySelectorAll(".reveal, .panel, .stat-card, .detail-card, .village-card");
  if (!motionQuery.matches && "IntersectionObserver" in window) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.remove("reveal-pending");
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });

    revealItems.forEach((item, index) => {
      item.classList.add("reveal-pending");
      item.style.setProperty("--reveal-delay", `${Math.min(index % 6, 5) * 65}ms`);
      revealObserver.observe(item);
    });
  }

  if (!motionQuery.matches) {
    document.querySelectorAll(".stat-card").forEach((card, index) => {
      card.classList.add("stat-card-enter");
      card.style.setProperty("--card-delay", `${index * 75}ms`);
    });
    document.querySelectorAll("[data-count]").forEach((counter) => {
      const target = Number(counter.dataset.count);
      if (!Number.isFinite(target) || target < 0) return;
      const start = performance.now();
      const duration = 750;
      const update = (now) => {
        const progress = Math.min((now - start) / duration, 1);
        counter.textContent = String(Math.round(target * (1 - Math.pow(1 - progress, 3))));
        if (progress < 1) window.requestAnimationFrame(update);
      };
      window.requestAnimationFrame(update);
    });
  }

  document.querySelectorAll(".button").forEach((button) => {
    button.addEventListener("click", (event) => {
      if (motionQuery.matches || button.matches(":disabled")) return;
      const bounds = button.getBoundingClientRect();
      const ripple = document.createElement("span");
      ripple.className = "button-ripple";
      ripple.style.left = `${event.clientX - bounds.left}px`;
      ripple.style.top = `${event.clientY - bounds.top}px`;
      button.append(ripple);
      ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
    });
  });

  if (typeof Chart === "undefined") return;
  Chart.defaults.font.family = '"Segoe UI", Arial, sans-serif';
  Chart.defaults.color = "#718078";
  Chart.defaults.animation.duration = motionQuery.matches ? 0 : 800;
  Chart.defaults.plugins.tooltip.backgroundColor = "#173f2e";
  Chart.defaults.plugins.tooltip.padding = 11;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;

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
        interaction: { mode: "index", intersect: false },
        plugins: { tooltip: { displayColors: true, usePointStyle: true } },
        scales: {
          count: { type: "linear", position: "left", beginAtZero: true, title: { display: true, text: "Facilities" }, ticks: { precision: 0, padding: 8 }, grid: { color: "#edf1ee" } },
          percent: { type: "linear", position: "right", beginAtZero: true, max: 100, title: { display: true, text: "Rating / percent" }, ticks: { padding: 8 }, grid: { drawOnChartArea: false } },
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
      options: { responsive: true, maintainAspectRatio: false, cutout: "68%", plugins: { legend: { position: "bottom", labels: { usePointStyle: true, padding: 18 } } } },
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
        scales: { y: { beginAtZero: true, suggestedMax: selector.value === "roads" || selector.value === "water" ? 100 : undefined, ticks: { precision: 0, padding: 8 }, grid: { color: "#edf1ee" } } },
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
      options: { responsive: true, maintainAspectRatio: false, cutout: "68%", plugins: { legend: { position: "bottom", labels: { usePointStyle: true, padding: 18 } } } },
    });
  }
});
