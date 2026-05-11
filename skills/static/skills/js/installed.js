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

  const modal = document.getElementById('uninstall-modal');
  const modalCard = modal && modal.querySelector('.uninstall-modal-card');
  const modalClose = document.getElementById('uninstall-modal-close');
  const modalCancel = document.getElementById('uninstall-modal-cancel');
  const modalConfirm = document.getElementById('uninstall-modal-confirm');
  const modalInput = document.getElementById('uninstall-modal-confirm-input');
  const modalSkillName = document.getElementById('uninstall-modal-skill-name');
  const modalTarget = document.getElementById('uninstall-modal-target');
  const modalPath = document.getElementById('uninstall-modal-path');
  const modalFiles = document.getElementById('uninstall-modal-files');
  const modalMtime = document.getElementById('uninstall-modal-mtime');
  const modalTitle = document.getElementById('uninstall-modal-title');
  const modalResult = document.getElementById('uninstall-modal-result');

  let modalCtx = null;
  let lastFocus = null;

  function refreshConfirmState() {
    if (!modalCtx) return;
    const matches = modalInput.value.trim() === modalCtx.name;
    modalConfirm.disabled = !matches;
    modalConfirm.setAttribute('aria-disabled', String(!matches));
  }

  function setModalResult(message, isError) {
    if (!message) {
      modalResult.hidden = true;
      modalResult.textContent = '';
      modalResult.classList.remove('is-err', 'is-ok');
      return;
    }
    modalResult.textContent = message;
    modalResult.hidden = false;
    modalResult.classList.toggle('is-err', !!isError);
    modalResult.classList.toggle('is-ok', !isError);
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.remove('is-open');
    modal.hidden = true;
    modalInput.value = '';
    setModalResult('', false);
    modalConfirm.disabled = true;
    modalConfirm.setAttribute('aria-disabled', 'true');
    modalCtx = null;
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
    lastFocus = null;
  }

  async function submitUninstall() {
    if (!modalCtx) return;
    modalConfirm.disabled = true;
    modalCancel.disabled = true;
    modalConfirm.textContent = 'Removing…';
    setModalResult('', false);

    const url = `/api/install/targets/${encodeURIComponent(modalCtx.target)}/skills/${encodeURIComponent(modalCtx.name)}/uninstall`;
    try {
      const res = await fetch(url, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      if (!res.ok) {
        let msg;
        try { msg = (await res.json()).error || `HTTP ${res.status}`; }
        catch (_e) { msg = `HTTP ${res.status}`; }
        throw new Error(msg);
      }
      // Remove the row from the section, decrement counts
      const section = modalCtx.sectionEl;
      const cached = cache[modalCtx.target];
      if (cached) {
        cached.catalog = cached.catalog.filter((r) => r.name !== modalCtx.name);
        cached.orphan = cached.orphan.filter((r) => r.name !== modalCtx.name);
        const body = section.querySelector('.installed-target-body');
        renderSection(body, cached);
      }
      toast(`Removed "${modalCtx.name}" from ${modalCtx.target}`, 'success');
      closeModal();
    } catch (err) {
      setModalResult(err.message || String(err), true);
    } finally {
      modalConfirm.textContent = 'Remove';
      modalCancel.disabled = false;
      refreshConfirmState();
    }
  }

  function openUninstallModal(ctx) {
    if (!modal) return;
    modalCtx = ctx;
    lastFocus = ctx.triggerEl || document.activeElement;
    modalTitle.textContent = `Remove "${ctx.name}" from ${ctx.target}?`;
    modalTarget.textContent = ctx.target;
    modalPath.textContent = ctx.path;
    modalFiles.textContent = ctx.files !== '' && ctx.files != null ? ctx.files : '–';
    modalMtime.textContent = ctx.mtime || '–';
    modalSkillName.textContent = ctx.name;
    modalInput.value = '';
    setModalResult('', false);
    modalConfirm.disabled = true;
    modalConfirm.setAttribute('aria-disabled', 'true');
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add('is-open'));
    setTimeout(() => modalInput.focus(), 0);
  }

  window.openUninstallModal = openUninstallModal;

  if (modal) {
    modalInput.addEventListener('input', refreshConfirmState);
    modalConfirm.addEventListener('click', submitUninstall);
    modalCancel.addEventListener('click', closeModal);
    modalClose.addEventListener('click', closeModal);
    modal.addEventListener('click', (ev) => {
      if (ev.target === modal) closeModal();
    });
    document.addEventListener('keydown', (ev) => {
      if (modal.hidden) return;
      if (ev.key === 'Escape') {
        ev.preventDefault();
        closeModal();
      } else if (ev.key === 'Tab') {
        // simple focus trap: keep tab cycling inside the card
        const focusables = modalCard.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (ev.shiftKey && document.activeElement === first) {
          ev.preventDefault(); last.focus();
        } else if (!ev.shiftKey && document.activeElement === last) {
          ev.preventDefault(); first.focus();
        }
      }
    });
  }
})();
