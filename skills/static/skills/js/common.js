'use strict';

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------
// Initial .dark class is set by an inline <script> in the <head> to prevent
// flash; this file handles the toggle button + syncing the sun/moon icons.

function applyThemeIcons() {
  var isDark = document.documentElement.classList.contains('dark');
  var sun = document.getElementById('icon-sun');
  var moon = document.getElementById('icon-moon');
  if (sun) sun.classList.toggle('hidden', !isDark);
  if (moon) moon.classList.toggle('hidden', isDark);
}

function toggleTheme() {
  var next = !document.documentElement.classList.contains('dark');
  document.documentElement.classList.toggle('dark', next);
  localStorage.setItem('theme', next ? 'dark' : 'light');
  var themeLink = document.getElementById('hljs-theme');
  if (themeLink) {
    var basePath = themeLink.href.substring(0, themeLink.href.lastIndexOf('/'));
    themeLink.href = basePath + (next ? '/github-dark.min.css' : '/github.min.css');
  }
  applyThemeIcons();
}

// ---------------------------------------------------------------------------
// Relative time
// ---------------------------------------------------------------------------

function relativeTime(isoString) {
  var then = new Date(isoString).getTime();
  if (isNaN(then)) return '';
  var diffMs = Date.now() - then;
  var mins = Math.floor(diffMs / 60000);
  if (mins < 60) return mins + 'm ago';
  var hours = Math.floor(mins / 60);
  if (hours < 24) return hours + 'h ago';
  var days = Math.floor(hours / 24);
  if (days < 30) return days + 'd ago';
  var months = Math.floor(days / 30);
  return months + 'mo ago';
}

// ---------------------------------------------------------------------------
// Keyboard helpers
// ---------------------------------------------------------------------------

// True if the event's target is a text-entry surface, so global single-key
// shortcuts (e.g. `/`, `d`) should not fire.
function isTypingTarget(el) {
  if (!el) return false;
  var tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  return !!el.isContentEditable;
}

// ---------------------------------------------------------------------------
// HTML escaping — used by page scripts when building markup from API data
// ---------------------------------------------------------------------------

function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ---------------------------------------------------------------------------
// Toasts (top-level, persistent feedback)
// ---------------------------------------------------------------------------

(function injectToastStyles() {
  if (document.getElementById('skill-toast-styles')) return;
  var s = document.createElement('style');
  s.id = 'skill-toast-styles';
  s.textContent =
    '#toasts{position:fixed;top:16px;right:16px;z-index:10000;display:flex;flex-direction:column;gap:8px;pointer-events:none;max-width:90vw;}' +
    '.toast{pointer-events:auto;background:var(--bg-card);border:1px solid var(--border);color:var(--text-primary);' +
      'padding:10px 14px;border-radius:8px;font-size:0.85rem;box-shadow:0 4px 12px rgba(0,0,0,0.15);' +
      'display:flex;align-items:flex-start;gap:8px;max-width:420px;animation:toast-in 0.18s ease-out;}' +
    '.toast.is-success{border-left:3px solid #16a34a;}' +
    '.toast.is-error{border-left:3px solid #dc2626;}' +
    '.toast.is-info{border-left:3px solid #2563eb;}' +
    '.toast-msg{flex:1;line-height:1.4;}' +
    '.toast-close{background:transparent;border:0;color:var(--text-secondary);cursor:pointer;font-size:1.1rem;padding:0 4px;line-height:1;}' +
    '@keyframes toast-in{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}' +
    '@keyframes toast-out{from{opacity:1}to{opacity:0;transform:translateY(-8px)}}';
  document.head.appendChild(s);
})();

