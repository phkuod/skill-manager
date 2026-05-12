// installed-page-ui-audit.js
//
// Manual UI/UX smoke test for the /installed/ page (target list, section
// expand/collapse, catalog vs. orphan rows, uninstall modal, focus trap,
// theme contrast).
//
// Catches regressions like:
//   - Tailwind utility classes used on the page that aren't in the
//     JIT-purged vendor bundle (silent layout breakage).
//   - Section body still visible when aria-expanded is false.
//   - "Installed" nav link missing aria-current="page".
//   - Bootstrap JSON unparseable or empty.
//   - Cards stretched edge-to-edge because of missing grid template.
//   - Uninstall modal positioning broken in either theme.
//   - Type-to-confirm not gating the Remove button.
//   - Focus trap not cycling Tab/Shift+Tab.
//   - Empty-state copy missing when a target has zero installed skills.
//   - Result text colors invisible on the other theme.
//
// HOW TO USE
//   1. Make sure you're signed in (CURRENT_USER_NAME cookie set). If not,
//      the audit will set it to "audit-user" for you and reload-tests will
//      still pass — only the template-rendered "Signed in as" line uses
//      the cookie value, and we don't assert on that.
//   2. Open /installed/ in a browser (any backend, any deploy).
//   3. Wait for the page to finish loading (header nav visible).
//   4. Open DevTools console, paste the contents of this file, hit Enter.
//   5. Read the returned object. .failed === 0 means audit passes.
//
// The audit MOCKS window.fetch for the list and uninstall endpoints so it
// is hermetic and safe to run on any environment — nothing actually scans
// targets or deletes skills.
//
// If you change the installed.html markup, installed.js, or app.css
// uninstall/installed-* rules, run this audit before merging.

