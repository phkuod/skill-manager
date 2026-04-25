'use strict';

(function () {
  var API_BASE = (window.API_BASE || '').replace(/\/$/, '');

  var allSkills = [];
  var categories = ['All'];
  var currentCategory = 'All';
  var currentSearch = '';
  var currentSort = 'lastUpdated';
  var debounceTimer = null;

  var skillGrid = document.getElementById('skill-grid');
  var noResults = document.getElementById('no-results');
  var loadError = document.getElementById('load-error');
  var footerCount = document.getElementById('footer-count');
  var searchInput = document.getElementById('search-input');
  var sortSelect = document.getElementById('sort-select');
  var categoryFilters = document.getElementById('category-filters');
  var statSkills = document.getElementById('stat-skills');
  var statCategories = document.getElementById('stat-categories');

  // -------------------------------------------------------------------------
  // Card markup
  // -------------------------------------------------------------------------

  function cardHtml(skill) {
    var updated = skill.lastUpdated || '';
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

  function render() {
    var q = currentSearch.toLowerCase();

    var visible = allSkills.filter(function (s) {
      var matchCat = currentCategory === 'All' || s.category === currentCategory;
      if (!matchCat) return false;
      if (!q) return true;
      return (
        (s.name || '').toLowerCase().indexOf(q) !== -1 ||
        (s.description || '').toLowerCase().indexOf(q) !== -1
      );
    });

    visible.sort(function (a, b) {
      if (currentSort === 'name') {
        return (a.name || '').localeCompare(b.name || '');
      }
      return (b.lastUpdated || '').localeCompare(a.lastUpdated || '');
    });

    if (q) {
      visible.sort(function (a, b) {
        var aName = (a.name || '').toLowerCase().indexOf(q) !== -1 ? 0 : 1;
        var bName = (b.name || '').toLowerCase().indexOf(q) !== -1 ? 0 : 1;
        return aName - bName;
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
      if (statSkills) statSkills.textContent = allSkills.length;
      if (statCategories) statCategories.textContent = Math.max(0, categories.length - 1);
      renderCategories();
      render();
    })
    .catch(function () {
      loadError.classList.remove('hidden');
      if (footerCount) footerCount.textContent = '0';
    });
})();