// toast(message, level='info', opts={persist})
//   level: 'info' | 'success' | 'error'
//   opts.persist: when true, the toast sticks until dismissed. Defaults to
//                 true for 'error', false otherwise. Pass {persist:false}
//                 explicitly to override an error toast.
// Returns a function that dismisses the toast.
function toast(message, level, opts) {
  level = level || 'info';
  opts = opts || {};
  var container = document.getElementById('toasts');
  if (!container) return function () {};

  var el = document.createElement('div');
  el.className = 'toast is-' + level;
  el.setAttribute('role', level === 'error' ? 'alert' : 'status');
  el.innerHTML =
    '<span class="toast-msg"></span>' +
    '<button type="button" class="toast-close" aria-label="Dismiss">×</button>';
  el.querySelector('.toast-msg').textContent = message;

  function dismiss() {
    el.style.animation = 'toast-out 0.15s ease-in forwards';
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 160);
  }
  el.querySelector('.toast-close').onclick = dismiss;

  container.appendChild(el);

  var persist = opts.persist;
  if (persist === undefined) persist = (level === 'error');
  if (!persist) setTimeout(dismiss, 5000);
  return dismiss;
}

// ---------------------------------------------------------------------------
// Focus trap (modal accessibility)
// ---------------------------------------------------------------------------

(function injectFocusVisibleStyles() {
  if (document.getElementById('skill-focus-styles')) return;
  var s = document.createElement('style');
  s.id = 'skill-focus-styles';
  // Visible ring on keyboard focus only — never on click/tap. Targets common
  // interactive elements inside any modal-style dialog.
  s.textContent =
    '[role="dialog"] :focus-visible,.toast-close:focus-visible{' +
      'outline:2px solid #2563eb;outline-offset:2px;border-radius:4px;}';
  document.head.appendChild(s);
})();

var FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

