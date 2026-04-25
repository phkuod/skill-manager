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
// Copy to clipboard (delegated — works for elements added after load)
// ---------------------------------------------------------------------------

function copyButtonHandler(e) {
  var btn = e.target.closest('.copy-btn');
  if (!btn) return;

  var text;
  if (btn.dataset.copyTarget) {
    var el = document.getElementById(btn.dataset.copyTarget);
    text = el ? el.textContent : '';
  } else {
    text = btn.dataset.copy || '';
  }
  if (!text) return;

  navigator.clipboard.writeText(text).then(function () {
    var orig = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(function () { btn.textContent = orig; }, 2000);
  });
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
// Bootstrap
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', function () {
  applyThemeIcons();
  var themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);
  document.addEventListener('click', copyButtonHandler);
});
