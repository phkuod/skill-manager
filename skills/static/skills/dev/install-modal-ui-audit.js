// install-modal-ui-audit.js
//
// Manual UI/UX smoke test for the one-click install modal on /skill.html.
// Catches regressions like:
//   - Tailwind utility classes that aren't in the JIT-purged vendor bundle
//   - Modal positioned off-screen because of missing .fixed/.inset-0
//   - Modal card stretched edge-to-edge because of missing .max-w-md
//   - Hard-coded result text colors invisible on the other theme
//   - Buttons enabled/disabled state out of sync with cookie presence
//   - Result message not rendered after install POST
//
// HOW TO USE
//   1. Open /skill.html#<some-skill> in a browser (any backend, any deploy).
//   2. Make sure the page finished loading (skill name visible, etc.).
//   3. Open DevTools console, paste the contents of this file, hit Enter.
//   4. Read the returned object. .failed === 0 means audit passes.
//
// The audit MOCKS window.fetch for the install POST so it's hermetic and
// safe to run on any environment — nothing actually copies skills.
//
// If you change the modal markup or add classes, run this audit before
// merging. It's also embedded in the test plan for the install feature.

(async () => {
  const fails = []; const passes = [];
  const assert = (cond, msg) => { (cond ? passes : fails).push(msg); };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const luma = c => { const m = c.match(/\d+/g); return m ? (0.299*+m[0]+0.587*+m[1]+0.114*+m[2]) : 0; };

  // Wait until renderSkill has wired up the install button (it depends on
  // /api/skills/<name> + /files fetches which can take a moment in a
  // cross-origin or slow setup). Poll up to 5s.
  for (let i = 0; i < 100; i++) {
    const btn = document.getElementById('install-button');
    if (btn && typeof btn.onclick === 'function') break;
    await sleep(50);
  }

  // Mock /install POST — keeps audit hermetic.
  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    if (typeof url === 'string' && /\/install$/.test(url) && init && init.method === 'POST') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        status: 'ok', target: JSON.parse(init.body).target,
        path: '/audit/jdoe/skills/audit-skill'
      })});
    }
    return origFetch(url, init);
  };

  document.cookie = 'CURRENT_USER_NAME=jdoe; path=/';

  // ---------------------------------------------------------- 1. CSS audit
  const ruleExists = cls => Array.from(document.styleSheets).some(ss => {
    try { return Array.from(ss.cssRules).some(r => r.selectorText &&
      r.selectorText.split(',').some(s => s.trim() === '.' + cls)); }
    catch (e) { return false; }
  });
  const utilsOnModal = new Set();
  document.querySelectorAll('#install-modal, #install-modal *').forEach(el => {
    el.classList.forEach(c => { if (!/^install-modal/.test(c)) utilsOnModal.add(c); });
  });
  for (const cls of utilsOnModal) {
    assert(ruleExists(cls), 'Tailwind utility ".' + cls + '" exists in vendor bundle');
  }

  const requiredVars = ['--bg-card', '--text-primary', '--text-secondary',
    '--border', '--accent', '--result-ok-bg', '--result-ok-text',
    '--result-err-bg', '--result-err-text'];
  for (const mode of ['light', 'dark']) {
    document.documentElement.classList.toggle('dark', mode === 'dark');
    for (const v of requiredVars) {
      const val = getComputedStyle(document.documentElement).getPropertyValue(v).trim();
      assert(!!val, 'CSS var ' + v + ' resolves in ' + mode + ' theme');
    }
  }
  document.documentElement.classList.remove('dark');

  // ---------------------------------------------------------- 2. Initial state
  const installBtn = document.getElementById('install-button');
  assert(!!installBtn, 'install button exists in sidebar');
  assert(getComputedStyle(installBtn).display !== 'none', 'install button visible');
  assert(typeof installBtn.onclick === 'function', 'install button onclick wired');
  const initialModal = document.getElementById('install-modal');
  assert(initialModal.classList.contains('hidden'), 'modal starts hidden');
  assert(getComputedStyle(initialModal).display === 'none',
    'hidden modal is display:none (otherwise overlay intercepts every click on the page — Back link, etc.)');
  // Sanity: ensure the back link in the header IS clickable while modal is hidden.
  const backLink = document.querySelector('header a[href$="index.html"]');
  if (backLink) {
    const br = backLink.getBoundingClientRect();
    const elAt = document.elementFromPoint(br.left + br.width / 2, br.top + br.height / 2);
    assert(backLink.contains(elAt),
      'header Back link is reachable when modal hidden (got ' + (elAt ? elAt.tagName : 'null') + ' at click point)');
  }

  // ---------------------------------------------------------- 3. Modal opens
  installBtn.click();
  await sleep(400);
  const modal = document.getElementById('install-modal');
  const card = modal.querySelector(':scope > div');
  const cs = getComputedStyle(modal);
  const cardCs = getComputedStyle(card);
  const mb = modal.getBoundingClientRect();
  const cb = card.getBoundingClientRect();
  const visualW = document.documentElement.clientWidth; // excludes scrollbar
  assert(!modal.classList.contains('hidden'), 'modal becomes visible after click');
  assert(cs.position === 'fixed', 'modal overlay is position:fixed (was ' + cs.position + ')');
  assert(mb.top === 0 && mb.left === 0, 'modal overlay anchors at top-left of viewport');
  assert(Math.abs(mb.width - visualW) <= 2,
    'overlay spans viewport width (got ' + Math.round(mb.width) + ' vs ' + visualW + ')');
  assert(cb.width <= 500 && cb.width >= 350,
    'modal card has bounded width 350-500px (got ' + Math.round(cb.width) + ')');
  assert(parseInt(cardCs.padding) >= 16,
    'modal card has ≥16px padding (got ' + cardCs.padding + ')');
  const cardCx = cb.left + cb.width / 2;
  assert(Math.abs(cardCx - visualW / 2) < 20,
    'modal card horizontally centered (off by ' + Math.round(cardCx - visualW / 2) + 'px)');
  const cardCy = cb.top + cb.height / 2;
  assert(Math.abs(cardCy - window.innerHeight / 2) < 20,
    'modal card vertically centered (off by ' + Math.round(cardCy - window.innerHeight / 2) + 'px)');

  // ---------------------------------------------------------- 4. Modal contents
  const title = document.getElementById('install-modal-title').textContent;
  assert(title && title.length > 0, 'title rendered (got: ' + JSON.stringify(title) + ')');
  assert(document.getElementById('install-modal-user').textContent === 'jdoe',
    'user shows cookie value');
  assert(document.getElementById('install-modal-no-cookie').classList.contains('hidden'),
    'no-cookie warning hidden when cookie present');
  assert(!!document.querySelector('.install-modal-kicker'),
    'kicker label "INSTALL" is present');
  assert(!!document.getElementById('install-modal-close'),
    'close (×) button present in upper-right');

  await sleep(250);
  const targetBtns = document.querySelectorAll('.install-target-btn');
  assert(targetBtns.length >= 1,
    'at least one target row rendered (got ' + targetBtns.length + ')');
  assert(Array.from(targetBtns).every(b => /jdoe/.test(b.querySelector('.install-target-path').textContent)),
    'every target row path shows expanded user_name');
  assert(Array.from(targetBtns).every(b => !b.disabled),
    'target rows enabled when cookie present');
  assert(Array.from(targetBtns).every(b =>
    b.querySelector('.install-target-name') &&
    b.querySelector('.install-target-path') &&
    b.querySelector('.install-target-go')),
    'each target row has name + path + go-arrow children');

  if (targetBtns.length >= 2) {
    const gap = targetBtns[1].getBoundingClientRect().top - targetBtns[0].getBoundingClientRect().bottom;
    assert(gap >= 4 && gap <= 16,
      'target rows have visible gap 4-16px (got ' + Math.round(gap) + ')');
  }

  const cancelBtn = document.getElementById('install-modal-cancel');
  const cancelRight = cancelBtn.getBoundingClientRect().right;
  const cardRight = cb.right - parseInt(cardCs.paddingRight);
  assert(Math.abs(cancelRight - cardRight) < 4,
    'cancel button right-aligned within card (off by ' + Math.round(cancelRight - cardRight) + 'px)');

  // ---------------------------------------------------------- 5. No-cookie state
  document.cookie = 'CURRENT_USER_NAME=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/';
  cancelBtn.click(); await sleep(200);
  installBtn.click(); await sleep(300);
  assert(!document.getElementById('install-modal-no-cookie').classList.contains('hidden'),
    'no-cookie warning visible without cookie');
  await sleep(200);
  const btnsNoCookie = document.querySelectorAll('.install-target-btn');
  assert(btnsNoCookie.length > 0 && Array.from(btnsNoCookie).every(b => b.disabled),
    'install buttons disabled when cookie missing');
  document.getElementById('install-modal-cancel').click();
  await sleep(200);
  document.cookie = 'CURRENT_USER_NAME=jdoe; path=/';

  // ---------------------------------------------------------- 6. Install flow
  installBtn.click(); await sleep(400);
  const f12 = Array.from(document.querySelectorAll('.install-target-btn'))
    .find(b => /F12/.test(b.textContent));
  assert(!!f12, 'F12 install button present');
  if (f12) {
    f12.click();
    let resultEl;
    for (let i = 0; i < 30; i++) {
      await sleep(150);
      resultEl = document.getElementById('install-modal-result');
      if (!resultEl.classList.contains('hidden')) break;
    }
    assert(!resultEl.classList.contains('hidden'), 'result element shown after install POST');
    assert(/Installed to F12/.test(resultEl.textContent),
      'success result text rendered (got: ' + resultEl.textContent.slice(0, 60) + ')');
    assert(document.getElementById('install-modal-cancel').textContent === 'Close',
      'cancel button morphs to "Close" after install');
  }

  // ------------------------------------------------------------ 6.5 Focus trap
  // Modal is still open with cancel button at "Close". Verify the focus
  // trap from common.js cycles Tab/Shift+Tab among focusable descendants.
  const installModal = document.getElementById('install-modal');
  const focusables = Array.from(installModal.querySelectorAll(
    'button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'
  )).filter(el => el.offsetParent !== null);
  assert(focusables.length >= 2,
    'modal has ≥2 focusable elements (' + focusables.length + ' found)');
  if (focusables.length >= 2) {
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    last.focus();
    document.dispatchEvent(new KeyboardEvent('keydown',
      { key: 'Tab', bubbles: true, cancelable: true }));
    await sleep(40);
    assert(document.activeElement === first,
      'Tab from last focusable cycles back to first');
    first.focus();
    document.dispatchEvent(new KeyboardEvent('keydown',
      { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }));
    await sleep(40);
    assert(document.activeElement === last,
      'Shift+Tab from first focusable cycles to last');
  }

  // ---------------------------------------------------------- 7. Theme contrast
  for (const mode of ['light', 'dark']) {
    document.documentElement.classList.toggle('dark', mode === 'dark');
    const el = document.getElementById('install-modal-result');
    const fg = luma(getComputedStyle(el).color);
    const bg = luma(getComputedStyle(el).backgroundColor);
    assert(Math.abs(fg - bg) >= 50,
      mode + ' theme: result fg/bg luminosity diff ≥50 (got ' + Math.round(Math.abs(fg - bg)) + ')');
  }
  document.documentElement.classList.remove('dark');

  // -------------------------------------------------------- 8. Toast feedback
  // Success toast must appear after install and survive modal close.
  const toastSuccess = document.querySelector('#toasts .toast.is-success');
  assert(!!toastSuccess, 'success toast appears after install');
  if (toastSuccess) {
    assert(/Installed to F12/.test(toastSuccess.textContent),
      'toast carries the install success message');
  }
  document.getElementById('install-modal-cancel').click();
  await sleep(250);
  const toastAfterClose = document.querySelector('#toasts .toast.is-success');
  assert(!!toastAfterClose, 'success toast persists after modal close');

  window.fetch = origFetch;

  const summary = { passed: passes.length, failed: fails.length };
  if (fails.length) summary.failures = fails;
  return summary;
})();
