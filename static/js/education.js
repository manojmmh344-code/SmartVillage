document.addEventListener("DOMContentLoaded", () => {
  const grid = document.getElementById("education-service-grid");
  if (!grid) return;

  const cards = Array.from(grid.querySelectorAll(".education-service-card"));
  const searchInput = document.getElementById("education-search");
  const filters = Array.from(document.querySelectorAll(".education-filter"));
  const emptyState = document.getElementById("education-empty-state");
  const resultCount = document.getElementById("education-results-count");
  let activeCategory = "all";

  const applyFilters = () => {
    const query = searchInput.value.trim().toLocaleLowerCase();
    let visibleCount = 0;
    cards.forEach((card) => {
      const matchesCategory = activeCategory === "all" || card.dataset.category === activeCategory;
      const matchesSearch = !query || card.dataset.search.includes(query);
      const isVisible = matchesCategory && matchesSearch;
      card.hidden = !isVisible;
      if (isVisible) visibleCount += 1;
    });
    emptyState.hidden = visibleCount > 0;
    resultCount.textContent = query || activeCategory !== "all"
      ? `${visibleCount} ${visibleCount === 1 ? "service" : "services"} found`
      : "";
  };

  searchInput.addEventListener("input", applyFilters);
  filters.forEach((filter) => {
    filter.addEventListener("click", () => {
      activeCategory = filter.dataset.category;
      filters.forEach((item) => {
        const isSelected = item === filter;
        item.classList.toggle("is-selected", isSelected);
        item.setAttribute("aria-pressed", String(isSelected));
      });
      applyFilters();
    });
  });

  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!motionQuery.matches && "IntersectionObserver" in window) {
    const animatedItems = document.querySelectorAll(
      ".education-hero, .education-section-heading, .education-service-card, .education-steps li, .education-featured-card, .education-faq-list details, .education-detail-hero, .education-source-card"
    );
    const observer = new IntersectionObserver((entries, currentObserver) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.remove("education-reveal-pending");
          entry.target.classList.add("education-visible");
          currentObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });

    animatedItems.forEach((item, index) => {
      item.classList.add("education-reveal-pending");
      item.style.setProperty("animation-delay", `${Math.min(index % 6, 5) * 55}ms`);
      observer.observe(item);
    });
  }
});
