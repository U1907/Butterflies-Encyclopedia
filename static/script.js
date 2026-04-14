/* Lepidoptera Encyclopedia — main.js */

(function () {
  "use strict";

  // ── Quick search autocomplete ─────────────────────────────
  const input    = document.getElementById("quickSearch");
  const dropdown = document.getElementById("searchDropdown");

  if (input && dropdown) {
    let debounce;

    input.addEventListener("input", function () {
      clearTimeout(debounce);
      const q = this.value.trim();
      if (q.length < 2) { dropdown.classList.remove("open"); dropdown.innerHTML = ""; return; }

      debounce = setTimeout(async () => {
        try {
          const res  = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
          const data = await res.json();
          if (!data.length) { dropdown.classList.remove("open"); return; }
          dropdown.innerHTML = data.map(sp => `
            <a href="/species/${sp.id}" class="search-item">
              <span class="search-item-icon">🦋</span>
              <div class="search-item-text">
                <div class="search-item-name">${highlight(sp.common_name || sp.scientific_name, q)}</div>
                <div class="sci">${sp.scientific_name}</div>
              </div>
              <span class="status-badge status-${sanitizeStatus(sp.status_code)}">${sp.status_code}</span>
            </a>
          `).join("");
          dropdown.classList.add("open");
        } catch (_) { /* silently ignore */ }
      }, 220);
    });

    document.addEventListener("click", (e) => {
      if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove("open");
      }
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { dropdown.classList.remove("open"); input.blur(); }
    });
  }

  // ── Helpers ───────────────────────────────────────────────
  function highlight(text, query) {
    if (!text) return "";
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return text.replace(new RegExp(`(${escaped})`, "gi"), "<mark>$1</mark>");
  }

  function sanitizeStatus(code) {
    return (code || "").replace(/\s+/g, "-").replace(/[()]/g, "");
  }

  // ── Fade-in cards on scroll ───────────────────────────────
  const cards = document.querySelectorAll(".species-card, .detail-panel, .stat-card");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.style.opacity = "1";
          e.target.style.transform = "translateY(0)";
          observer.unobserve(e.target);
        }
      });
    }, { threshold: 0.1 });

    cards.forEach((card, i) => {
      card.style.opacity = "0";
      card.style.transform = "translateY(16px)";
      card.style.transition = `opacity .4s ease ${i * 0.04}s, transform .4s ease ${i * 0.04}s`;
      observer.observe(card);
    });
  }

})();