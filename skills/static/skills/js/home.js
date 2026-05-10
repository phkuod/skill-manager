'use strict';

(function () {
  // Server-rendered first paint already populates the grid. JS takes over
  // on the first user interaction: hydrates `allSkills` from the inline
  // <script id="skills-data"> JSON block and re-renders via filter/sort/search.

  var allSkills = null;       // lazily filled from #skills-data on first interaction
  var currentSearch = '';
  var currentSort = 'lastUpdated';
  var debounceTimer = null;
  var DEFAULT_SORT = 'lastUpdated';

  var skillGrid = document.getElementById('skill-grid');
  var noResults = document.getElementById('no-results');
  var footerCount = document.getElementById('footer-count');
  var resultCount = document.getElementById('result-count');
  var searchInput = document.getElementById('search-input');
  var searchClear = document.getElementById('search-clear');
  var sortSelect = document.getElementById('sort-select');

  function ensureSkillsLoaded() {
    if (allSkills !== null) return;
    var node = document.getElementById('skills-data');
    try {
      allSkills = JSON.parse(node.textContent);
    } catch (e) {
      allSkills = [];
    }
  }

  function cardHtml(skill) {
    var updated = skill.lastUpdated || '';
    return (
      '<a href="/skills/' + encodeURIComponent(skill.name) + '/"' +
      ' class="skill-card block rounded-xl border p-5 transition-all hover:shadow-lg"' +
      ' style="background-color:var(--bg-card);border-color:var(--border);text-decoration:none">' +
        '<div class="icon-wrapper">' +
          '<span>' + escapeHtml(skill.icon) + '</span>' +
        '</div>' +
        '<h3 class="font-semibold mb-1 truncate" style="color:var(--text-primary)">' + escapeHtml(skill.name) + '</h3>' +
        '<p class="text-sm mb-3 line-clamp-2" style="color:var(--text-secondary)">' + escapeHtml(skill.description) + '</p>' +
        '<div class="flex items-center justify-between text-xs" style="color:var(--text-secondary)">' +
          '<span>' + skill.fileCount + ' file' + (skill.fileCount === 1 ? '' : 's') + '</span>' +
          '<span>' + escapeHtml(relativeTime(updated) || updated.slice(0, 10)) + '</span>' +
        '</div>' +
      '</a>'
    );
  }

  function matchRank(skill, q) {
    if ((skill.name || '').toLowerCase().indexOf(q) !== -1) return 0;
    if ((skill.description || '').toLowerCase().indexOf(q) !== -1) return 1;
    if ((skill.content || '').toLowerCase().indexOf(q) !== -1) return 2;
    return -1;
  }

  function render() {
    ensureSkillsLoaded();
    var q = currentSearch.toLowerCase();
    var visible = allSkills.filter(function (s) {
      if (!q) return true;
      return matchRank(s, q) !== -1;
    });
    visible.sort(function (a, b) {
      if (currentSort === 'name') return (a.name || '').localeCompare(b.name || '');
      return (b.lastUpdated || '').localeCompare(a.lastUpdated || '');
    });
    if (q) visible.sort(function (a, b) { return matchRank(a, q) - matchRank(b, q); });

    skillGrid.innerHTML = visible.map(cardHtml).join('');
    noResults.classList.toggle('hidden', visible.length > 0);
    if (footerCount) footerCount.textContent = visible.length;
    if (resultCount) resultCount.textContent = 'Showing ' + visible.length + ' of ' + allSkills.length;
    if (searchClear) searchClear.classList.toggle('hidden', !currentSearch);
    writeUrlState();
  }

  function writeUrlState() {
    // Two-way bind search/sort to ?q=&sort= so reload + copy-paste preserve
    // catalog state. Defaults are omitted from the URL.
    var params = new URLSearchParams();
    if (currentSearch) params.set('q', currentSearch);
    if (currentSort && currentSort !== DEFAULT_SORT) params.set('sort', currentSort);
    var qs = params.toString();
    var newUrl = qs
      ? window.location.pathname + '?' + qs
      : window.location.pathname;
    window.history.replaceState(null, '', newUrl);
  }

  function hydrateFromUrl() {
    var params = new URLSearchParams(window.location.search);
    var q = params.get('q') || '';
    var sort = params.get('sort');
    var dirty = false;
    if (q) {
      currentSearch = q;
      if (searchInput) searchInput.value = q;
      dirty = true;
    }
    if (sort === 'name' || sort === 'lastUpdated') {
      currentSort = sort;
      if (sortSelect) sortSelect.value = sort;
      if (sort !== DEFAULT_SORT) dirty = true;
    }
    if (dirty) render();
  }



  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        currentSearch = searchInput.value.trim();
        render();
      }, 300);
    });
  }

  if (searchClear) {
    searchClear.addEventListener('click', function () {
      searchInput.value = '';
      currentSearch = '';
      render();
      searchInput.focus();
    });
  }

  if (sortSelect) {
    sortSelect.addEventListener('change', function () {
      currentSort = sortSelect.value;
      render();
    });
  }

  hydrateFromUrl();

  // Keyboard shortcuts (unchanged from prior version)
  document.addEventListener('keydown', function (e) {
    if (!searchInput) return;
    var typing = isTypingTarget(e.target);
    if (e.key === '/' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
      return;
    }
    if (e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey) && !e.altKey) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
      return;
    }
    if (e.key === 'Escape' && document.activeElement === searchInput) {
      e.preventDefault();
      searchInput.value = '';
      currentSearch = '';
      render();
      searchInput.blur();
    }
  });
})();
