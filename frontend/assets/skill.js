'use strict';

(function () {
  var API_BASE = (window.API_BASE || '').replace(/\/$/, '');

  var root = document.getElementById('skill-root');
  var loadState = document.getElementById('load-state');

  // Hash format: #<name>  or  #<name>?version=<v>
  // Hash-based routing keeps the page deployable on any plain static host
  // (no per-path rewrite rules needed for /skill/<name>).
  function parseHash() {
    var raw = window.location.hash.slice(1);
    var qIdx = raw.indexOf('?');
    var name = qIdx >= 0 ? raw.slice(0, qIdx) : raw;
    var query = qIdx >= 0 ? raw.slice(qIdx + 1) : '';
    return {
      name: name ? decodeURIComponent(name) : null,
      version: new URLSearchParams(query).get('version') || '',
    };
  }

  var skillName = null;

  function getVersion() {
    return parseHash().version;
  }

  function apiBase(name, version) {
    var base = API_BASE + '/api/skills/' + encodeURIComponent(name);
    if (!version) return base;
    return base + '/versions/' + encodeURIComponent(version);
  }

  function detailUrl(name, version) {
    return apiBase(name, version);
  }

  function filesUrl(name, version) {
    return apiBase(name, version) + '/files';
  }

  function zipUrl(name, version) {
    return apiBase(name, version) + '/zip';
  }

  function showError(msg) {
    loadState.textContent = msg;
    loadState.classList.remove('hidden');
    root.classList.add('hidden');
  }

  // ---------------------------------------------------------------------------
  // Install — helpers
  // ---------------------------------------------------------------------------

  function getCookie(name) {
    var prefix = name + '=';
    var parts = document.cookie.split(';');
    for (var i = 0; i < parts.length; i++) {
      var c = parts[i].trim();
      if (c.indexOf(prefix) === 0) return decodeURIComponent(c.slice(prefix.length));
    }
    return '';
  }

  function fetchInstallTargets() {
    return fetch(API_BASE + '/api/install/targets')
      .then(function (r) { return r.ok ? r.json() : { targets: [] }; })
      .then(function (data) { return data.targets || []; })
      .catch(function () { return []; });
  }

  function installUrl(name, version) {
    return apiBase(name, version) + '/install';
  }

  function openInstallModal() {
    var modal = document.getElementById('install-modal');
    var title = document.getElementById('install-modal-title');
    var userEl = document.getElementById('install-modal-user');
    var targetsEl = document.getElementById('install-modal-targets');
    var noCookieEl = document.getElementById('install-modal-no-cookie');
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var closeBtn = document.getElementById('install-modal-close');

    var version = getVersion();
    title.textContent = skillName + (version ? ' @ ' + version : '');

    var user = getCookie('CURRENT_USER_NAME');
    userEl.textContent = user || 'no session';

    // Reset modal state every open
    resultEl.classList.add('hidden');
    resultEl.classList.remove('is-ok', 'is-err');
    resultEl.textContent = '';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.disabled = false;
    noCookieEl.classList.toggle('hidden', !!user);
    targetsEl.innerHTML = '';

    fetchInstallTargets().then(function (targets) {
      if (!targets.length) {
        var empty = document.createElement('p');
        empty.style.color = 'var(--text-secondary)';
        empty.style.fontSize = '0.85rem';
        empty.style.margin = '0';
        empty.textContent = 'No install targets configured — set INSTALL_TARGET_* env vars on the backend.';
        targetsEl.appendChild(empty);
        return;
      }
      targets.forEach(function (t) {
        var path = (user
          ? t.base.replace('{user_name}', user)
          : t.base.replace('{user_name}', '<user>')) + '/' + skillName;
        var row = document.createElement('button');
        row.type = 'button';
        row.className = 'install-target-btn';
        row.disabled = !user;
        row.innerHTML =
          '<span class="install-target-name">' + escapeHtml(t.name) + '</span>' +
          '<span class="install-target-path">' + escapeHtml(path) + '</span>' +
          '<span class="install-target-go">&rarr;</span>';
        row.onclick = function () { performInstall(t.name, row); };
        targetsEl.appendChild(row);
      });
    });

    cancelBtn.onclick = closeInstallModal;
    closeBtn.onclick = closeInstallModal;
    modal.classList.remove('hidden');
    // Trigger entrance animation on next frame
    requestAnimationFrame(function () { modal.classList.add('is-open'); });
  }

  function closeInstallModal() {
    var modal = document.getElementById('install-modal');
    modal.classList.remove('is-open');
    // Hide after exit animation completes (matches CSS transition duration).
    setTimeout(function () { modal.classList.add('hidden'); }, 220);
  }

  function performInstall(targetName, row) {
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var allRows = document.querySelectorAll('.install-target-btn');

    Array.prototype.forEach.call(allRows, function (r) { r.disabled = true; });
    row.setAttribute('data-state', 'busy');
    row.querySelector('.install-target-go').innerHTML = '&#8987;'; // hourglass

    fetch(installUrl(skillName, getVersion()), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: targetName }),
    })
      .then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, body: j }; });
      })
      .then(function (out) {
        resultEl.classList.remove('hidden');
        if (out.ok) {
          resultEl.classList.remove('is-err');
          resultEl.classList.add('is-ok');
          resultEl.textContent = '✓ Installed to ' + out.body.target + ' — ' + out.body.path;
          row.setAttribute('data-state', 'ok');
          row.querySelector('.install-target-go').textContent = '✓';
        } else {
          resultEl.classList.remove('is-ok');
          resultEl.classList.add('is-err');
          resultEl.textContent = '✗ ' + (out.body.error || 'Install failed');
          row.setAttribute('data-state', 'err');
          row.querySelector('.install-target-go').textContent = '✗';
        }
      })
      .catch(function (err) {
        resultEl.classList.remove('hidden', 'is-ok');
        resultEl.classList.add('is-err');
        resultEl.textContent = '✗ Network error — ' + err.message;
        row.setAttribute('data-state', 'err');
        row.querySelector('.install-target-go').textContent = '✗';
      })
      .finally(function () {
        cancelBtn.textContent = 'Close';
        cancelBtn.disabled = false;
      });
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  function renderSkill(skill) {
    document.getElementById('page-title').textContent = skill.name + ' — Skill Market';

    document.getElementById('skill-icon').textContent = skill.icon || '📦';
    document.getElementById('skill-name').textContent = skill.name;

    var cat = document.getElementById('skill-category');
    cat.textContent = skill.category || '';
    cat.setAttribute('data-category', skill.category || '');

    document.getElementById('skill-license').textContent = skill.license || 'Unknown';
    document.getElementById('skill-description').textContent = skill.description || '';

    // Sidebar
    document.getElementById('detail-files').textContent = skill.fileCount != null ? skill.fileCount : '';
    document.getElementById('detail-license').textContent = skill.license || 'Unknown';
    document.getElementById('detail-category').textContent = skill.category || '';
    document.getElementById('detail-updated').textContent = relativeTime(skill.lastUpdated) || (skill.lastUpdated || '').slice(0, 10);

    // Install paths + commands
    var paths = skill.installPaths || {};
    var repo = skill.repoPath || '';
    document.getElementById('path-claude').textContent = paths.claudeCode || '';
    document.getElementById('path-opencode').textContent = paths.opencode || '';
    document.getElementById('cmd-claude').textContent = 'cp -r "' + repo + '" "' + (paths.claudeCode || '') + '"';
    document.getElementById('cmd-opencode').textContent = 'cp -r "' + repo + '" "' + (paths.opencode || '') + '"';

    // Download link — respects current version
    document.getElementById('download-link').setAttribute('href', zipUrl(skillName, getVersion()));

    var installBtn = document.getElementById('install-button');
    if (installBtn) installBtn.onclick = openInstallModal;

    // Markdown content
    var contentEl = document.getElementById('skill-content');
    contentEl.innerHTML = skill.content ? window.marked.parse(skill.content) : '';

    // Version dropdown — only on pages with versions (queried from skill metadata)
    renderVersionSelector(skill);

    // Install tabs
    wireInstallTabs();

    root.classList.remove('hidden');
    loadState.classList.add('hidden');
  }

  function renderVersionSelector(skill) {
    var row = document.getElementById('version-row');
    var select = document.getElementById('version-select');
    if (!skill.versions || skill.versions.length === 0) {
      row.classList.add('hidden');
      row.classList.remove('flex');
      return;
    }

    var current = getVersion() || skill.currentVersion || '';
    select.innerHTML = skill.versions.map(function (v) {
      var label = v.version + (v.date ? ' (' + v.date + ')' : '');
      return '<option value="' + escapeHtml(v.version) + '">' + escapeHtml(label) + '</option>';
    }).join('');
    select.value = current;

    row.classList.remove('hidden');
    row.classList.add('flex');

    select.onchange = function () {
      var v = select.value;
      var encoded = encodeURIComponent(skillName);
      window.location.hash = encoded + (v ? '?version=' + encodeURIComponent(v) : '');
      // hashchange listener (below) reruns load()
    };
  }

  function wireInstallTabs() {
    Array.prototype.forEach.call(document.querySelectorAll('.install-tab'), function (tab) {
      tab.onclick = function () {
        var target = tab.dataset.tab;
        document.querySelectorAll('.install-tab').forEach(function (t) {
          t.classList.toggle('active', t.dataset.tab === target);
        });
        document.querySelectorAll('.install-tab-content').forEach(function (c) {
          c.classList.toggle('hidden', c.id !== 'tab-' + target);
        });
      };
    });
  }

  // ---------------------------------------------------------------------------
  // Files
  // ---------------------------------------------------------------------------

  function renderFiles(files) {
    var section = document.getElementById('files-section');
    var list = document.getElementById('files-list');
    if (!files || files.length === 0) {
      section.classList.add('hidden');
      list.innerHTML = '';
      return;
    }

    list.innerHTML = files.map(function (f) {
      var header =
        '<div class="flex items-center justify-between px-5 py-3" style="background-color:var(--bg-secondary)">' +
          '<span class="text-sm font-mono" style="color:var(--text-primary)">' + escapeHtml(f.path) + '</span>' +
          '<span class="text-xs px-2 py-0.5 rounded border ml-2 flex-shrink-0" style="color:var(--text-secondary);border-color:var(--border)">' + escapeHtml(f.language) + '</span>' +
        '</div>';

      var body;
      if (f.truncated) {
        body = '<div class="px-5 py-4 text-sm italic" style="color:var(--text-secondary)">File too large to preview.</div>';
      } else if (f.language === 'markdown') {
        body = '<div class="px-5 py-4 skill-markdown">' + window.marked.parse(f.content || '') + '</div>';
      } else {
        body = '<pre class="px-5 py-4 overflow-x-auto text-sm m-0"><code class="language-' + escapeHtml(f.language) + '">' + escapeHtml(f.content || '') + '</code></pre>';
      }

      return '<div class="file-block">' + header + body + '</div>';
    }).join('');

    section.classList.remove('hidden');

    // Syntax highlighting
    if (typeof hljs !== 'undefined') {
      list.querySelectorAll('pre code').forEach(function (block) {
        hljs.highlightElement(block);
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Load pipeline
  // ---------------------------------------------------------------------------

  function load() {
    skillName = parseHash().name;
    if (!skillName) {
      showError('Skill not found.');
      return;
    }

    loadState.textContent = 'Loading…';
    loadState.classList.remove('hidden');
    root.classList.add('hidden');

    var version = getVersion();

    Promise.all([
      fetch(detailUrl(skillName, version)),
      fetch(filesUrl(skillName, version)),
    ]).then(function (responses) {
      var detailRes = responses[0];
      var filesRes = responses[1];
      if (detailRes.status === 404) {
        throw new Error('not-found');
      }
      if (!detailRes.ok) throw new Error('detail ' + detailRes.status);
      return Promise.all([
        detailRes.json(),
        filesRes.ok ? filesRes.json() : [],
      ]);
    }).then(function (data) {
      var skill = data[0];
      var files = data[1];
      renderSkill(skill);
      renderFiles(files);
    }).catch(function (err) {
      if (err && err.message === 'not-found') {
        showError("Skill '" + skillName + "' not found.");
      } else {
        showError('Failed to load skill. Refresh to try again.');
      }
    });
  }

  window.addEventListener('hashchange', load);

  // -------------------------------------------------------------------------
  // Keyboard shortcuts
  //   Esc   navigate back to the catalog
  //   d     trigger Download ZIP for the current skill / version
  // -------------------------------------------------------------------------

  document.addEventListener('keydown', function (e) {
    if (isTypingTarget(e.target)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === 'Escape') {
      e.preventDefault();
      window.location.href = 'index.html';
      return;
    }

    if (e.key === 'd' || e.key === 'D') {
      var link = document.getElementById('download-link');
      if (!link) return;
      e.preventDefault();
      link.click();
    }
  });

  load();
})();
