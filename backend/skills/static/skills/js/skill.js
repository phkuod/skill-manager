'use strict';

(function () {
  var skillName = document.body.dataset.skillName || '';
  var version = document.body.dataset.version || '';

  if (!skillName) return;

  // Syntax-highlight server-rendered markdown code blocks (fenced code in
  // contentHtml) immediately. hljs is loaded before this script.
  if (window.hljs && window.hljs.highlightAll) window.hljs.highlightAll();

  // -------------------------------------------------------------------------
  // URL builders
  // -------------------------------------------------------------------------

  function filesUrl() {
    return version
      ? '/api/skills/' + encodeURIComponent(skillName) + '/versions/' + encodeURIComponent(version) + '/files'
      : '/api/skills/' + encodeURIComponent(skillName) + '/files';
  }

  function installPostUrl() {
    return version
      ? '/api/skills/' + encodeURIComponent(skillName) + '/versions/' + encodeURIComponent(version) + '/install'
      : '/api/skills/' + encodeURIComponent(skillName) + '/install';
  }

  // -------------------------------------------------------------------------
  // Install modal (preserve existing behavior verbatim)
  // -------------------------------------------------------------------------

  function getCookie(name) {
    var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : '';
  }

  function fetchInstallTargets() {
    return fetch('/api/install/targets')
      .then(function (res) { return res.ok ? res.json() : { targets: [] }; })
      .then(function (data) { return data.targets || []; })
      .catch(function () { return []; });
  }

  function openInstallModal() {
    var modal = document.getElementById('install-modal');
    var titleEl = document.getElementById('install-modal-title');
    var userEl = document.getElementById('install-modal-user');
    var noCookieEl = document.getElementById('install-modal-no-cookie');
    var targetsEl = document.getElementById('install-modal-targets');
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var closeBtn = document.getElementById('install-modal-close');

    var user = getCookie('CURRENT_USER_NAME');
    titleEl.textContent = skillName;
    userEl.textContent = user || 'no session';
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
        var path = (user ? t.base.replace('{user_name}', user) : t.base.replace('{user_name}', '<user>')) + '/' + skillName;
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
    requestAnimationFrame(function () { modal.classList.add('is-open'); });
  }

  function closeInstallModal() {
    var modal = document.getElementById('install-modal');
    modal.classList.remove('is-open');
    setTimeout(function () { modal.classList.add('hidden'); }, 220);
  }

  function performInstall(targetName, row) {
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var targetsEl = document.getElementById('install-modal-targets');
    Array.prototype.forEach.call(targetsEl.querySelectorAll('.install-target-btn'), function (b) { b.disabled = true; });
    row.dataset.state = 'busy';
    row.querySelector('.install-target-go').innerHTML = '⏳';

    fetch(installPostUrl(), {
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
          row.querySelector('.install-target-go').innerHTML = '✓';
          resultEl.textContent = '✓ Installed to ' + r.data.target + ' — ' + r.data.path;
          resultEl.classList.add('is-ok');
        } else {
          row.dataset.state = 'err';
          row.querySelector('.install-target-go').innerHTML = '✗';
          resultEl.textContent = '✗ ' + (r.data.error || 'Install failed');
          resultEl.classList.add('is-err');
        }
        resultEl.classList.remove('hidden');
        cancelBtn.textContent = 'Close';
      })
      .catch(function (err) {
        row.dataset.state = 'err';
        row.querySelector('.install-target-go').innerHTML = '✗';
        resultEl.textContent = '✗ Network error — ' + err.message;
        resultEl.classList.add('is-err');
        resultEl.classList.remove('hidden');
        cancelBtn.textContent = 'Close';
      });
  }

  // -------------------------------------------------------------------------
  // Install tabs
  // -------------------------------------------------------------------------

  Array.prototype.forEach.call(document.querySelectorAll('.install-tab'), function (tab) {
    tab.addEventListener('click', function () {
      var name = tab.dataset.tab;
      document.querySelectorAll('.install-tab').forEach(function (t) {
        t.classList.toggle('active', t.dataset.tab === name);
      });
      document.querySelectorAll('.install-tab-content').forEach(function (c) {
        c.classList.toggle('hidden', c.id !== 'tab-' + name);
      });
    });
  });

  // -------------------------------------------------------------------------
  // Version selector (path navigation)
  // -------------------------------------------------------------------------

  var versionSelect = document.getElementById('version-select');
  if (versionSelect) {
    versionSelect.addEventListener('change', function () {
      var v = versionSelect.value;
      window.location.href = '/skills/' + encodeURIComponent(skillName) + '/v/' + encodeURIComponent(v) + '/';
    });
  }

  // -------------------------------------------------------------------------
  // File viewer (lazy from /api/skills/<name>/files)
  // -------------------------------------------------------------------------

  function renderFiles(files) {
    var section = document.getElementById('files-section');
    var list = document.getElementById('files-list');
    if (!files || !files.length) return;
    section.classList.remove('hidden');
    list.innerHTML = files.map(function (f) {
      var content = f.truncated || f.content === null
        ? '<p style="color:var(--text-secondary);font-style:italic;padding:1rem">File too large to display.</p>'
        : '<pre><code class="hljs">' + escapeHtml(f.content || '') + '</code></pre>';
      return (
        '<details class="px-5 py-3"><summary style="cursor:pointer;color:var(--text-primary)">' +
          escapeHtml(f.path) +
        '</summary><div class="mt-3">' + content + '</div></details>'
      );
    }).join('');
    if (window.hljs && window.hljs.highlightAll) window.hljs.highlightAll();
  }

  fetch(filesUrl())
    .then(function (res) { return res.ok ? res.json() : []; })
    .then(renderFiles)
    .catch(function () { /* silent — files section just stays hidden */ });

  // -------------------------------------------------------------------------
  // Install button
  // -------------------------------------------------------------------------

  var installBtn = document.getElementById('install-button');
  if (installBtn) installBtn.onclick = openInstallModal;

  // -------------------------------------------------------------------------
  // Keyboard shortcuts
  //   Esc → back to catalog
  //   D   → trigger download link
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
})();
