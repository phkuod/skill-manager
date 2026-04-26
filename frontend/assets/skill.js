'use strict';

(function () {
  var API_BASE = (window.API_BASE || '').replace(/\/$/, '');

  var root = document.getElementById('skill-root');
  var loadState = document.getElementById('load-state');

  // Parse /skill/<name> and optional ?version=<v>
  var pathParts = window.location.pathname.split('/').filter(Boolean);
  var skillName = pathParts.length >= 2 && pathParts[0] === 'skill' ? decodeURIComponent(pathParts[1]) : null;

  function getVersion() {
    var params = new URLSearchParams(window.location.search);
    return params.get('version') || '';
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

  function fileUrl(name, version, path) {
    return apiBase(name, version) + '/files/' + path.split('/').map(encodeURIComponent).join('/');
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
      var next = '/skill/' + encodeURIComponent(skillName) + (v ? '?version=' + encodeURIComponent(v) : '');
      history.pushState({}, '', next);
      load();
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

  // Each entry from /files (metadata mode) is {path, language, size, truncated?}.
  // The body is fetched on first expand and cached in-memory in the row's
  // .file-body element.

  function formatSize(bytes) {
    if (bytes == null) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  function renderFileBody(bodyEl, file) {
    if (file.truncated) {
      bodyEl.innerHTML = '<div class="px-5 py-4 text-sm italic" style="color:var(--text-secondary)">File too large to preview.</div>';
    } else if (file.language === 'markdown') {
      bodyEl.innerHTML = '<div class="px-5 py-4 skill-markdown">' + window.marked.parse(file.content || '') + '</div>';
    } else {
      bodyEl.innerHTML = '<pre class="px-5 py-4 overflow-x-auto text-sm m-0"><code class="language-' + escapeHtml(file.language) + '">' + escapeHtml(file.content || '') + '</code></pre>';
      if (typeof hljs !== 'undefined') {
        bodyEl.querySelectorAll('pre code').forEach(function (block) {
          hljs.highlightElement(block);
        });
      }
    }
  }

  function renderFiles(files) {
    var section = document.getElementById('files-section');
    var list = document.getElementById('files-list');
    if (!files || files.length === 0) {
      section.classList.add('hidden');
      list.innerHTML = '';
      return;
    }

    list.innerHTML = files.map(function (f, idx) {
      var sizeLabel = formatSize(f.size);
      var header =
        '<button type="button" class="file-header w-full flex items-center justify-between px-5 py-3 text-left" data-idx="' + idx + '" style="background-color:var(--bg-secondary)">' +
          '<span class="flex items-center gap-2 min-w-0">' +
            '<svg class="file-chevron w-4 h-4 flex-shrink-0 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>' +
            '<span class="text-sm font-mono truncate" style="color:var(--text-primary)">' + escapeHtml(f.path) + '</span>' +
          '</span>' +
          '<span class="flex items-center gap-2 flex-shrink-0">' +
            (sizeLabel ? '<span class="text-xs" style="color:var(--text-secondary)">' + escapeHtml(sizeLabel) + '</span>' : '') +
            '<span class="text-xs px-2 py-0.5 rounded border" style="color:var(--text-secondary);border-color:var(--border)">' + escapeHtml(f.language) + '</span>' +
          '</span>' +
        '</button>' +
        '<div class="file-body hidden"></div>';

      return '<div class="file-block" data-idx="' + idx + '">' + header + '</div>';
    }).join('');

    section.classList.remove('hidden');

    var version = getVersion();
    list.querySelectorAll('.file-block').forEach(function (block) {
      var idx = +block.dataset.idx;
      var file = files[idx];
      var header = block.querySelector('.file-header');
      var body = block.querySelector('.file-body');
      var chevron = block.querySelector('.file-chevron');
      var loaded = false;
      var loading = false;

      header.addEventListener('click', function () {
        if (loading) return;
        var isHidden = body.classList.contains('hidden');
        if (!isHidden) {
          body.classList.add('hidden');
          chevron.style.transform = '';
          return;
        }

        body.classList.remove('hidden');
        chevron.style.transform = 'rotate(90deg)';

        if (loaded) return;

        if (file.truncated) {
          renderFileBody(body, file);
          loaded = true;
          return;
        }

        loading = true;
        body.innerHTML = '<div class="px-5 py-4 text-sm" style="color:var(--text-secondary)">Loading…</div>';
        fetch(fileUrl(skillName, version, file.path))
          .then(function (res) {
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return res.json();
          })
          .then(function (data) {
            renderFileBody(body, data);
            loaded = true;
            loading = false;
          })
          .catch(function () {
            body.innerHTML = '<div class="px-5 py-4 text-sm" style="color:var(--text-secondary)">Failed to load file.</div>';
            loading = false;
          });
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Load pipeline
  // ---------------------------------------------------------------------------

  function load() {
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

  window.addEventListener('popstate', load);

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
      window.location.href = '/';
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
