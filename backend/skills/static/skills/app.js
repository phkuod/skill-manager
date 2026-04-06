'use strict';

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------

function applyTheme(dark) {
  document.documentElement.classList.toggle('dark', dark);
  const sun = document.getElementById('icon-sun');
  const moon = document.getElementById('icon-moon');
  if (sun) sun.classList.toggle('hidden', !dark);
  if (moon) moon.classList.toggle('hidden', dark);
}

function initTheme() {
  const stored = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(stored === 'dark' || (!stored && prefersDark));
}

function toggleTheme() {
  const isDark = document.documentElement.classList.contains('dark');
  const next = !isDark;
  localStorage.setItem('theme', next ? 'dark' : 'light');
  applyTheme(next);
}

// Apply theme immediately to prevent flash
initTheme();

document.addEventListener('DOMContentLoaded', function () {
  // Re-apply (in case icons weren't in DOM yet)
  initTheme();

  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

  // ---------------------------------------------------------------------------
  // Relative time
  // ---------------------------------------------------------------------------

  function relativeTime(isoString) {
    const now = Date.now();
    const then = new Date(isoString).getTime();
    const diffMs = now - then;
    const mins = Math.floor(diffMs / 60000);
    if (mins < 60) return mins + 'm ago';
    const hours = Math.floor(mins / 60);
    if (hours < 24) return hours + 'h ago';
    const days = Math.floor(hours / 24);
    if (days < 30) return days + 'd ago';
    const months = Math.floor(days / 30);
    return months + 'mo ago';
  }

  document.querySelectorAll('.relative-time').forEach(function (el) {
    const t = el.dataset.time;
    if (t) el.textContent = relativeTime(t);
  });

  // ---------------------------------------------------------------------------
  // Copy to clipboard
  // ---------------------------------------------------------------------------

  document.querySelectorAll('.copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const text = btn.dataset.copy;
      navigator.clipboard.writeText(text).then(function () {
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(function () { btn.textContent = orig; }, 2000);
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Install tabs (detail page)
  // ---------------------------------------------------------------------------

  document.querySelectorAll('.install-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      const target = tab.dataset.tab;
      document.querySelectorAll('.install-tab').forEach(function (t) {
        t.classList.toggle('active', t.dataset.tab === target);
      });
      document.querySelectorAll('.install-tab-content').forEach(function (c) {
        c.classList.toggle('hidden', c.id !== 'tab-' + target);
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Syntax highlighting
  // ---------------------------------------------------------------------------

  if (typeof hljs !== 'undefined') {
    document.querySelectorAll('pre code').forEach(function (block) {
      hljs.highlightElement(block);
    });
  }

  // ---------------------------------------------------------------------------
  // Home page: search + category filter + sort
  // ---------------------------------------------------------------------------

  const searchInput = document.getElementById('search-input');
  const sortSelect = document.getElementById('sort-select');
  const skillGrid = document.getElementById('skill-grid');
  const noResults = document.getElementById('no-results');
  const footerCount = document.getElementById('footer-count');

  if (!skillGrid) return; // Not on home page

  const cards = Array.from(skillGrid.querySelectorAll('.skill-card'));
  let currentCategory = 'All';
  let currentSearch = '';
  let currentSort = 'lastUpdated';
  let debounceTimer = null;

  function applyFilters() {
    const q = currentSearch.toLowerCase();
    let visible = [];
    let hidden = [];

    cards.forEach(function (card) {
      const name = (card.dataset.name || '').toLowerCase();
      const desc = (card.dataset.description || '').toLowerCase();
      const cat = card.dataset.category || '';

      const matchCat = currentCategory === 'All' || cat === currentCategory;
      const matchSearch = !q || name.includes(q) || desc.includes(q);

      if (matchCat && matchSearch) {
        visible.push(card);
      } else {
        card.style.display = 'none';
        hidden.push(card);
      }
    });

    // Sort visible cards
    visible.sort(function (a, b) {
      if (currentSort === 'name') {
        return (a.dataset.name || '').localeCompare(b.dataset.name || '');
      } else {
        // lastUpdated descending
        return (b.dataset.updated || '').localeCompare(a.dataset.updated || '');
      }
    });

    // If searching, name matches first
    if (q) {
      visible.sort(function (a, b) {
        const aName = (a.dataset.name || '').toLowerCase().includes(q) ? 0 : 1;
        const bName = (b.dataset.name || '').toLowerCase().includes(q) ? 0 : 1;
        return aName - bName;
      });
    }

    // Re-append in sorted order
    visible.forEach(function (card) {
      card.style.display = '';
      skillGrid.appendChild(card);
    });

    if (noResults) noResults.classList.toggle('hidden', visible.length > 0);
    if (footerCount) footerCount.textContent = visible.length;
  }

  // Search input with 300ms debounce
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        currentSearch = searchInput.value.trim();
        applyFilters();
      }, 300);
    });
  }

  // Sort dropdown
  if (sortSelect) {
    sortSelect.addEventListener('change', function () {
      currentSort = sortSelect.value;
      applyFilters();
    });
  }

  // Category pills
  document.querySelectorAll('.category-pill').forEach(function (pill) {
    pill.addEventListener('click', function () {
      currentCategory = pill.dataset.category;
      document.querySelectorAll('.category-pill').forEach(function (p) {
        p.classList.toggle('active', p.dataset.category === currentCategory);
      });
      applyFilters();
    });
  });

  // Activate "All" pill by default
  const allPill = document.querySelector('.category-pill[data-category="All"]');
  if (allPill) allPill.classList.add('active');

  // Initial sort
  applyFilters();

  // ---------------------------------------------------------------------------
  // Version selector (detail page)
  // ---------------------------------------------------------------------------

  const versionSelect = document.getElementById('version-select');
  if (versionSelect) {
    versionSelect.addEventListener('change', function () {
      const version = versionSelect.value;
      // Extract skill name from URL path /skill/<name>
      const parts = window.location.pathname.split('/');
      const skillName = parts[parts.indexOf('skill') + 1];
      if (skillName) {
        window.location.href = '/skill/' + skillName + '?version=' + encodeURIComponent(version);
      }
    });
  }
});
