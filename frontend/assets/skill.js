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
    var actionsEl = document.getElementById('install-modal-actions');
    var cancelBtn = document.getElementById('install-modal-cancel');

    var version = getVersion();
    var titleText = 'Install "' + skillName + '"' + (version ? ' (' + version + ')' : '');
    title.textContent = titleText;

    var user = getCookie('CURRENT_USER_NAME');
    userEl.textContent = user || '(none)';

    // Reset modal state
    resultEl.classList.add('hidden');
    resultEl.textContent = '';
    resultEl.removeAttribute('style');
    cancelBtn.textContent = 'Cancel';

    // Remove previously-injected install buttons (idempotent re-open)
    Array.prototype.forEach.call(
      actionsEl.querySelectorAll('.install-target-btn'),
      function (b) { b.remove(); }
    );

    targetsEl.innerHTML = '';
    noCookieEl.classList.toggle('hidden', !!user);

    fetchInstallTargets().then(function (targets) {
      if (!targets.length) {
        targetsEl.innerHTML = '<li style="color:var(--text-secondary)">'
          + '(no install targets configured — set INSTALL_TARGET_* env vars)</li>';
        return;
      }
      targetsEl.innerHTML = targets.map(function (t) {
        var path = user
          ? t.base.replace('{user_name}', user) + '/' + skillName
          : t.base.replace('{user_name}', '<user>') + '/' + skillName;
        return '<li class="font-mono text-xs" style="color:var(--text-primary)">'
          + escapeHtml(t.name) + ' &rarr; ' + escapeHtml(path) + '</li>';
      }).join('');

      targets.forEach(function (t) {
        var btn = document.createElement('button');
        btn.className = 'install-target-btn px-3 py-2 text-sm rounded-lg font-medium text-white';
        btn.style.backgroundColor = 'var(--accent)';
        btn.textContent = 'Install to ' + t.name;
        btn.disabled = !user;
        if (!user) btn.style.opacity = '0.5';
        btn.onclick = function () { performInstall(t.name, btn); };
        actionsEl.insertBefore(btn, cancelBtn);
      });
    });

    cancelBtn.onclick = closeInstallModal;
    modal.classList.remove('hidden');
  }

  function closeInstallModal() {
    document.getElementById('install-modal').classList.add('hidden');
  }

  function performInstall(targetName, clickedBtn) {
    var actionsEl = document.getElementById('install-modal-actions');
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var allBtns = actionsEl.querySelectorAll('button');
    Array.prototype.forEach.call(allBtns, function (b) { b.disabled = true; });
    clickedBtn.textContent = 'Installing…';

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
          resultEl.style.backgroundColor = 'var(--result-ok-bg)';
          resultEl.style.color = 'var(--result-ok-text)';
          resultEl.textContent = '✓ Installed to ' + out.body.target + ': ' + out.body.path;
        } else {
          resultEl.style.backgroundColor = 'var(--result-err-bg)';
          resultEl.style.color = 'var(--result-err-text)';
          resultEl.textContent = '✗ ' + (out.body.error || 'Install failed');
        }
      })
      .catch(function (err) {
        resultEl.classList.remove('hidden');
        resultEl.style.backgroundColor = 'var(--result-err-bg)';
        resultEl.style.color = 'var(--result-err-text)';
        resultEl.textContent = '✗ Network error: ' + err.message;
      })
      .finally(function () {
        // Hide install buttons; turn Cancel into Close.
        Array.prototype.forEach.call(
          actionsEl.querySelectorAll('.install-target-btn'),
          function (b) { b.remove(); }
        );
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
