'use strict';

(function () {
  var API_BASE = (window.API_BASE || '').replace(/\/$/, '');

  var allSkills = [];
  var categories = ['All'];
  var allTags = [];
  var currentCategory = 'All';
  var currentSearch = '';
  var currentSort = 'lastUpdated';
  var selectedTags = {}; // tag -> true (OR-combined)
  var debounceTimer = null;

  var skillGrid = document.getElementById('skill-grid');
  var noResults = document.getElementById('no-results');
  var loadError = document.getElementById('load-error');
  var footerCount = document.getElementById('footer-count');
  var searchInput = document.getElementById('search-input');
  var sortSelect = document.getElementById('sort-select');
  var categoryFilters = document.getElementById('category-filters');
  var tagFilters = document.getElementById('tag-filters');
  var tagFilterRow = document.getElementById('tag-filter-row');
  var statSkills = document.getElementById('stat-skills');
  var statCategories = document.getElementById('stat-categories');

  // -------------------------------------------------------------------------
  // Card markup
  // -------------------------------------------------------------------------

  function cardHtml(skill) {
    var updated = skill.lastUpdated || '';
    var tags = skill.tags || [];
    var tagsHtml = tags.length
      ? '<div class="flex flex-wrap gap-1 mb-3">' +
          tags.slice(0, 4).map(function (t) {
            return '<span class="text-xs px-1.5 py-0.5 rounded border" style="color:var(--text-secondary);border-color:var(--border)">' + escapeHtml(t) + '</span>';
          }).join('') +
        '</div>'
      : '';
    return (
      '<a href="/skill/' + encodeURIComponent(skill.name) + '"' +
      ' class="skill-card block rounded-xl border p-5 transition-all hover:shadow-lg"' +
      ' style="background-color:var(--bg-card);border-color:var(--border);text-decoration:none">' +
        '<div class="flex items-start justify-between mb-3">' +
          '<span class="text-3xl">' + escapeHtml(skill.icon) + '</span>' +
          '<span class="text-xs px-2 py-0.5 rounded-full category-badge" data-category="' + escapeHtml(skill.category) + '">' +
            escapeHtml(skill.category) +
          '</span>' +
        '</div>' +
        '<h3 class="font-semibold mb-1 truncate" style="color:var(--text-primary)">' + escapeHtml(skill.name) + '</h3>' +
        '<p class="text-sm mb-3 line-clamp-2" style="color:var(--text-secondary)">' + escapeHtml(skill.description) + '</p>' +
        tagsHtml +
        '<div class="flex items-center justify-between text-xs" style="color:var(--text-secondary)">' +
          '<span>' + skill.fileCount + ' file' + (skill.fileCount === 1 ? '' : 's') + '</span>' +
          '<span>' + escapeHtml(relativeTime(updated) || updated.slice(0, 10)) + '</span>' +
        '</div>' +
      '</a>'
    );
  }

  // -------------------------------------------------------------------------
  // Filter / sort / render
  // -------------------------------------------------------------------------

  // Rank by where the query hit: name (0) > description (1) > content (2).
  // Mirrors backend/skills/views.py::_search_sort_key.
  function matchRank(skill, q) {
    if ((skill.name || '').toLowerCase().indexOf(q) !== -1) return 0;
    if ((skill.description || '').toLowerCase().indexOf(q) !== -1) return 1;
    if ((skill.content || '').toLowerCase().indexOf(q) !== -1) return 2;
    return -1;
  }

  function hasSelectedTags() {
    for (var k in selectedTags) {
      if (selectedTags[k]) return true;
    }
    return false;
  }

  function matchesTags(s) {
    if (!hasSelectedTags()) return true;
    var skillTags = s.tags || [];
    for (var i = 0; i < skillTags.length; i++) {
      if (selectedTags[skillTags[i]]) return true;
    }
    return false;
  }

  function render() {
    var q = currentSearch.toLowerCase();

    var visible = allSkills.filter(function (s) {
      var matchCat = currentCategory === 'All' || s.category === currentCategory;
      if (!matchCat) return false;
      if (!matchesTags(s)) return false;
      if (!q) return true;
      return matchRank(s, q) !== -1;
    });

    visible.sort(function (a, b) {
      if (currentSort === 'name') {
        return (a.name || '').localeCompare(b.name || '');
      }
      return (b.lastUpdated || '').localeCompare(a.lastUpdated || '');
    });

    if (q) {
      visible.sort(function (a, b) {
        return matchRank(a, q) - matchRank(b, q);
      });
    }

    skillGrid.innerHTML = visible.map(cardHtml).join('');
    noResults.classList.toggle('hidden', visible.length > 0);
    footerCount.textContent = visible.length;
  }

  // -------------------------------------------------------------------------
  // Category pills
  // -------------------------------------------------------------------------

  function renderCategories() {
    categoryFilters.innerHTML = categories.map(function (cat) {
      return (
        '<button class="category-pill px-3 py-1 rounded-full text-sm border font-medium transition-colors"' +
        ' data-category="' + escapeHtml(cat) + '"' +
        ' style="border-color:var(--border);color:var(--text-secondary);background-color:var(--bg-secondary)">' +
          escapeHtml(cat) +
        '</button>'
      );
    }).join('');

    Array.prototype.forEach.call(categoryFilters.querySelectorAll('.category-pill'), function (pill) {
      pill.addEventListener('click', function () {
        currentCategory = pill.dataset.category;
        categoryFilters.querySelectorAll('.category-pill').forEach(function (p) {
          p.classList.toggle('active', p.dataset.category === currentCategory);
        });
        render();
      });
    });

    var first = categoryFilters.querySelector('.category-pill[data-category="All"]');
    if (first) first.classList.add('active');
  }

  // -------------------------------------------------------------------------
  // Tag pills (multi-select, OR-combined)
  // -------------------------------------------------------------------------

  function renderTags() {
    if (!tagFilters || !tagFilterRow) return;
    if (!allTags || allTags.length === 0) {
      tagFilterRow.classList.add('hidden');
      tagFilterRow.classList.remove('flex');
      return;
    }
    tagFilterRow.classList.remove('hidden');
    tagFilterRow.classList.add('flex');

    tagFilters.innerHTML = allTags.map(function (t) {
      return (
        '<button class="tag-pill px-2 py-0.5 rounded-full text-xs border transition-colors"' +
        ' data-tag="' + escapeHtml(t) + '"' +
        ' style="border-color:var(--border);color:var(--text-secondary);background-color:var(--bg-secondary)">' +
          escapeHtml(t) +
        '</button>'
      );
    }).join('');

    Array.prototype.forEach.call(tagFilters.querySelectorAll('.tag-pill'), function (pill) {
      pill.addEventListener('click', function () {
        var tag = pill.dataset.tag;
        selectedTags[tag] = !selectedTags[tag];
        pill.classList.toggle('active', !!selectedTags[tag]);
        render();
      });
    });
  }

  // -------------------------------------------------------------------------
  // Wire inputs
  // -------------------------------------------------------------------------

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        currentSearch = searchInput.value.trim();
        render();
      }, 300);
    });
  }

  if (sortSelect) {
    sortSelect.addEventListener('change', function () {
      currentSort = sortSelect.value;
      render();
    });
  }

  // -------------------------------------------------------------------------
  // Keyboard shortcuts
  //   /        focus the search box
  //   Ctrl+K   focus the search box (also Cmd+K on macOS)
  //   Esc      while searching, clear the query and unfocus
  // -------------------------------------------------------------------------

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

  // -------------------------------------------------------------------------
  // Fetch and initialize
  // -------------------------------------------------------------------------

  fetch(API_BASE + '/api/skills')
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    })
    .then(function (data) {
      allSkills = data.skills || [];
      categories = data.categories && data.categories.length ? data.categories : ['All'];
      allTags = data.tags || [];
      if (statSkills) statSkills.textContent = allSkills.length;
      if (statCategories) statCategories.textContent = Math.max(0, categories.length - 1);
      renderCategories();
      renderTags();
      render();
    })
    .catch(function () {
      loadError.classList.remove('hidden');
      if (footerCount) footerCount.textContent = '0';
    });
})();
