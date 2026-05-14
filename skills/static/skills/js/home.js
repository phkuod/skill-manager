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

  function getTargetStyle(tName) {
    var c = (tName || '').toLowerCase();
    if (c.indexOf('prod') !== -1 || c.indexOf('f20') !== -1) {
      return { bg: 'rgba(16, 185, 129, 0.08)', border: 'rgba(16, 185, 129, 0.25)', text: '#059669', dot: '#10b981' };
    } else if (c.indexOf('stage') !== -1 || c.indexOf('f15') !== -1) {
      return { bg: 'rgba(139, 92, 246, 0.08)', border: 'rgba(139, 92, 246, 0.25)', text: '#6d28d9', dot: '#8b5cf6' };
    } else {
      return { bg: 'rgba(14, 165, 233, 0.08)', border: 'rgba(14, 165, 233, 0.25)', text: '#0369a1', dot: '#0ea5e9' };
    }
  }

  function cardHtml(skill) {
    var q = currentSearch;
    var updated = skill.lastUpdated || '';
    var tgts = window.__installedMap ? (window.__installedMap[skill.name] || []) : [];
    var targetsHtml = '';
    var uninstallHtml = '';
    if (tgts.length > 0) {
      uninstallHtml = '<button type="button" class="quick-uninstall-btn px-2 py-1 text-xs font-semibold rounded-lg border cursor-pointer transition-all hover:bg-red-50 dark:hover:bg-red-950/20" style="color:#b42318;border-color:rgba(180,35,24,0.3);background-color:transparent;" data-skill="' + escapeHtml(skill.name) + '" data-target="' + escapeHtml(tgts[0]) + '">Uninstall</button>';
      tgts.forEach(function(t) {
        var ts = getTargetStyle(t);
        targetsHtml += '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition-all hover:scale-105" style="background-color:' + ts.bg + ';border:1px solid ' + ts.border + ';color:' + ts.text + ';font-size:0.72rem;font-weight:600;box-shadow:0 2px 4px rgba(0,0,0,0.03);margin-right:6px;">' +
          '<span class="inline-block w-2 h-2 rounded-full" style="background-color:' + ts.dot + ';box-shadow:0 0 8px ' + ts.dot + ';"></span>' +
          '<span style="opacity:0.75;font-size:0.62rem;text-transform:uppercase;letter-spacing:0.06em;">Target</span>' +
          '<span style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">' + escapeHtml(t) + '</span>' +
        '</span>';
      });
    }
    var installHtml = '';
    if (tgts.length === 0) {
      installHtml = '<button type="button" class="quick-install-btn px-2.5 py-1 text-xs font-semibold rounded-lg border cursor-pointer transition-all hover:scale-105" style="color:var(--accent);border-color:var(--accent);background-color:var(--bg-primary);" data-skill="' + escapeHtml(skill.name) + '">Install</button>';
    }
    return (
      '<a href="/skills/' + encodeURIComponent(skill.name) + '/"' +
      ' class="skill-card block rounded-xl border p-5 transition-all hover:shadow-lg relative"' +
      ' style="background-color:var(--bg-card);border-color:var(--border);text-decoration:none">' +
        '<div class="flex items-center justify-between gap-2 mb-3">' +
          '<div class="flex items-center gap-4 min-w-0">' +
            '<div class="icon-wrapper shrink-0">' +
              '<span>' + escapeHtml(skill.icon) + '</span>' +
            '</div>' +
            '<div class="skill-card-targets flex flex-wrap gap-1.5 items-center min-w-0 empty:hidden ml-1" data-skill-targets="' + escapeHtml(skill.name) + '">' + targetsHtml + '</div>' +
          '</div>' +
          '<div class="inline-flex items-center gap-1.5 shrink-0 z-10" onclick="event.preventDefault(); event.stopPropagation();">' +
            uninstallHtml +
            installHtml +
          '</div>' +
        '</div>' +
        '<h3 class="font-semibold mb-1 truncate" style="color:var(--text-primary)">' + highlight(skill.name, q) + '</h3>' +
        '<p class="text-sm mb-3 line-clamp-2" style="color:var(--text-secondary)">' + highlight(skill.description, q) + '</p>' +
        '<div class="pt-2 border-t flex items-center justify-between text-xs" style="color:var(--text-secondary);border-color:var(--border)">' +
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

  function openHomeUninstallModal(skillName) {
    currentActionSkill = skillName;
    var modal = document.getElementById('uninstall-target-modal');
    if (!modal) return;
    var titleEl = document.getElementById('uninstall-target-modal-title');
    var targetsEl = document.getElementById('uninstall-target-modal-targets');
    var resultEl = document.getElementById('uninstall-target-modal-result');
    var cancelBtn = document.getElementById('uninstall-target-modal-cancel');
    var closeBtn = document.getElementById('uninstall-target-modal-close');

    if (titleEl) titleEl.textContent = skillName;
    if (resultEl) {
      resultEl.classList.add('hidden');
      resultEl.classList.remove('is-ok', 'is-err');
      resultEl.textContent = '';
    }
    if (cancelBtn) {
      cancelBtn.textContent = 'Cancel';
      cancelBtn.disabled = false;
    }
    if (targetsEl) targetsEl.innerHTML = '';

    var tgts = window.__installedMap ? (window.__installedMap[skillName] || []) : [];
    if (!tgts.length) {
      if (targetsEl) targetsEl.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85rem;margin:0;">Not installed on any targets.</p>';
    } else {
      tgts.forEach(function(tName) {
        var row = document.createElement('button');
        row.type = 'button';
        row.className = 'uninstall-target-btn';
        row.innerHTML =
          '<span class="install-target-name" style="color:#b42318;">' + escapeHtml(tName) + '</span>' +
          '<span class="install-target-path" style="color:var(--text-secondary);">Remove from this target</span>' +
          '<span class="install-target-go" style="color:#b42318;font-size:1.25rem;">&times;</span>';
        row.onclick = function() { confirmHomeUninstallSelection(tName); };
        targetsEl.appendChild(row);
      });
    }

    if (cancelBtn) cancelBtn.onclick = closeHomeUninstallModal;
    if (closeBtn) closeBtn.onclick = closeHomeUninstallModal;
    modal.classList.remove('hidden');
    requestAnimationFrame(function () { modal.classList.add('is-open'); });
    modal._focusRelease = typeof focusTrap === 'function' ? focusTrap(modal) : function(){};
  }

  function confirmHomeUninstallSelection(targetName) {
    var targetsEl = document.getElementById('uninstall-target-modal-targets');
    var resultEl = document.getElementById('uninstall-target-modal-result');
    if (!targetsEl) return;

    if (resultEl) {
      resultEl.classList.add('hidden');
      resultEl.classList.remove('is-ok', 'is-err');
      resultEl.textContent = '';
    }

    targetsEl.innerHTML =
      '<div style="padding:16px; background-color:var(--bg-secondary); border:1px solid var(--border); border-radius:12px;">' +
        '<p style="margin:0 0 8px; font-size:0.95rem; font-weight:600; color:var(--text-primary);">Remove from <span style="color:#b42318;font-family:monospace;">' + escapeHtml(targetName) + '</span>?</p>' +
        '<p style="margin:0 0 12px; font-size:0.82rem; color:var(--text-secondary);">This action cannot be undone. Please type <strong style="color:var(--text-primary);">' + escapeHtml(currentActionSkill) + '</strong> to confirm.</p>' +
        '<input type="text" id="home-uninstall-confirm-input" autocomplete="off" spellcheck="false" placeholder="Type skill name..." style="width:100%; padding:10px 12px; border:1px solid var(--border); border-radius:8px; background:var(--bg-primary); color:var(--text-primary); font-size:0.85rem; margin-bottom:14px; box-sizing:border-box; outline:none;">' +
        '<div style="display:flex; justify-content:flex-end; gap:8px;">' +
          '<button type="button" id="home-uninstall-back-btn" style="padding:8px 14px; border:1px solid var(--border); border-radius:8px; background:transparent; color:var(--text-secondary); font-size:0.82rem; font-weight:600; cursor:pointer;">Back</button>' +
          '<button type="button" id="home-uninstall-go-btn" disabled style="padding:8px 14px; border:none; border-radius:8px; background:#b42318; color:#ffffff; font-size:0.82rem; font-weight:600; cursor:pointer; opacity:0.5; transition:opacity 0.15s;">Remove</button>' +
        '</div>' +
      '</div>';

    var inputEl = document.getElementById('home-uninstall-confirm-input');
    var backBtn = document.getElementById('home-uninstall-back-btn');
    var goBtn = document.getElementById('home-uninstall-go-btn');

    if (backBtn) {
      backBtn.onclick = function() {
        openHomeUninstallModal(currentActionSkill);
      };
    }

    if (inputEl && goBtn) {
      inputEl.oninput = function() {
        if (inputEl.value.trim() === currentActionSkill) {
          goBtn.disabled = false;
          goBtn.style.opacity = '1';
          goBtn.style.cursor = 'pointer';
        } else {
          goBtn.disabled = true;
          goBtn.style.opacity = '0.5';
          goBtn.style.cursor = 'not-allowed';
        }
      };

      goBtn.onclick = function() {
        performHomeUninstallSelection(targetName);
      };

      setTimeout(function() { inputEl.focus(); }, 50);
    }
  }

  function closeHomeUninstallModal() {
    var modal = document.getElementById('uninstall-target-modal');
    if (!modal) return;
    if (modal._focusRelease) {
      modal._focusRelease();
      modal._focusRelease = null;
    }
    modal.classList.remove('is-open');
    setTimeout(function () { modal.classList.add('hidden'); }, 220);
  }

  function performHomeUninstallSelection(targetName) {
    var resultEl = document.getElementById('uninstall-target-modal-result');
    var cancelBtn = document.getElementById('uninstall-target-modal-cancel');
    var targetsEl = document.getElementById('uninstall-target-modal-targets');
    
    var goBtn = document.getElementById('home-uninstall-go-btn');
    var backBtn = document.getElementById('home-uninstall-back-btn');
    var inputEl = document.getElementById('home-uninstall-confirm-input');
    
    if (goBtn) { goBtn.disabled = true; goBtn.textContent = 'Removing...'; }
    if (backBtn) backBtn.disabled = true;
    if (inputEl) inputEl.disabled = true;

    fetch('/api/install/targets/' + encodeURIComponent(targetName) + '/skills/' + encodeURIComponent(currentActionSkill) + '/uninstall', {
      method: 'POST',
      credentials: 'include'
    })
    .then(function(res) { return res.json().then(function(d) { return { ok: res.ok, data: d }; }); })
    .then(function(r) {
      if (r.ok && r.data && r.data.status === 'ok') {
        var okMsg = '✓ Uninstalled from ' + targetName;
        if (resultEl) {
          resultEl.textContent = okMsg;
          resultEl.classList.add('is-ok');
          resultEl.classList.remove('hidden');
        }
        toast(okMsg, 'success');
        if (window.__installedMap[currentActionSkill]) {
          window.__installedMap[currentActionSkill] = window.__installedMap[currentActionSkill].filter(function(tgt) { return tgt !== targetName; });
        }
        decorateVisibleCards();
        setTimeout(closeHomeUninstallModal, 600);
      } else {
        var errMsg = '✗ Uninstall failed: ' + (r.data ? r.data.error : '');
        if (resultEl) {
          resultEl.textContent = errMsg;
          resultEl.classList.add('is-err');
          resultEl.classList.remove('hidden');
        }
        toast(errMsg, 'error');
        if (goBtn) { goBtn.disabled = false; goBtn.textContent = 'Remove'; }
        if (backBtn) backBtn.disabled = false;
        if (inputEl) inputEl.disabled = false;
      }
      if (cancelBtn) cancelBtn.textContent = 'Close';
    })
    .catch(function(err) {
      var netMsg = '✗ Network error';
      if (resultEl) {
        resultEl.textContent = netMsg;
        resultEl.classList.add('is-err');
        resultEl.classList.remove('hidden');
      }
      if (cancelBtn) cancelBtn.textContent = 'Close';
      toast(netMsg, 'error');
      if (goBtn) { goBtn.disabled = false; goBtn.textContent = 'Remove'; }
      if (backBtn) backBtn.disabled = false;
      if (inputEl) inputEl.disabled = false;
    });
  }

  // Map to store skillName -> array of installed targets
  window.__installedMap = window.__installedMap || {};

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
    Array.prototype.forEach.call(cards, function(card) {
      // Find quick buttons
      var installBtn = card.querySelector('.quick-install-btn');
      var uninstallBtn = card.querySelector('.quick-uninstall-btn');
      var targetsContainer = card.querySelector('.skill-card-targets');
      
      // Determine skill name
      var sName = '';
      if (installBtn) sName = installBtn.dataset.skill;
      else if (uninstallBtn) sName = uninstallBtn.dataset.skill;
      else if (targetsContainer) sName = targetsContainer.dataset.skillTargets;
      
      if (!sName) return;
      var tgts = window.__installedMap[sName] || [];
      
      if (installBtn) {
        if (tgts.length === 0) {
          installBtn.classList.remove('hidden');
        } else {
          installBtn.classList.add('hidden');
        }
      }
      if (uninstallBtn) {
        if (tgts.length > 0) {
          uninstallBtn.classList.remove('hidden');
          uninstallBtn.dataset.target = tgts[0];
        } else {
          uninstallBtn.classList.add('hidden');
        }
      }
      if (targetsContainer) {
        if (tgts.length > 0) {
          var html = '';
          tgts.forEach(function(t) {
            var ts = getTargetStyle(t);
            html += '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition-all hover:scale-105" style="background-color:' + ts.bg + ';border:1px solid ' + ts.border + ';color:' + ts.text + ';font-size:0.72rem;font-weight:600;box-shadow:0 2px 4px rgba(0,0,0,0.03);margin-right:6px;">' +
              '<span class="inline-block w-2 h-2 rounded-full" style="background-color:' + ts.dot + ';box-shadow:0 0 8px ' + ts.dot + ';"></span>' +
              '<span style="opacity:0.75;font-size:0.62rem;text-transform:uppercase;letter-spacing:0.06em;">Target</span>' +
              '<span style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">' + escapeHtml(t) + '</span>' +
            '</span>';
          });
          targetsContainer.innerHTML = html;
        } else {
          targetsContainer.innerHTML = '';
        }
      }
    });
  }

  // Handle click events via event delegation on skillGrid to keep event handlers fast and decoupled
  if (skillGrid) {
    skillGrid.addEventListener('click', function(ev) {
      var installBtn = ev.target.closest('.quick-install-btn');
      if (installBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        var sName = installBtn.dataset.skill;
        if (sName) openHomeInstallModal(sName);
        return;
      }
      var uninstallBtn = ev.target.closest('.quick-uninstall-btn');
      if (uninstallBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        var sNameU = uninstallBtn.dataset.skill;
        if (sNameU) openHomeUninstallModal(sNameU);
        return;
      }
    });
  }

  // Esc listener on open modal closes it
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var openModal = document.getElementById('install-modal');
      if (openModal && !openModal.classList.contains('hidden')) {
        e.preventDefault();
        e.stopPropagation();
        closeHomeInstallModal();
      }
      var openUninstallModal = document.getElementById('uninstall-target-modal');
      if (openUninstallModal && !openUninstallModal.classList.contains('hidden')) {
        e.preventDefault();
        e.stopPropagation();
        closeHomeUninstallModal();
      }
    }
  });

  // Load installed states immediately on load
  loadInstalledState();
})();