(async () => {
  const fails = []; const passes = [];
  const assert = (cond, msg) => { (cond ? passes : fails).push(msg); };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const luma = c => {
    const m = c.match(/\d+/g);
    return m ? (0.299 * +m[0] + 0.587 * +m[1] + 0.114 * +m[2]) : 0;
  };

  if (!/\/installed\/?$/.test(location.pathname)) {
    return { passed: 0, failed: 1, failures: ['Run this on /installed/'] };
  }

  // -------------------------------------------------- 0. Hermetic fetch mock
  const FAKE_LIST = {
    target: 'F12',
    base: '/audit/audit-user/skills',
    catalog: [
      {
        name: 'coding-guide',
        icon: '📘',
        description: 'How to write clean code',
        path: '/audit/audit-user/skills/coding-guide',
        mtime: '2026-05-09T12:43:11Z',
        fileCount: 14,
      },
      {
        name: 'webapp-testing',
        icon: '🧪',
        description: 'End-to-end test patterns',
        path: '/audit/audit-user/skills/webapp-testing',
        mtime: '2026-04-22T08:00:00Z',
        fileCount: 7,
      },
    ],
    orphan: [
      {
        name: 'legacy-thing',
        path: '/audit/audit-user/skills/legacy-thing',
        mtime: '2025-08-01T09:11:00Z',
      },
    ],
  };

  let mockUninstallShouldFail = false;
  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    const u = typeof url === 'string' ? url : url.toString();
    const listMatch = u.match(/\/api\/install\/targets\/([^/]+)\/skills$/);
    if (listMatch && (!init || (init.method || 'GET') === 'GET')) {
      const t = decodeURIComponent(listMatch[1]);
      const body = { ...FAKE_LIST, target: t, base: '/audit/audit-user/skills' };
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(body),
      });
    }
    const unMatch = u.match(/\/api\/install\/targets\/([^/]+)\/skills\/([^/]+)\/uninstall$/);
    if (unMatch && init && init.method === 'POST') {
      if (mockUninstallShouldFail) {
        return Promise.resolve({
          ok: false, status: 500,
          json: () => Promise.resolve({ error: 'mock failure for audit' }),
        });
      }
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({
          status: 'ok',
          target: decodeURIComponent(unMatch[1]),
          path: '/audit/audit-user/skills/' + decodeURIComponent(unMatch[2]),
        }),
      });
    }
    return origFetch(url, init);
  };

  document.cookie = 'CURRENT_USER_NAME=audit-user; path=/';

  // -------------------------------------------------- 1. Bootstrap + sections
  const bootstrapEl = document.getElementById('installed-bootstrap');
  assert(!!bootstrapEl, 'installed-bootstrap script tag exists');
  let bootstrapData = [];
  if (bootstrapEl) {
    try { bootstrapData = JSON.parse(bootstrapEl.textContent || '[]'); }
    catch (_e) { /* leave empty */ }
    assert(Array.isArray(bootstrapData), 'bootstrap JSON parses to an array');
  }

  const sections = document.querySelectorAll('.installed-target');
  assert(sections.length >= 1, 'at least one .installed-target section rendered (got ' + sections.length + ')');
  assert(sections.length === bootstrapData.length,
    'section count matches bootstrap targets (' + sections.length + ' vs ' + bootstrapData.length + ')');

  sections.forEach((s, i) => {
    const name = s.dataset.target;
    assert(!!name, 'section[' + i + '] has data-target');
    const header = s.querySelector('.installed-target-header');
    const body = s.querySelector('.installed-target-body');
    assert(!!header, 'section[' + i + '] has .installed-target-header');
    assert(!!body, 'section[' + i + '] has .installed-target-body');
    assert(header && header.getAttribute('aria-expanded') === 'false',
      'section[' + i + '] starts with aria-expanded="false"');
    assert(body && body.hidden, 'section[' + i + '] body starts hidden');
  });

  // -------------------------------------------------- 2. Header nav active state
  const navInstalled = document.getElementById('nav-installed');
  assert(!!navInstalled, 'header has #nav-installed link');
  if (navInstalled) {
    assert(navInstalled.getAttribute('aria-current') === 'page',
      'nav-installed marked aria-current="page" by installed.js');
    assert(navInstalled.getAttribute('href') === '/installed/',
      'nav-installed href is /installed/');
  }

  // -------------------------------------------------- 3. CSS audit (utility classes)
  const ruleExists = cls => Array.from(document.styleSheets).some(ss => {
    try {
      return Array.from(ss.cssRules).some(r => r.selectorText &&
        r.selectorText.split(',').some(s => s.trim() === '.' + cls));
    } catch (_e) { return false; }
  });
  const utilsToCheck = ['text-sm', 'font-medium', 'px-3', 'py-2', 'rounded-lg', 'border', 'max-w-5xl'];
  for (const cls of utilsToCheck) {
    assert(ruleExists(cls),
      'Tailwind utility "' + cls + '" present in vendor bundle (used by /installed/)');
  }

  // -------------------------------------------------- 4. CSS variables in both themes
  const requiredVars = ['--bg-primary', '--bg-secondary', '--text-primary', '--text-secondary', '--border'];
  const wasDark = document.documentElement.classList.contains('dark');
  for (const mode of ['light', 'dark']) {
    document.documentElement.classList.toggle('dark', mode === 'dark');
    for (const v of requiredVars) {
      const val = getComputedStyle(document.documentElement).getPropertyValue(v).trim();
      assert(!!val, 'CSS var ' + v + ' resolves in ' + mode + ' theme');
    }
  }
  document.documentElement.classList.toggle('dark', wasDark);

  // -------------------------------------------------- 5. Expand first section
  const first = sections[0];
  const firstHeader = first.querySelector('.installed-target-header');
  const firstBody = first.querySelector('.installed-target-body');
  const firstCaret = first.querySelector('.installed-target-caret');
  const firstRefresh = first.querySelector('.installed-target-refresh');
  assert(!!firstCaret, 'caret element exists');
  assert(!!firstRefresh, 'refresh element exists');
  assert(firstRefresh && firstRefresh.hidden, 'refresh hidden while collapsed');

  firstHeader.click();
  await sleep(0);
  assert(firstBody.innerHTML.includes('installed-skeleton'),
    'skeleton placeholders shown during load');
  await sleep(200);
  assert(firstHeader.getAttribute('aria-expanded') === 'true',
    'aria-expanded toggles to "true" after click');
  assert(!firstBody.hidden, 'body becomes visible after click');
  assert(firstCaret.textContent === '▾', 'caret rotates to "down" when expanded');
  assert(!firstRefresh.hidden, 'refresh icon visible when expanded');

  // -------------------------------------------------- 6. Rendered rows
  const catalogCards = firstBody.querySelectorAll('.installed-card:not(.installed-card-orphan)');
  const orphanCards = firstBody.querySelectorAll('.installed-card.installed-card-orphan');
  assert(catalogCards.length === FAKE_LIST.catalog.length,
    'catalog cards: expected ' + FAKE_LIST.catalog.length + ', got ' + catalogCards.length);
  assert(orphanCards.length === FAKE_LIST.orphan.length,
    'orphan cards: expected ' + FAKE_LIST.orphan.length + ', got ' + orphanCards.length);

  const groupTitles = firstBody.querySelectorAll('.installed-group-title');
  assert(groupTitles.length === 2,
    'expanded section has two group titles (In catalog + Not in catalog)');
  assert(/In catalog \(2\)/.test(groupTitles[0].textContent),
    'first group title has correct count');
  assert(/Not in catalog \(1\)/.test(groupTitles[1].textContent),
    'second group title has correct count');

  const cg = catalogCards[0];
  assert(cg.dataset.name === 'coding-guide', 'first catalog card data-name');
  assert(cg.querySelector('.installed-card-icon').textContent.length > 0,
    'first catalog card shows an icon');
  assert(/How to write clean code/.test(cg.querySelector('.installed-card-desc').textContent),
    'first catalog card shows description');
  assert(/14 files/.test(cg.querySelector('.installed-card-meta').textContent),
    'first catalog card shows file count');
  assert(/coding-guide/.test(cg.querySelector('.installed-card-path').textContent),
    'first catalog card shows install path');
  const uninstallBtn = cg.querySelector('.installed-uninstall-btn');
  assert(!!uninstallBtn, 'first catalog card has Uninstall button');
  assert(uninstallBtn && uninstallBtn.dataset.name === 'coding-guide',
    'Uninstall button data-name matches');

  const orph = orphanCards[0];
  assert(orph.dataset.name === 'legacy-thing', 'orphan card data-name');
  assert(/Not in catalog/.test(orph.querySelector('.installed-card-badge').textContent),
    'orphan card shows "Not in catalog" badge');
  const orphIcon = orph.querySelector('.installed-card-icon').textContent.trim();
  assert(orphIcon.length > 0, 'orphan card has a fallback icon');

  // -------------------------------------------------- 7. Card layout sanity
  const cardCs = getComputedStyle(cg);
  assert(cardCs.display === 'grid', 'card uses CSS grid (got ' + cardCs.display + ')');
  assert(cardCs.gridTemplateColumns.split(' ').length === 3,
    'card has 3 grid columns (icon | body | button), got "' + cardCs.gridTemplateColumns + '"');
  const cardRect = cg.getBoundingClientRect();
  assert(cardRect.height > 60, 'card has reasonable height (got ' + Math.round(cardRect.height) + 'px)');

  const uninstallCs = getComputedStyle(uninstallBtn);
  assert(/180.*35.*24|b42318/i.test(uninstallCs.borderTopColor + ' ' + uninstallCs.borderColor),
    'Uninstall button border is red-toned (got ' + uninstallCs.borderTopColor + ')');

  // -------------------------------------------------- 8. Refresh re-fetches
  let fetchCallCount = 0;
  const installedFetchProxy = window.fetch;
  window.fetch = (url, init) => {
    if (typeof url === 'string' && /\/api\/install\/targets\/[^/]+\/skills$/.test(url)) {
      fetchCallCount += 1;
    }
    return installedFetchProxy(url, init);
  };
  firstRefresh.click();
  await sleep(200);
  assert(fetchCallCount >= 1, 'refresh button triggered a re-fetch (' + fetchCallCount + ' call(s))');

  // -------------------------------------------------- 9. Collapse + cache
  firstHeader.click();
  await sleep(80);
  assert(firstHeader.getAttribute('aria-expanded') === 'false', 'section collapses on second click');
  assert(firstBody.hidden, 'body becomes hidden again');
  assert(firstCaret.textContent === '▸', 'caret rotates back to "right"');
  fetchCallCount = 0;
  firstHeader.click();
  await sleep(120);
  assert(fetchCallCount === 0, 'expanding again uses cache (no new fetch)');

  // -------------------------------------------------- 10. Uninstall modal opens
  const modal = document.getElementById('uninstall-modal');
  assert(!!modal, 'uninstall-modal exists in DOM');
  assert(modal.hidden, 'modal starts hidden');

  const refreshedUninstallBtn = first.querySelector('.installed-card[data-name="coding-guide"] .installed-uninstall-btn');
  refreshedUninstallBtn.click();
  await sleep(80);
  assert(!modal.hidden, 'modal becomes visible after Uninstall click');
  assert(modal.classList.contains('is-open'), 'modal has .is-open class');

  // -------------------------------------------------- 11. Modal contents + positioning
  assert(document.getElementById('uninstall-modal-target').textContent === 'F12',
    'modal shows target name');
  assert(/coding-guide/.test(document.getElementById('uninstall-modal-path').textContent),
    'modal shows skill path');
  assert(document.getElementById('uninstall-modal-files').textContent === '14',
    'modal shows file count');
  assert(document.getElementById('uninstall-modal-skill-name').textContent === 'coding-guide',
    'modal shows skill name in confirm hint');
  assert(/Remove "coding-guide"/.test(document.getElementById('uninstall-modal-title').textContent),
    'modal title includes skill name');

  const modalCs = getComputedStyle(modal);
  assert(modalCs.position === 'fixed', 'modal overlay is position:fixed');
  const mb = modal.getBoundingClientRect();
  const visualW = document.documentElement.clientWidth;
  assert(Math.abs(mb.width - visualW) <= 2, 'modal overlay fills viewport width');
  const card = modal.querySelector('.uninstall-modal-card');
  const cb = card.getBoundingClientRect();
  assert(cb.width >= 350 && cb.width <= 540,
    'modal card width in 350-540px range (got ' + Math.round(cb.width) + ')');
  const cardCx = cb.left + cb.width / 2;
  assert(Math.abs(cardCx - visualW / 2) < 20,
    'modal card horizontally centered (off by ' + Math.round(cardCx - visualW / 2) + 'px)');

  // -------------------------------------------------- 12. Type-to-confirm gating
  const confirmBtn = document.getElementById('uninstall-modal-confirm');
  const confirmInput = document.getElementById('uninstall-modal-confirm-input');
  assert(confirmBtn.disabled === true, 'Remove button disabled on open');
  assert(confirmBtn.getAttribute('aria-disabled') === 'true', 'Remove button has aria-disabled="true"');

  confirmInput.value = 'WRONG-NAME';
  confirmInput.dispatchEvent(new Event('input', { bubbles: true }));
  assert(confirmBtn.disabled === true, 'Remove stays disabled with wrong text');
  assert(confirmBtn.getAttribute('aria-disabled') === 'true', 'aria-disabled stays "true"');

  confirmInput.value = 'coding-guide';
  confirmInput.dispatchEvent(new Event('input', { bubbles: true }));
  assert(confirmBtn.disabled === false, 'Remove enables when name matches');
  assert(confirmBtn.getAttribute('aria-disabled') === 'false', 'aria-disabled becomes "false"');

  confirmInput.value = '  coding-guide  ';
  confirmInput.dispatchEvent(new Event('input', { bubbles: true }));
  assert(confirmBtn.disabled === false, 'Remove stays enabled after surrounding whitespace (trimmed)');

  // -------------------------------------------------- 13. Focus trap
  const focusables = Array.from(card.querySelectorAll(
    'button:not([disabled]),a[href],input:not([disabled])'
  )).filter(el => el.offsetParent !== null);
  assert(focusables.length >= 2, 'modal has at least 2 focusable elements');
  if (focusables.length >= 2) {
    const f0 = focusables[0];
    const fN = focusables[focusables.length - 1];
    fN.focus();
    document.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Tab', bubbles: true, cancelable: true,
    }));
    await sleep(40);
    assert(document.activeElement === f0, 'Tab from last focusable cycles to first');
    f0.focus();
    document.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Tab', shiftKey: true, bubbles: true, cancelable: true,
    }));
    await sleep(40);
    assert(document.activeElement === fN, 'Shift+Tab from first focusable cycles to last');
  }

  // -------------------------------------------------- 14. Theme contrast
  const wasDark14 = document.documentElement.classList.contains('dark');
  for (const mode of ['light', 'dark']) {
    document.documentElement.classList.toggle('dark', mode === 'dark');
    await sleep(20);
    const titleEl = document.getElementById('uninstall-modal-title');
    const fg = luma(getComputedStyle(titleEl).color);
    const bg = luma(getComputedStyle(card).backgroundColor);
    assert(Math.abs(fg - bg) >= 50,
      mode + ' theme: title fg/bg luminosity diff >= 50 (got ' + Math.round(Math.abs(fg - bg)) + ')');
    const danger = document.getElementById('uninstall-modal-confirm');
    const dangerFg = luma(getComputedStyle(danger).color);
    const dangerBg = luma(getComputedStyle(danger).backgroundColor);
    assert(Math.abs(dangerFg - dangerBg) >= 80,
      mode + ' theme: danger button fg/bg luminosity diff >= 80 (got ' + Math.round(Math.abs(dangerFg - dangerBg)) + ')');
  }
  document.documentElement.classList.toggle('dark', wasDark14);

  // -------------------------------------------------- 15. Successful uninstall flow
  confirmInput.value = 'coding-guide';
  confirmInput.dispatchEvent(new Event('input', { bubbles: true }));
  mockUninstallShouldFail = false;
  confirmBtn.click();
  for (let i = 0; i < 30; i++) {
    await sleep(80);
    if (modal.hidden) break;
  }
  assert(modal.hidden, 'modal closes after successful uninstall');
  const removedCard = first.querySelector('.installed-card[data-name="coding-guide"]');
  assert(!removedCard, 'removed skill row no longer in DOM');
  const titleAfter = first.querySelector('.installed-group-title');
  assert(/In catalog \(1\)/.test(titleAfter.textContent),
    'catalog count decremented (got "' + titleAfter.textContent + '")');
  const successToast = document.querySelector('#toasts .toast.is-success');
  assert(!!successToast, 'success toast appears after uninstall');
  if (successToast) {
    assert(/coding-guide/.test(successToast.textContent),
      'toast names the removed skill');
  }

  // -------------------------------------------------- 16. Failure path keeps modal open
  const second = first.querySelector('.installed-card[data-name="webapp-testing"] .installed-uninstall-btn');
  assert(!!second, 'second catalog card still present (webapp-testing)');
  if (second) {
    second.click();
    await sleep(60);
    assert(!modal.hidden, 'modal reopens for second skill');
    const inp = document.getElementById('uninstall-modal-confirm-input');
    inp.value = 'webapp-testing';
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    mockUninstallShouldFail = true;
    document.getElementById('uninstall-modal-confirm').click();
    for (let i = 0; i < 30; i++) {
      await sleep(80);
      const r = document.getElementById('uninstall-modal-result');
      if (r && !r.hidden) break;
    }
    const resEl = document.getElementById('uninstall-modal-result');
    assert(!modal.hidden, 'modal stays open on uninstall failure');
    assert(resEl && !resEl.hidden, 'result block becomes visible on failure');
    assert(resEl.classList.contains('is-err'), 'result block has .is-err class');
    assert(/mock failure for audit/.test(resEl.textContent),
      'error message rendered from server response');
    assert(document.getElementById('uninstall-modal-confirm').textContent === 'Remove',
      'Remove button text restored after failure');
    const stillThere = first.querySelector('.installed-card[data-name="webapp-testing"]');
    assert(!!stillThere, 'failed-uninstall row still present in DOM');
  }

  // -------------------------------------------------- 17. Escape closes modal
  document.dispatchEvent(new KeyboardEvent('keydown', {
    key: 'Escape', bubbles: true, cancelable: true,
  }));
  await sleep(80);
  assert(modal.hidden, 'Escape closes the modal');

  // -------------------------------------------------- 18. Overlay click closes
  const reopenBtn = first.querySelector('.installed-card[data-name="webapp-testing"] .installed-uninstall-btn');
  if (reopenBtn) {
    reopenBtn.click();
    await sleep(60);
    assert(!modal.hidden, 'modal reopens for backdrop test');
    const overlayClick = new MouseEvent('click', { bubbles: true, cancelable: true });
    Object.defineProperty(overlayClick, 'target', { value: modal });
    modal.dispatchEvent(overlayClick);
    await sleep(80);
    assert(modal.hidden, 'clicking outside the card closes the modal');
  }

  // -------------------------------------------------- 19. Empty state
  const second2 = sections[1];
  if (second2) {
    const innerProxy = window.fetch;
    window.fetch = (url, init) => {
      if (typeof url === 'string' && /\/api\/install\/targets\/[^/]+\/skills$/.test(url)) {
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({
            target: second2.dataset.target,
            base: '/audit/audit-user/skills',
            catalog: [], orphan: [],
          }),
        });
      }
      return innerProxy(url, init);
    };
    second2.querySelector('.installed-target-header').click();
    await sleep(200);
    const body2 = second2.querySelector('.installed-target-body');
    assert(!!body2.querySelector('.installed-empty'),
      'empty state ".installed-empty" rendered when target has no skills');
    window.fetch = innerProxy;
  }

  // -------------------------------------------------- 20. Cleanup
  window.fetch = origFetch;

  const summary = { passed: passes.length, failed: fails.length };
  if (fails.length) summary.failures = fails;
  console.table([
    { label: 'passed', value: summary.passed },
    { label: 'failed', value: summary.failed },
  ]);
  if (summary.failed) console.warn('FAILURES:', summary.failures);
  return summary;
})();
