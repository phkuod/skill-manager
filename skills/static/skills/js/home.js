'use strict';

(function () {
  // Server-rendered first paint already populates the grid. JS takes over
  // on the first user interaction: hydrates `allSkills` from the inline
  // <script id="skills-data"> JSON block and re-renders via filter/sort/search.

  var allSkills = null;       // lazily filled from #skills-data on first interaction
  var currentSearch = '';
  var currentSort = 'lastUpdated';
  var currentCategory = '';
  var debounceTimer = null;
  var DEFAULT_SORT = 'lastUpdated';

  // Map to store skillName -> array of installed targets. Must exist before
  // the first render() call: render() now calls decorateVisibleCards() (it
  // didn't in the dual-renderer version), and decorateVisibleCards() reads
  // this map unconditionally.
  window.__installedMap = window.__installedMap || {};

  var skillGrid = document.getElementById('skill-grid');
  var noResults = document.getElementById('no-results');
  var footerCount = document.getElementById('footer-count');
  var resultCount = document.getElementById('result-count');
  var searchInput = document.getElementById('search-input');
  var searchClear = document.getElementById('search-clear');
  var sortSelect = document.getElementById('sort-select');
  var rail = document.querySelector('.rail');

  function setActiveRailItem(cat) {
    if (!rail) return;
    rail.querySelectorAll('.rail-item').forEach(function (btn) {
      var on = (btn.dataset.cat || '') === cat;
      btn.classList.toggle('is-active', on);
      if (on) btn.setAttribute('aria-current', 'true');
      else btn.removeAttribute('aria-current');
    });
  }

  function ensureSkillsLoaded() {
    if (allSkills !== null) return;
    var node = document.getElementById('skills-data');
    try {
      allSkills = JSON.parse(node.textContent);
    } catch (e) {
      allSkills = [];
    }
  }

  // Highlight `query` matches inside `text`. Walk the *raw* string with the
  // regex, escape each segment before concatenation, and wrap matches in
  // <mark>. Escaping the full text first (the prior approach) breaks the
  // entity sequence when the query contains &, <, >, ", or '.
  function highlight(text, query) {
    if (!query) return escapeHtml(text);
    var re = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    var out = '';
    var last = 0;
    var m;
    while ((m = re.exec(text)) !== null) {
      out += escapeHtml(text.slice(last, m.index)) + '<mark>' + escapeHtml(m[0]) + '</mark>';
      last = m.index + m[0].length;
      if (m[0].length === 0) re.lastIndex++;
    }
    return out + escapeHtml(text.slice(last));
  }

  function matchRank(skill, q) {
    if ((skill.name || '').toLowerCase().indexOf(q) !== -1) return 0;
    if ((skill.description || '').toLowerCase().indexOf(q) !== -1) return 1;
    if ((skill.content || '').toLowerCase().indexOf(q) !== -1) return 2;
    return -1;
  }

  var cardsIndexed = false;
  var catalogByName = {};

  function ensureIndexes() {
    if (cardsIndexed) return;
    cardsIndexed = true;
    allSkills.forEach(function (s) { catalogByName[s.name] = s; });
  }

  function render() {
    ensureSkillsLoaded();
    ensureIndexes();
    var q = currentSearch.trim().toLowerCase();
    var visible = [];
    skillGrid.querySelectorAll('.skill-card').forEach(function (card) {
      var s = catalogByName[card.dataset.name];
      if (!s) { card.classList.add('hidden'); return; }
      var okCat = !currentCategory || (s.category || 'Other') === currentCategory;
      // matchRank returns -1 for "no match" and 0/1/2 for name/description/content
      // matches respectively (lower is a *better* match) — not the 0-is-no-match,
      // higher-is-better convention a first draft of this renderer assumed.
      var rank = q ? matchRank(s, q) : 0;
      var show = okCat && (!q || rank !== -1);
      card.classList.toggle('hidden', !show);
      if (show) visible.push({ card: card, skill: s, rank: rank });
    });
    visible.sort(function (a, b) {
      if (q && b.rank !== a.rank) return a.rank - b.rank;
      if (currentSort === 'name') return a.skill.name.localeCompare(b.skill.name);
      /* default sort: featured pinned first (only without a query), then lastUpdated desc */
      var fa = a.card.dataset.featured ? 1 : 0;
      var fb = b.card.dataset.featured ? 1 : 0;
      if (!q && fb !== fa) return fb - fa;
      return (b.skill.lastUpdated || '').localeCompare(a.skill.lastUpdated || '');
    });
    visible.forEach(function (v) { skillGrid.appendChild(v.card); });
    visible.forEach(function (v) {
      var nameEl = v.card.querySelector('.card-name');
      var descEl = v.card.querySelector('.card-desc');
      if (nameEl) nameEl.innerHTML = q ? highlight(v.skill.name, currentSearch) : escapeHtml(v.skill.name);
      if (descEl) descEl.innerHTML = q ? highlight(v.skill.description, currentSearch) : escapeHtml(v.skill.description);
    });
    noResults.classList.toggle('hidden', visible.length > 0);
    if (footerCount) footerCount.textContent = visible.length;
    if (resultCount) resultCount.textContent = 'Showing ' + visible.length + ' of ' + allSkills.length;
    if (searchClear) searchClear.classList.toggle('hidden', !currentSearch);
    decorateVisibleCards();
    writeUrlState();
  }

  function writeUrlState() {
    // Two-way bind search/sort to ?q=&sort= so reload + copy-paste preserve
    // catalog state. Defaults are omitted from the URL.
    var params = new URLSearchParams();
    if (currentSearch) params.set('q', currentSearch);
    if (currentSort && currentSort !== DEFAULT_SORT) params.set('sort', currentSort);
    if (currentCategory) params.set('cat', currentCategory);
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
    var cat = params.get('cat');
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
    if (cat) {
      currentCategory = cat;
      setActiveRailItem(currentCategory);
      dirty = true;
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

  if (rail) {
    rail.addEventListener('click', function (ev) {
      var btn = ev.target.closest('.rail-item');
      if (!btn) return;
      currentCategory = btn.dataset.cat || '';
      setActiveRailItem(currentCategory);
      render();
    });
  }

  hydrateFromUrl();
  // Always render once on init so the result counter and search-clear button
  // reflect the current state, even when the URL has nothing to hydrate.
  render();

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
    if (e.key === 'Escape' && document.activeElement === searchInput) {
      e.preventDefault();
      searchInput.value = '';
      currentSearch = '';
      render();
      searchInput.blur();
    }
  });
  // -------------------------------------------------------------------------
  // Dashboard Install / Uninstall Modal Workflow
  // -------------------------------------------------------------------------
  var currentActionSkill = '';

  function getCookie(name) {
    var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : '';
  }

  function fetchInstallTargets() {
    return fetch('/api/install/targets')
      .then(function (res) { return res.ok ? res.json() : { targets: [] }; })
      .then(function (data) { return data.targets || []; });
  }

  function openHomeInstallModal(skillName) {
    currentActionSkill = skillName;
    var modal = document.getElementById('install-modal');
    if (!modal) return;
    var titleEl = document.getElementById('install-modal-title');
    var userEl = document.getElementById('install-modal-user');
    var noCookieEl = document.getElementById('install-modal-no-cookie');
    var targetsEl = document.getElementById('install-modal-targets');
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var closeBtn = document.getElementById('install-modal-close');

    var user = getCookie('CURRENT_USER_NAME');
    if (titleEl) titleEl.textContent = skillName;
    if (userEl) userEl.textContent = user || 'no session';
    if (resultEl) {
      resultEl.classList.add('hidden');
      resultEl.classList.remove('is-ok', 'is-err');
      resultEl.textContent = '';
    }
    if (cancelBtn) {
      cancelBtn.textContent = 'Cancel';
      cancelBtn.disabled = false;
    }
    if (noCookieEl) noCookieEl.classList.toggle('hidden', !!user);
    if (targetsEl) targetsEl.innerHTML = '';

    function loadTargets() {
      if (!targetsEl) return;
      targetsEl.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85rem;margin:0;">Loading install targets…</p>';
      fetchInstallTargets().then(function (targets) {
        targetsEl.innerHTML = '';
        if (!targets.length) {
          targetsEl.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85rem;margin:0;">No install targets configured.</p>';
          return;
        }
        targets.forEach(function (t) {
          var path = (user ? t.base.replace('{user_name}', user) : t.base.replace('{user_name}', '<user>')) + '/' + skillName;
          var row = document.createElement('button');
          row.type = 'button';
          row.className = 'install-target-btn';
          row.disabled = !user;
          row.innerHTML =
            '<span class="install-target-name">' + escapeHtml(t.name) + '</span>' +
            '<span class="install-target-path">' + escapeHtml(path) + '</span>' +
            '<span class="install-target-go">&rarr;</span>';
          row.onclick = function () { performHomeInstall(t.name, row); };
          targetsEl.appendChild(row);
        });
      }).catch(function () {
        targetsEl.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85rem;margin:0;">Could not load install targets.</p>';
      });
    }
    loadTargets();

    if (cancelBtn) cancelBtn.onclick = closeHomeInstallModal;
    if (closeBtn) closeBtn.onclick = closeHomeInstallModal;
    modal.classList.remove('hidden');
    requestAnimationFrame(function () { modal.classList.add('is-open'); });
    modal._focusRelease = typeof focusTrap === 'function' ? focusTrap(modal) : function(){};
  }

  function closeHomeInstallModal() {
    var modal = document.getElementById('install-modal');
    if (!modal) return;
    if (modal._focusRelease) {
      modal._focusRelease();
      modal._focusRelease = null;
    }
    modal.classList.remove('is-open');
    setTimeout(function () { modal.classList.add('hidden'); }, 220);
  }

  function performHomeInstall(targetName, row) {
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var targetsEl = document.getElementById('install-modal-targets');
    if (targetsEl) {
      Array.prototype.forEach.call(targetsEl.querySelectorAll('.install-target-btn'), function (b) { b.disabled = true; });
    }
    row.dataset.state = 'busy';
    var goEl = row.querySelector('.install-target-go');
    if (goEl) goEl.innerHTML = '⏳';

    fetch('/api/skills/' + encodeURIComponent(currentActionSkill) + '/install', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: targetName }),
    })
      .then(function (res) {
        return res.json().then(function (data) { return { ok: res.ok, data: data }; });
      })
      .then(function (r) {
        if (r.ok && r.data.status === 'ok') {
          row.dataset.state = 'ok';
          if (goEl) goEl.innerHTML = '✓';
          var okMsg = '✓ Installed to ' + r.data.target + ' — ' + r.data.path;
          if (resultEl) {
            resultEl.textContent = okMsg;
            resultEl.classList.add('is-ok');
            resultEl.classList.remove('hidden');
          }
          toast(okMsg, 'success');
          // Reload installed map to instantaneously display pills
          loadInstalledState();
        } else {
          row.dataset.state = 'err';
          if (goEl) goEl.innerHTML = '✗';
          var errMsg = '✗ ' + (r.data.error || 'Install failed');
          if (resultEl) {
            resultEl.textContent = errMsg;
            resultEl.classList.add('is-err');
            resultEl.classList.remove('hidden');
          }
          toast(errMsg, 'error');
        }
        if (cancelBtn) cancelBtn.textContent = 'Close';
      })
      .catch(function (err) {
        row.dataset.state = 'err';
        if (goEl) goEl.innerHTML = '✗';
        var netMsg = '✗ Network error — ' + err.message;
        if (resultEl) {
          resultEl.textContent = netMsg;
          resultEl.classList.add('is-err');
          resultEl.classList.remove('hidden');
        }
        if (cancelBtn) cancelBtn.textContent = 'Close';
        toast(netMsg, 'error');
      });
  }

  // Pill click → inline confirm row in same card. Removes one target at a time.
  function handlePillClick(pill) {
    var skillName = pill.dataset.skill;
    var targetName = pill.dataset.target;
    if (!skillName || !targetName) return;
    var card = pill.closest('.skill-card');
    if (!card) return;
    var slot = card.querySelector('.inline-confirm-row[data-confirm-slot]');
    if (!slot) return;

    openInlineUninstallConfirm(slot, skillName, targetName, function () {
      return performUninstall(skillName, targetName).then(function (ok) {
        if (!ok) return false;
        if (window.__installedMap && window.__installedMap[skillName]) {
          window.__installedMap[skillName] = window.__installedMap[skillName].filter(function (t) {
            return t !== targetName;
          });
        }
        decorateVisibleCards();
        return true;
      });
    });
  }

  function loadInstalledState() {
    fetchInstallTargets().then(function(targets) {
      var map = {};
      var promises = targets.map(function(t) {
        return fetch('/api/install/targets/' + encodeURIComponent(t.name) + '/skills', { credentials: 'include' })
          .then(function(r) { return r.ok ? r.json() : null; })
          .then(function(d) {
            if (d && d.catalog) {
              d.catalog.forEach(function(item) {
                if (!map[item.name]) map[item.name] = [];
                map[item.name].push(t.name);
              });
            }
          })
          .catch(function() {});
      });
      Promise.all(promises).then(function() {
        window.__installedMap = map;
        // Decorate already server-rendered grid and ensure re-renders keep the status
        decorateVisibleCards();
      });
    }).catch(function() {});
  }

  function decorateVisibleCards() {
    var cards = document.querySelectorAll('.skill-card');
    Array.prototype.forEach.call(cards, function (card) {
      var installBtn = card.querySelector('.quick-install-btn');
      var targetsContainer = card.querySelector('.skill-card-targets');

      var sName = '';
      if (installBtn) sName = installBtn.dataset.skill;
      else if (targetsContainer) sName = targetsContainer.dataset.skillTargets;
      if (!sName) return;

      var tgts = window.__installedMap[sName] || [];

      if (installBtn) {
        installBtn.classList.toggle('hidden', tgts.length > 0);
      }
      if (targetsContainer) {
        if (tgts.length > 0) {
          var html = '';
          tgts.forEach(function (t) { html += targetPillHtml(sName, t); });
          targetsContainer.innerHTML = html;
        } else {
          targetsContainer.innerHTML = '';
        }
      }
      // Ensure the inline-confirm-row slot exists on server-rendered cards
      // (the server template doesn't include it; only JS-rendered cards do).
      if (!card.querySelector('.inline-confirm-row[data-confirm-slot]')) {
        var slot = document.createElement('div');
        slot.className = 'inline-confirm-row hidden';
        slot.setAttribute('data-confirm-slot', sName);
        var footer = card.querySelector('.card-foot');
        if (footer) card.insertBefore(slot, footer);
        else card.appendChild(slot);
      }
    });
  }

  // Handle click events via event delegation on document (rather than
  // scoping to #skill-grid) since base.html's content block has no wrapping
  // element that would make a tighter delegation root meaningfully cheaper.
  // The .closest() guards below already scope this to real hits.
  document.addEventListener('click', function (ev) {
    var pill = ev.target.closest('.target-pill');
    if (pill) {
      ev.preventDefault();
      ev.stopPropagation();
      handlePillClick(pill);
      return;
    }
    var installBtn = ev.target.closest('.quick-install-btn');
    if (installBtn) {
      ev.preventDefault();
      ev.stopPropagation();
      var sName = installBtn.dataset.skill;
      if (sName) openHomeInstallModal(sName);
      return;
    }
  });

  // Esc closes an open install modal (uninstall is inline; its own listener handles Esc).
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var openModal = document.getElementById('install-modal');
      if (openModal && !openModal.classList.contains('hidden')) {
        e.preventDefault();
        e.stopPropagation();
        closeHomeInstallModal();
      }
    }
  });

  // Load installed states immediately on load
  loadInstalledState();
})();
