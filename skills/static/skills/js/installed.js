(function () {
  'use strict';

  // common.js exposes window.escapeHtml and window.toast
  const escapeHtml = window.escapeHtml || ((s) => String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]));
  const toast = window.toast || ((msg) => console.log('toast:', msg));

  const bootstrapEl = document.getElementById('installed-bootstrap');
  const TARGETS = bootstrapEl ? JSON.parse(bootstrapEl.textContent || '[]') : [];
  const cache = {}; // target -> {catalog, orphan, base}

  function fmtMtime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  }

  function renderRow(row, isOrphan) {
    const safeName = escapeHtml(row.name);
    const safePath = escapeHtml(row.path);
    const safeMtime = escapeHtml(fmtMtime(row.mtime));
    const icon = !isOrphan && row.icon ? escapeHtml(row.icon) : '📁';
    const description = !isOrphan && row.description ? escapeHtml(row.description) : '';
    const fileCount = !isOrphan && (row.fileCount || row.fileCount === 0) ? row.fileCount : '';
    const orphanClass = isOrphan ? ' installed-card-orphan' : '';
    const orphanBadge = isOrphan ? '<span class="installed-card-badge">Not in catalog</span>' : '';
    const filesLine = fileCount !== '' ? `${fileCount} files · ` : '';

    return (
      `<div class="installed-card${orphanClass}" data-name="${safeName}">
        <div class="installed-card-icon">${icon}</div>
        <div class="installed-card-body">
          <div class="installed-card-name">${safeName} ${orphanBadge}</div>
          ${description ? `<div class="installed-card-desc">${description}</div>` : ''}
          <div class="installed-card-meta">${filesLine}updated ${safeMtime}</div>
          <div class="installed-card-path">${safePath}</div>
        </div>
        <button type="button" class="installed-uninstall-btn"
                data-name="${safeName}"
                data-path="${safePath}"
                data-mtime="${safeMtime}"
                data-files="${fileCount}">Uninstall</button>
      </div>`
    );
  }

  function renderSection(body, data) {
    const catalogRows = data.catalog.map((r) => renderRow(r, false)).join('');
    const orphanRows = data.orphan.map((r) => renderRow(r, true)).join('');
    const html =
      `<div class="installed-group">
        <div class="installed-group-title">In catalog (${data.catalog.length})</div>
        ${data.catalog.length === 0 ? '<div class="installed-empty">No catalog skills installed on this target.</div>' : catalogRows}
      </div>` +
      (data.orphan.length > 0 ?
        `<div class="installed-group">
           <div class="installed-group-title">Not in catalog (${data.orphan.length})</div>
           ${orphanRows}
         </div>` : '');
    body.innerHTML = html;
    wireUninstallButtons(body);
  }

  function renderLoading(body) {
    body.innerHTML =
      '<div class="installed-skeleton"></div>'.repeat(3);
  }

  function renderError(body, message, retryFn) {
    body.innerHTML =
      `<div class="installed-error">
        <span>Couldn't reach target — ${escapeHtml(message)}</span>
        <button type="button" class="btn-secondary installed-retry-btn">Retry</button>
      </div>`;
    const btn = body.querySelector('.installed-retry-btn');
    if (btn) btn.addEventListener('click', retryFn);
  }

  async function fetchTarget(targetName) {
    const res = await fetch(`/api/install/targets/${encodeURIComponent(targetName)}/skills`, {
      credentials: 'include',
    });
    if (!res.ok) {
      let msg;
      try { msg = (await res.json()).error || `HTTP ${res.status}`; }
      catch (_e) { msg = `HTTP ${res.status}`; }
      throw new Error(msg);
    }
    return res.json();
  }

  function wireUninstallButtons(scope) {
    scope.querySelectorAll('.installed-uninstall-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const section = btn.closest('.installed-target');
        openUninstallModal({
          target: section.dataset.target,
          name: btn.dataset.name,
          path: btn.dataset.path,
          mtime: btn.dataset.mtime,
          files: btn.dataset.files,
          triggerEl: btn,
          sectionEl: section,
        });
      });
    });
  }

  async function loadSection(section, force) {
    const targetName = section.dataset.target;
    const body = section.querySelector('.installed-target-body');
    if (!force && cache[targetName]) {
      renderSection(body, cache[targetName]);
      return;
    }
    renderLoading(body);
    try {
      const data = await fetchTarget(targetName);
      cache[targetName] = data;
      renderSection(body, data);
    } catch (err) {
      renderError(body, err.message || String(err), () => loadSection(section, true));
    }
  }

  function wireSection(section) {
    const header = section.querySelector('.installed-target-header');
    const body = section.querySelector('.installed-target-body');
    const caret = section.querySelector('.installed-target-caret');
    const refresh = section.querySelector('.installed-target-refresh');

    header.addEventListener('click', (ev) => {
      if (refresh && refresh.contains(ev.target)) return;
      const expanded = header.getAttribute('aria-expanded') === 'true';
      const next = !expanded;
      header.setAttribute('aria-expanded', String(next));
      body.hidden = !next;
      caret.textContent = next ? '▾' : '▸';
      if (refresh) refresh.hidden = !next;
      if (next) loadSection(section, false);
    });

    if (refresh) {
      refresh.addEventListener('click', (ev) => {
        ev.stopPropagation();
        loadSection(section, true);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.installed-target').forEach(wireSection);
    // Mark nav link as current page for active styling
    const nav = document.getElementById('nav-installed');
    if (nav) nav.setAttribute('aria-current', 'page');
  });

  // Expose openUninstallModal placeholder; real impl appended in Task 13.
  window.openUninstallModal = window.openUninstallModal || function () {};
})();
