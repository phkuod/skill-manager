'use strict';

// Copy-to-clipboard for install command blocks
// Accessible as a global for onclick handlers in the template.
function copyCommand(btn) {
  var code = btn.parentElement.querySelector('code');
  if (!code) return;
  var text = code.textContent;
  navigator.clipboard.writeText(text).then(function () {
    btn.classList.add('copied');
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>';
    setTimeout(function () {
      btn.classList.remove('copied');
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
    }, 2000);
  }).catch(function () {
    // Fallback for older browsers / non-https contexts
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    btn.classList.add('copied');
    setTimeout(function () { btn.classList.remove('copied'); }, 2000);
  });
}

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
    // Throws on network/server failure so the caller can show a retry card,
    // versus the existing empty-targets state which means "configured but none".
    return fetch('/api/install/targets')
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) { return data.targets || []; });
  }

  function renderTargetsRetry(container, retryFn) {
    container.innerHTML =
      '<div style="padding:1rem;text-align:center;color:var(--text-secondary);">' +
        '<p style="margin:0 0 0.6rem 0;font-size:0.85rem;">Could not load install targets.</p>' +
        '<button type="button" id="install-targets-retry" ' +
          'style="background:transparent;border:1px solid var(--border);color:var(--text-primary);' +
          'padding:5px 14px;border-radius:6px;font-size:0.8rem;cursor:pointer;">Retry</button>' +
      '</div>';
    var btn = document.getElementById('install-targets-retry');
    if (btn) btn.onclick = retryFn;
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

    function loadTargets() {
      targetsEl.innerHTML =
        '<p style="color:var(--text-secondary);font-size:0.85rem;margin:0;">Loading install targets…</p>';
      fetchInstallTargets().then(function (targets) {
        targetsEl.innerHTML = '';
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
      }).catch(function () {
        renderTargetsRetry(targetsEl, loadTargets);
      });
    }
    loadTargets();

    cancelBtn.onclick = closeInstallModal;
    closeBtn.onclick = closeInstallModal;
    modal.classList.remove('hidden');
    requestAnimationFrame(function () { modal.classList.add('is-open'); });
    // Trap keyboard focus inside the modal until close.
    modal._focusRelease = focusTrap(modal);
  }

  function closeInstallModal() {
    var modal = document.getElementById('install-modal');
    if (modal._focusRelease) {
      modal._focusRelease();
      modal._focusRelease = null;
    }
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
          var okMsg = '✓ Installed to ' + r.data.target + ' — ' + r.data.path;
          resultEl.textContent = okMsg;
          resultEl.classList.add('is-ok');
          // Auto-dismissing success toast — survives modal close.
          toast(okMsg, 'success');
        } else {
          row.dataset.state = 'err';
          row.querySelector('.install-target-go').innerHTML = '✗';
          var errMsg = '✗ ' + (r.data.error || 'Install failed');
          resultEl.textContent = errMsg;
          resultEl.classList.add('is-err');
          // Sticky error toast — must be dismissed manually.
          toast(errMsg, 'error');
        }
        resultEl.classList.remove('hidden');
        cancelBtn.textContent = 'Close';
      })
      .catch(function (err) {
        row.dataset.state = 'err';
        row.querySelector('.install-target-go').innerHTML = '✗';
        var netMsg = '✗ Network error — ' + err.message;
        resultEl.textContent = netMsg;
        resultEl.classList.add('is-err');
        resultEl.classList.remove('hidden');
        cancelBtn.textContent = 'Close';
        toast(netMsg, 'error');
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

  var currentFiles = [];

  // Minimal escape helper
  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function formatBytes(bytes) {
    if (bytes === undefined || bytes === null) return '';
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / 1048576).toFixed(1) + ' MB';
  }

  window.selectFile = function(filename) {
    var file = currentFiles.find(function(f) { return f.path === filename; });
    var panel = document.getElementById('file-content-panel');
    var title = document.getElementById('content-panel-title');
    
    if (title) title.textContent = filename;
    
    if (!file) {
      panel.innerHTML = '<p style="color:var(--text-secondary);font-style:italic">Select a file to view its content.</p>';
      return;
    }
    
    document.querySelectorAll('.file-nav-item').forEach(function(el) {
      if (el.dataset.filename === filename) {
        el.classList.add('font-bold');
        el.style.backgroundColor = 'var(--bg-secondary)';
      } else {
        el.classList.remove('font-bold');
        el.style.backgroundColor = 'transparent';
      }
    });

    if (file.truncated || file.content === null) {
      panel.innerHTML = '<p style="color:var(--text-secondary);font-style:italic;">File too large to display.</p>';
    } else if (filename === 'SKILL.md') {
      var compiled = document.getElementById('compiled-skill-md');
      var contentHtml = compiled ? compiled.innerHTML.trim() : '';
      if (contentHtml) {
        panel.innerHTML = '<div class="skill-markdown">' + contentHtml + '</div>';
      } else {
        renderCodeWithLineNumbers(panel, file.content, 'markdown');
      }
    } else {
      renderCodeWithLineNumbers(panel, file.content, '');
    }
  };

  function renderCodeWithLineNumbers(panel, content, extraClass) {
      var tempDiv = document.createElement('div');
      tempDiv.style.display = 'none';
      var codeEl = document.createElement('code');
      codeEl.className = 'hljs ' + extraClass;
      codeEl.textContent = content || '';
      tempDiv.appendChild(codeEl);
      document.body.appendChild(tempDiv);
      
      if (window.hljs && window.hljs.highlightElement) {
        window.hljs.highlightElement(codeEl);
      }
      
      var highlightedHtml = codeEl.innerHTML;
      document.body.removeChild(tempDiv);

      var lines = highlightedHtml.split('\n');
      var out = '<div style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.875rem; line-height: 1.5; padding: 1rem 0; overflow-x: hidden;">';
      
      var openTags = [];
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (i === lines.length - 1 && line === '') continue;
        
        var prefix = openTags.join('');
        var re = /<span[^>]*>|<\/span>/g;
        var match;
        while ((match = re.exec(line)) !== null) {
          if (match[0] === '</span>') {
            openTags.pop();
          } else {
            openTags.push(match[0]);
          }
        }
        var suffix = '';
        for (var j = openTags.length - 1; j >= 0; j--) {
          suffix += '</span>';
        }
        
        var lineNum = i + 1;
        var wrappedLine = prefix + line + suffix;
        if (!wrappedLine) wrappedLine = ' ';
        
        out += '<div style="display: flex; width: 100%;">';
        out += '<div style="flex: 0 0 auto; min-width: 3rem; text-align: right; padding-right: 1rem; color: var(--text-secondary); user-select: none; border-right: 1px solid var(--border); opacity: 0.5;">' + lineNum + '</div>';
        out += '<div style="flex: 1; min-width: 0; padding-left: 1rem; white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere; tab-size: 4;"><code class="hljs" style="background:transparent;padding:0;line-height:1.5;color:inherit;white-space:pre-wrap;">' + wrappedLine + '</code></div>';
        out += '</div>';
      }
      out += '</div>';

      panel.innerHTML = out;
  }

  window.toggleFolder = function(btn) {
    var children = btn.nextElementSibling;
    if (children) {
      var isHidden = children.classList.contains('hidden');
      if (isHidden) {
        children.classList.remove('hidden');
        btn.querySelector('.folder-arrow').style.transform = 'rotate(90deg)';
      } else {
        children.classList.add('hidden');
        btn.querySelector('.folder-arrow').style.transform = 'rotate(0deg)';
      }
    }
  };

  window.toggleFileExplorer = function() {
    var section = document.getElementById('files-section');
    if (section) {
      section.classList.toggle('collapsed');
    }
  };

  function buildTreeHtml(nodes, level) {
    var html = '';
    var indent = level * 1.5;
    nodes.forEach(function(node) {
      if (node.type === 'folder') {
        html += '<button onclick="toggleFolder(this)" class="transition-colors w-full text-left flex items-center gap-2 py-1.5 px-3 rounded" style="color: var(--text-primary); cursor: pointer; padding-left: ' + (indent + 0.75) + 'rem;">' +
                  '<svg class="folder-arrow transition-transform" style="width:12px;height:12px;color:var(--text-secondary);transform:rotate(0deg);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>' +
                  '<span style="font-size:1.1em">📁</span>' +
                  '<span class="font-bold">' + escapeHtml(node.name) + '</span>' +
                '</button>';
        html += '<div class="folder-children hidden">' + buildTreeHtml(node.children, level + 1) + '</div>';
      } else {
        html += '<button class="file-nav-item transition-colors w-full text-left flex items-center justify-between py-1.5 px-3 rounded" data-filename="' + escapeHtml(node.file.path) + '" onclick="selectFile(\'' + escapeHtml(node.file.path) + '\')" style="color: var(--text-primary); cursor: pointer; padding-left: ' + (indent + 1.5) + 'rem;">' +
                  '<div class="flex items-center gap-2">' +
                    '<span style="color:var(--text-secondary);font-size:1.1em">📄</span>' +
                    '<span>' + escapeHtml(node.name) + '</span>' +
                  '</div>' +
                  '<span style="color:var(--text-secondary); font-size:0.85em;">' + formatBytes(node.file.size) + '</span>' +
                '</button>';
      }
    });
    return html;
  }

  function renderFiles(files) {
    currentFiles = files || [];
    var filesSection = document.getElementById('files-section');
    var contentSection = document.getElementById('content-section');
    var list = document.getElementById('files-list');
    var badge = document.getElementById('file-count-badge');
    
    if (!currentFiles.length) return;
    if (filesSection) filesSection.classList.remove('hidden');
    if (contentSection) contentSection.classList.remove('hidden');
    if (badge) badge.textContent = currentFiles.length + ' files';
    
    var tree = [];
    currentFiles.forEach(function(f) {
      var parts = f.path.split('/');
      var currentLevel = tree;
      for (var i=0; i < parts.length - 1; i++) {
        var part = parts[i];
        var existing = currentLevel.find(function(item) { return item.name === part && item.type === 'folder'; });
        if (!existing) {
          existing = { name: part, type: 'folder', children: [] };
          currentLevel.push(existing);
        }
        currentLevel = existing.children;
      }
      currentLevel.push({ name: parts[parts.length - 1], type: 'file', file: f });
    });

    list.innerHTML = buildTreeHtml(tree, 0);
    
    var defaultFile = currentFiles.find(function(f) { return f.path === 'SKILL.md'; });
    if (defaultFile) {
      selectFile('SKILL.md');
    } else {
      // If no SKILL.md, show a placeholder in the content panel rather than just
      // picking a random file. This provides a better UX.
      var panel = document.getElementById('file-content-panel');
      var title = document.getElementById('content-panel-title');
      if (title) title.textContent = 'Documentation';
      if (panel) {
        panel.innerHTML = 
          '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:4rem 2rem;text-align:center;color:var(--text-secondary);">' +
            '<div style="font-size:3rem;margin-bottom:1rem;opacity:0.5;">📄</div>' +
            '<h3 style="font-size:1.1rem;font-weight:600;margin-bottom:0.5rem;color:var(--text-primary);">No documentation provided</h3>' +
            '<p style="font-size:0.9rem;max-width:300px;">This skill doesn\'t have a SKILL.md file. You can still explore its source files in the sidebar.</p>' +
          '</div>';
      }
    }
  }

  // -------------------------------------------------------------------------
  // File-tree loading + retry
  // -------------------------------------------------------------------------

  (function injectSkeletonStyles() {
    if (document.getElementById('skill-skeleton-styles')) return;
    var s = document.createElement('style');
    s.id = 'skill-skeleton-styles';
    s.textContent =
      '@keyframes skill-skeleton-pulse{0%,100%{opacity:0.4}50%{opacity:0.7}}';
    document.head.appendChild(s);
  })();

  function renderFilesSkeleton() {
    var list = document.getElementById('files-list');
    var filesSection = document.getElementById('files-section');
    if (!list) return;
    if (filesSection) filesSection.classList.remove('hidden');
    var html = '';
    for (var i = 0; i < 5; i++) {
      var bar = (60 + (i * 7) % 30);
      html +=
        '<div style="padding:8px 12px;display:flex;align-items:center;gap:8px;">' +
          '<div style="width:14px;height:14px;background:var(--bg-secondary);border-radius:3px;opacity:0.5;"></div>' +
          '<div style="flex:0 0 ' + bar + '%;height:10px;background:var(--bg-secondary);border-radius:3px;' +
            'animation:skill-skeleton-pulse 1.4s ease-in-out infinite;"></div>' +
        '</div>';
    }
    list.innerHTML = html;
  }

  function renderFilesError(retryFn) {
    var list = document.getElementById('files-list');
    var filesSection = document.getElementById('files-section');
    if (!list) return;
    if (filesSection) filesSection.classList.remove('hidden');
    list.innerHTML =
      '<div style="padding:1.25rem;text-align:center;color:var(--text-secondary);">' +
        '<p style="margin:0 0 0.6rem 0;font-size:0.9rem;">Could not load files.</p>' +
        '<button type="button" id="files-retry-btn" ' +
          'style="background:transparent;border:1px solid var(--border);color:var(--text-primary);' +
          'padding:6px 14px;border-radius:6px;font-size:0.85rem;cursor:pointer;">Retry</button>' +
      '</div>';
    var btn = document.getElementById('files-retry-btn');
    if (btn) btn.onclick = retryFn;
  }

  function loadFiles() {
    renderFilesSkeleton();
    fetch(filesUrl())
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(renderFiles)
      .catch(function () { renderFilesError(loadFiles); });
  }

  loadFiles();

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
    // Esc on an open install modal closes it instead of navigating away.
    // Runs before isTypingTarget so the close still works while focus is
    // on a modal control.
    if (e.key === 'Escape') {
      var openModal = document.getElementById('install-modal');
      if (openModal && !openModal.classList.contains('hidden')) {
        e.preventDefault();
        closeInstallModal();
        return;
      }
    }

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