// focusTrap(containerEl)
//   Caches document.activeElement, moves focus into containerEl, and cycles
//   Tab/Shift+Tab among focusable descendants. Returns a release function:
//   call it on close to detach the trap and restore focus to the originally
//   focused element.
function focusTrap(containerEl) {
  if (!containerEl) return function () {};
  var previouslyFocused = document.activeElement;

  function focusable() {
    return Array.prototype.filter.call(
      containerEl.querySelectorAll(FOCUSABLE_SELECTOR),
      function (el) { return el.offsetParent !== null && !el.disabled; }
    );
  }

  function onKeyDown(e) {
    if (e.key !== 'Tab') return;
    var els = focusable();
    if (!els.length) { e.preventDefault(); return; }
    var first = els[0];
    var last = els[els.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  // Move initial focus into the modal.
  setTimeout(function () {
    var first = focusable()[0];
    if (first) first.focus();
  }, 0);

  document.addEventListener('keydown', onKeyDown);

  return function release() {
    document.removeEventListener('keydown', onKeyDown);
    if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
      try { previouslyFocused.focus(); } catch (e) { /* element gone */ }
    }
  };
}

// ---------------------------------------------------------------------------
// Inline-expand uninstall (pill-as-action) — shared by home + detail
// ---------------------------------------------------------------------------

(function injectPillUninstallStyles() {
  if (document.getElementById('skill-pill-uninstall-styles')) return;
  var s = document.createElement('style');
  s.id = 'skill-pill-uninstall-styles';
  s.textContent =
    '.target-pill{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;' +
      'font-size:0.72rem;font-weight:600;font-family:inherit;cursor:pointer;border:1px solid transparent;' +
      'transition:all 140ms ease;background:var(--pill-bg,rgba(14,165,233,0.08));' +
      'color:var(--pill-fg,#0369a1);box-shadow:0 2px 4px rgba(0,0,0,0.03);margin-right:6px;}' +
    '.target-pill:hover{border-color:currentColor;}' +
    '.target-pill:focus-visible{outline:2px solid #2563eb;outline-offset:2px;}' +
    '.target-pill .pill-dot{display:inline-block;width:8px;height:8px;border-radius:50%;' +
      'background:var(--pill-dot,#0ea5e9);box-shadow:0 0 8px var(--pill-dot,#0ea5e9);}' +
    '.target-pill .pill-label{opacity:0.75;font-size:0.62rem;text-transform:uppercase;letter-spacing:0.06em;}' +
    '.target-pill .pill-name{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}' +
    '.target-pill .pill-x{opacity:0;transform:scale(0.7);transition:all 140ms ease;font-size:13px;' +
      'line-height:1;margin-left:2px;margin-right:-3px;font-family:inherit;}' +
    '.target-pill:hover .pill-x,.target-pill:focus-visible .pill-x{opacity:1;transform:scale(1);}' +
    '.target-pill[data-busy="true"]{opacity:0.6;cursor:wait;}' +
    '.target-pill[data-busy="true"] .pill-x{display:none;}' +
    '.inline-confirm-row{margin-top:12px;background:var(--bg-secondary);border:1px solid #b42318;' +
      'border-radius:8px;padding:12px 14px;animation:inline-confirm-in 180ms ease;}' +
    '.inline-confirm-row.hidden{display:none;}' +
    '.inline-confirm-row .icr-head{font-size:0.875rem;margin:0 0 6px;color:var(--text-primary);}' +
    '.inline-confirm-row .icr-target{color:#b42318;font-weight:600;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}' +
    '.inline-confirm-row .icr-body{font-size:0.78rem;color:var(--text-secondary);margin:0 0 10px;line-height:1.5;}' +
    '.inline-confirm-row .icr-body code{background:rgba(0,0,0,0.06);padding:1px 6px;border-radius:4px;' +
      'color:var(--text-primary);font-size:0.72rem;}' +
    '.dark .inline-confirm-row .icr-body code{background:rgba(255,255,255,0.08);}' +
    '.inline-confirm-row .icr-input{width:100%;background:var(--bg-primary);border:1px solid var(--border);' +
      'border-radius:6px;padding:7px 10px;color:var(--text-primary);' +
      'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:0.8rem;margin-bottom:10px;' +
      'box-sizing:border-box;outline:none;}' +
    '.inline-confirm-row .icr-input:focus{border-color:#2563eb;}' +
    '.inline-confirm-row .icr-actions{display:flex;gap:8px;justify-content:flex-end;}' +
    '.inline-confirm-row .icr-btn{padding:6px 12px;border-radius:6px;font-size:0.78rem;font-weight:600;' +
      'cursor:pointer;font-family:inherit;border:1px solid var(--border);background:transparent;' +
      'color:var(--text-primary);}' +
    '.inline-confirm-row .icr-btn:hover:not(:disabled){border-color:var(--text-secondary);}' +
    '.inline-confirm-row .icr-btn-danger{background:#b42318;border-color:#b42318;color:#fff;}' +
    '.inline-confirm-row .icr-btn-danger:disabled{opacity:0.45;cursor:not-allowed;}' +
    '.inline-confirm-row .icr-btn-danger:not(:disabled):hover{background:#931b14;}' +
    '@keyframes inline-confirm-in{from{opacity:0;transform:translateY(-4px);}' +
      'to{opacity:1;transform:translateY(0);}}';
  document.head.appendChild(s);
})();

function targetPillStyle(tName) {
  var c = (tName || '').toLowerCase();
  if (c.indexOf('prod') !== -1 || c.indexOf('f20') !== -1) {
    return { bg: 'rgba(16,185,129,0.08)', fg: '#059669', dot: '#10b981' };
  } else if (c.indexOf('stage') !== -1 || c.indexOf('f15') !== -1) {
    return { bg: 'rgba(139,92,246,0.08)', fg: '#6d28d9', dot: '#8b5cf6' };
  }
  return { bg: 'rgba(14,165,233,0.08)', fg: '#0369a1', dot: '#0ea5e9' };
}

function targetPillHtml(skillName, targetName) {
  var s = targetPillStyle(targetName);
  return (
    '<button type="button" class="target-pill" ' +
      'data-skill="' + escapeHtml(skillName) + '" ' +
      'data-target="' + escapeHtml(targetName) + '" ' +
      'aria-label="Uninstall ' + escapeHtml(skillName) + ' from ' + escapeHtml(targetName) + '" ' +
      'title="Click to uninstall from ' + escapeHtml(targetName) + '" ' +
      'style="--pill-bg:' + s.bg + ';--pill-fg:' + s.fg + ';--pill-dot:' + s.dot + ';">' +
      '<span class="pill-dot"></span>' +
      '<span class="pill-label">Target</span>' +
      '<span class="pill-name">' + escapeHtml(targetName) + '</span>' +
      '<span class="pill-x" aria-hidden="true">&times;</span>' +
    '</button>'
  );
}

// Open the inline confirm row in `slotEl`. Closes any other open rows in
// the document first (one at a time, page-wide). `onConfirm()` returns a
// promise resolving to true on success (we close) or false (we re-enable).
function openInlineUninstallConfirm(slotEl, skillName, targetName, onConfirm) {
  document.querySelectorAll('.inline-confirm-row.is-open').forEach(function (r) {
    r.classList.remove('is-open');
    r.classList.add('hidden');
    r.innerHTML = '';
  });
  if (!slotEl) return function () {};
  slotEl.classList.remove('hidden');
  slotEl.classList.add('is-open');
  slotEl.innerHTML =
    '<p class="icr-head">Remove <span class="icr-target">' + escapeHtml(skillName) + '</span> from ' +
      '<span class="icr-target">' + escapeHtml(targetName) + '</span>?</p>' +
    '<p class="icr-body">This cannot be undone. Type <code>' + escapeHtml(skillName) + '</code> to confirm.</p>' +
    '<input type="text" class="icr-input" autocomplete="off" spellcheck="false" placeholder="' +
      escapeHtml(skillName) + '">' +
    '<div class="icr-actions">' +
      '<button type="button" class="icr-btn" data-action="cancel">Cancel</button>' +
      '<button type="button" class="icr-btn icr-btn-danger" data-action="confirm" disabled>Remove</button>' +
    '</div>';

  var input = slotEl.querySelector('.icr-input');
  var confirmBtn = slotEl.querySelector('[data-action="confirm"]');
  var cancelBtn = slotEl.querySelector('[data-action="cancel"]');

  function close() {
    slotEl.classList.remove('is-open');
    slotEl.classList.add('hidden');
    slotEl.innerHTML = '';
  }

  input.addEventListener('input', function () {
    confirmBtn.disabled = input.value.trim() !== skillName;
  });
  slotEl.addEventListener('click', function (e) { e.stopPropagation(); });
  slotEl.addEventListener('keydown', function (e) {
    e.stopPropagation();
    if (e.key === 'Escape') { e.preventDefault(); close(); }
  });
  cancelBtn.addEventListener('click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    close();
  });
  confirmBtn.addEventListener('click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Removing…';
    cancelBtn.disabled = true;
    input.disabled = true;
    Promise.resolve(onConfirm()).then(function (ok) {
      if (ok) {
        close();
      } else {
        confirmBtn.textContent = 'Remove';
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
        input.disabled = false;
      }
    });
  });
  setTimeout(function () { input.focus(); }, 60);
  return close;
}

function performUninstall(skillName, targetName) {
  return fetch('/api/install/targets/' + encodeURIComponent(targetName) +
               '/skills/' + encodeURIComponent(skillName) + '/uninstall', {
    method: 'POST',
    credentials: 'include'
  })
  .then(function (res) { return res.json().then(function (d) { return { ok: res.ok, data: d }; }); })
  .then(function (r) {
    if (r.ok && r.data && r.data.status === 'ok') {
      toast('Uninstalled ' + skillName + ' from ' + targetName, 'success');
      return true;
    }
    toast(((r.data && r.data.error) || 'Uninstall failed'), 'error');
    return false;
  })
  .catch(function () {
    toast('Network error', 'error');
    return false;
  });
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', function () {
  applyThemeIcons();
  var themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

  // Back to Top functionality
  var backToTop = document.getElementById('back-to-top');
  if (backToTop) {
    backToTop.addEventListener('click', function() {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // Keyboard shortcut for Jump to top
  document.addEventListener('keydown', function(e) {
    if (isTypingTarget(e.target)) return;
    if (e.key.toLowerCase() === 'j') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });
});
