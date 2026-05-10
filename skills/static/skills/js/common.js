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
