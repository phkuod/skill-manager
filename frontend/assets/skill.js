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

  load();
})();
