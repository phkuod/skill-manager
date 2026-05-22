/* Paste in DevTools console while viewing /installed/ with an expanded
   target that has at least one installed skill. Returns {passed,failed,results}. */
(async function () {
  const results = [];
  const T = (name, cond, detail) => results.push({ name, passed: !!cond, detail: detail || '' });

  // 1. Page has the bootstrap block
  T('bootstrap block exists', !!document.getElementById('installed-bootstrap'));

  // 2. At least one target section is rendered
  const sections = document.querySelectorAll('.installed-target');
  T('at least one target section', sections.length > 0);

  // 3. Expand the first section
  const first = sections[0];
  const header = first.querySelector('.installed-target-header');
  if (header.getAttribute('aria-expanded') !== 'true') header.click();
  await new Promise((r) => setTimeout(r, 1500));

  const body = first.querySelector('.installed-target-body');
  T('section body visible after click', !body.hidden);
  T('section body has rows or empty state',
    !!(body.querySelector('.installed-card') || body.querySelector('.installed-empty')));

  // 4. Click the first Uninstall button
  const btn = first.querySelector('.installed-uninstall-btn');
  if (btn) {
    btn.click();
    await new Promise((r) => setTimeout(r, 50));
    const modal = document.getElementById('uninstall-modal');
    T('modal opens on Uninstall click', !modal.hidden && modal.classList.contains('is-open'));

    const rect = modal.getBoundingClientRect();
    T('modal fills viewport', rect.width >= window.innerWidth * 0.99);

    const card = modal.querySelector('.uninstall-modal-card');
    const cardRect = card.getBoundingClientRect();
    T('modal card horizontally centered',
      Math.abs((cardRect.left + cardRect.right) / 2 - window.innerWidth / 2) < 20,
      `delta=${(cardRect.left + cardRect.right) / 2 - window.innerWidth / 2}`);

    const confirm = document.getElementById('uninstall-modal-confirm');
    T('Remove button initially disabled', confirm.disabled === true);
    T('Remove button has aria-disabled', confirm.getAttribute('aria-disabled') === 'true');

    const input = document.getElementById('uninstall-modal-confirm-input');
    input.value = 'WRONG-NAME';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    T('Remove stays disabled with wrong text', confirm.disabled === true);

    const skillName = btn.dataset.name;
    input.value = skillName;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    T('Remove enables when name matches', confirm.disabled === false);

    // close without submitting
    document.getElementById('uninstall-modal-close').click();
    await new Promise((r) => setTimeout(r, 200));
    T('modal closes on x', modal.hidden === true);
  } else {
    T('Uninstall button available (skipped - no rows installed)', true, 'no installed skills to test');
  }

  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;
  console.table(results);
  return { passed, failed, results };
})();
