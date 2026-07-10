"""
Playwright e2e tests for the Skill Market web UI.
"""
import os
import re
import shutil
import time

import pytest
import requests


def _card_name(card):
    """Skill name from a card's href: '/skills/pdf/' -> 'pdf'."""
    href = card.get_attribute("href") or ""
    # href format: /skills/<name>/
    return href.rstrip("/").rsplit("/", 1)[-1]


def _open_detail(page, server_url, name):
    """Navigate to the detail page and wait for it to finish loading."""
    page.goto(f"{server_url}/skills/{name}/")
    page.locator("#content-section").wait_for(state="visible", timeout=5000)


# ---------------------------------------------------------------------------
# Version fixture — gives webapp-testing a second version so the
# version-popover keyboard-nav tests have >=2 items to move between.
# Mirrors skills/tests/test_views.py's _create_version_fixture/
# _remove_version_fixture pattern, adapted for the live subprocess server:
# the watcher's watchdog observer (300ms debounce) picks the new directory
# up on its own, so setup polls the API until it's visible instead of
# reaching into watcher internals directly.
# ---------------------------------------------------------------------------

SKILL_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../skill_repo"))
VERSION_FIXTURE_SKILL = "webapp-testing"
VERSION_FIXTURE_DIR = os.path.join(SKILL_REPO, VERSION_FIXTURE_SKILL, "20260401-e2e-version-test")


def _create_version_fixture():
    os.makedirs(VERSION_FIXTURE_DIR, exist_ok=True)
    with open(os.path.join(VERSION_FIXTURE_DIR, "SKILL.md"), "w") as f:
        f.write(
            "---\n"
            "name: webapp-testing\n"
            "description: \"Versioned webapp testing skill (e2e fixture)\"\n"
            "license: Complete terms in LICENSE.txt\n"
            "---\n\n"
            "Versioned content for webapp-testing (e2e fixture).\n"
        )


def _remove_version_fixture():
    if os.path.exists(VERSION_FIXTURE_DIR):
        shutil.rmtree(VERSION_FIXTURE_DIR, ignore_errors=True)


@pytest.fixture(scope="module")
def versioned_skill(server_url):
    """Ensure webapp-testing has >=2 versions, then clean up afterward.

    Defensive check first: if the skill already has versions for some other
    reason, don't clobber whatever created them — just use what's there.
    """
    existing = requests.get(f"{server_url}/api/skills/{VERSION_FIXTURE_SKILL}", timeout=5).json()
    if existing.get("versions"):
        yield existing
        return

    _remove_version_fixture()  # in case a prior interrupted run left it behind
    _create_version_fixture()

    data = None
    for _ in range(25):  # up to 10s: 300ms debounce + reparse + margin
        time.sleep(0.4)
        data = requests.get(f"{server_url}/api/skills/{VERSION_FIXTURE_SKILL}", timeout=5).json()
        if data.get("versions") and len(data["versions"]) >= 2:
            break
    else:
        _remove_version_fixture()
        pytest.fail("Watcher did not pick up the version fixture directory in time")

    yield data
    _remove_version_fixture()


# ---------------------------------------------------------------------------
# Home page — basic render
# ---------------------------------------------------------------------------

def test_home_loads_skill_cards(page, server_url):
    page.goto(server_url)
    cards = page.locator("#skill-grid .skill-card")
    assert cards.count() == 17, f"Expected 17 skill cards, got {cards.count()}"


def test_home_shows_stats(page, server_url):
    page.goto(server_url)
    assert page.locator("#footer-count").inner_text() == "17"
    assert "skills available" in page.inner_text("footer")


def test_home_has_search_input(page, server_url):
    page.goto(server_url)
    assert page.locator("#search-input").is_visible()


def test_home_has_category_select(page, server_url):
    page.goto(server_url)
    select = page.locator("#category-select")
    assert select.is_visible()
    assert select.locator("option").count() >= 2


def test_home_has_sort_select(page, server_url):
    page.goto(server_url)
    assert page.locator("#sort-select").is_visible()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_filters_cards(page, server_url):
    page.goto(server_url)
    page.fill("#search-input", "pdf")
    page.wait_for_timeout(300)

    visible = [
        page.locator("#skill-grid .skill-card").nth(i)
        for i in range(page.locator("#skill-grid .skill-card").count())
        if page.locator("#skill-grid .skill-card").nth(i).is_visible()
    ]
    assert len(visible) >= 1
    assert any(_card_name(c) == "pdf" for c in visible)


def test_search_shows_no_results_message(page, server_url):
    page.goto(server_url)
    page.fill("#search-input", "zzz_no_match_zzz")
    page.wait_for_timeout(300)
    assert page.locator("#no-results").is_visible()


def test_search_clear_restores_all_cards(page, server_url):
    page.goto(server_url)
    page.fill("#search-input", "pdf")
    page.wait_for_timeout(300)
    page.fill("#search-input", "")
    page.wait_for_timeout(300)

    visible_count = sum(
        1 for i in range(page.locator("#skill-grid .skill-card").count())
        if page.locator("#skill-grid .skill-card").nth(i).is_visible()
    )
    assert visible_count == 17


# ---------------------------------------------------------------------------
# Category filter
# ---------------------------------------------------------------------------

def test_category_filter_reduces_cards(page, server_url):
    page.goto(server_url)
    options = page.locator("#category-select option")
    non_all_value = None
    for i in range(options.count()):
        val = options.nth(i).get_attribute("value")
        if val:
            non_all_value = val
            break
    assert non_all_value, "Expected at least one non-'All' category option"
    page.select_option("#category-select", non_all_value)
    page.wait_for_timeout(300)

    visible_count = sum(
        1 for i in range(page.locator("#skill-grid .skill-card").count())
        if page.locator("#skill-grid .skill-card").nth(i).is_visible()
    )
    assert 0 < visible_count < 17


def test_category_select_all_restores_all_cards(page, server_url):
    page.goto(server_url)
    options = page.locator("#category-select option")
    non_all_value = None
    for i in range(options.count()):
        val = options.nth(i).get_attribute("value")
        if val:
            non_all_value = val
            break
    page.select_option("#category-select", non_all_value)
    page.wait_for_timeout(200)
    page.select_option("#category-select", "")
    page.wait_for_timeout(200)

    visible_count = sum(
        1 for i in range(page.locator("#skill-grid .skill-card").count())
        if page.locator("#skill-grid .skill-card").nth(i).is_visible()
    )
    assert visible_count == 17


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------

def test_sort_by_name(page, server_url):
    page.goto(server_url)
    page.select_option("#sort-select", "name")
    page.wait_for_timeout(200)

    names = [
        _card_name(page.locator("#skill-grid .skill-card").nth(i))
        for i in range(page.locator("#skill-grid .skill-card").count())
        if page.locator("#skill-grid .skill-card").nth(i).is_visible()
    ]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# Dark mode toggle
# ---------------------------------------------------------------------------

def test_dark_mode_toggle(page, server_url):
    page.goto(server_url)
    html = page.locator("html")
    initial_class = html.get_attribute("class") or ""

    page.locator("#theme-toggle").click()
    page.wait_for_timeout(200)

    toggled_class = html.get_attribute("class") or ""
    assert initial_class != toggled_class, "Theme class should change after toggle"


def test_dark_mode_persists_on_reload(page, server_url):
    page.goto(server_url)
    # Toggle once to dark
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(200)
    dark_class = page.locator("html").get_attribute("class") or ""

    page.reload()
    page.wait_for_timeout(200)
    reloaded_class = page.locator("html").get_attribute("class") or ""
    assert dark_class == reloaded_class, "Theme should persist across reload (localStorage)"


# ---------------------------------------------------------------------------
# Home page — quick-install click delegation (regression: commit 9a6b1cd
# fixed a wrapper div's stopPropagation() swallowing clicks before they
# reached the document-level delegated handler).
# ---------------------------------------------------------------------------

def test_featured_card_quick_install_opens_modal(page, server_url):
    page.goto(server_url)
    featured_card = page.locator(".skill-card.is-featured")
    assert featured_card.count() >= 1, (
        "Expected at least one featured card in the home grid (catalog needs >4 skills)"
    )

    install_btn = featured_card.locator(".quick-install-btn").first
    skill_name = install_btn.get_attribute("data-skill")
    install_btn.click()
    page.wait_for_timeout(200)

    modal = page.locator("#install-modal")
    assert "is-open" in (modal.get_attribute("class") or ""), (
        "Clicking a featured-card quick-install button should open the install modal"
    )
    assert page.locator("#install-modal-title").inner_text() == skill_name


def test_main_grid_quick_install_opens_modal(page, server_url):
    # Same assertion as the Featured-shelf test, but scoped to #skill-grid so
    # a future regression that reintroduces stopPropagation() on the wrapper
    # div fails here regardless of which shelf a reviewer happens to check.
    page.goto(server_url)
    install_btn = page.locator("#skill-grid .skill-card .quick-install-btn").first
    skill_name = install_btn.get_attribute("data-skill")
    install_btn.click()
    page.wait_for_timeout(200)

    modal = page.locator("#install-modal")
    assert "is-open" in (modal.get_attribute("class") or ""), (
        "Clicking a main-grid quick-install button should open the install modal"
    )
    assert page.locator("#install-modal-title").inner_text() == skill_name


# ---------------------------------------------------------------------------
# Skill detail page
# ---------------------------------------------------------------------------

def test_skill_card_navigates_to_detail(page, server_url):
    page.goto(server_url)
    page.locator("#skill-grid .skill-card[href$='/pdf/']").click()
    page.wait_for_url(re.compile(r"/skills/pdf/"))
    assert "/skills/pdf/" in page.url

    # Verify skill name is in the initial HTML response (server-rendered, not JS-injected)
    response = page.context.request.get(f"{server_url}/skills/pdf/")
    assert 'pdf' in response.text()


def test_detail_shows_license(page, server_url):
    _open_detail(page, server_url, "pdf")
    assert "Proprietary" in page.inner_text("body")


def test_detail_install_button_opens_modal(page, server_url):
    _open_detail(page, server_url, "pdf")
    page.locator("#install-button").click()
    page.wait_for_timeout(200)
    modal = page.locator("#install-modal")
    assert "is-open" in (modal.get_attribute("class") or "")


def test_detail_shows_file_list(page, server_url):
    _open_detail(page, server_url, "pdf")
    body = page.inner_text("body")
    assert "SKILL.md" in body or "LICENSE.txt" in body


def test_detail_download_zip_link_exists(page, server_url):
    _open_detail(page, server_url, "pdf")
    zip_links = page.locator("a[href*='/zip']")
    assert zip_links.count() >= 1


def test_detail_back_link_returns_home(page, server_url):
    _open_detail(page, server_url, "pdf")
    page.locator("a[href='/']").first.click()
    page.wait_for_url(re.compile(r"/$"))


# ---------------------------------------------------------------------------
# Skill detail page — version popover keyboard nav (regression: commit
# 9a6b1cd added ArrowUp/ArrowDown/Enter/Space/Escape handling to the
# previously mouse-only version popover).
# ---------------------------------------------------------------------------

def test_version_popover_arrow_and_enter_navigate(page, server_url, versioned_skill):
    _open_detail(page, server_url, VERSION_FIXTURE_SKILL)

    page.locator("#version-popover-trigger").click()
    page.locator("#version-popover-list").wait_for(state="visible", timeout=2000)

    items = page.locator(".version-popover-item")
    count = items.count()
    assert count >= 2, "Expected at least 2 versions in the popover"

    active_index = None
    for i in range(count):
        cls = items.nth(i).get_attribute("class") or ""
        if "is-active" in cls:
            active_index = i
            break
    assert active_index is not None, "Expected one item marked is-active on open"

    # Move focus to a *different* item. Arrow nav clamps at the ends rather
    # than wrapping, so pick the direction that's guaranteed to move.
    if active_index < count - 1:
        page.keyboard.press("ArrowDown")
        target_index = active_index + 1
    else:
        page.keyboard.press("ArrowUp")
        target_index = active_index - 1

    target_version = items.nth(target_index).get_attribute("data-version")
    page.keyboard.press("Enter")

    page.wait_for_url(re.compile(re.escape(f"/skills/{VERSION_FIXTURE_SKILL}/v/{target_version}/")))
    assert f"/skills/{VERSION_FIXTURE_SKILL}/v/{target_version}/" in page.url


def test_version_popover_escape_closes_without_navigating_home(page, server_url, versioned_skill):
    _open_detail(page, server_url, VERSION_FIXTURE_SKILL)
    detail_url = page.url

    page.locator("#version-popover-trigger").click()
    page.locator("#version-popover-list").wait_for(state="visible", timeout=2000)

    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    assert "hidden" in (page.locator("#version-popover-list").get_attribute("class") or ""), (
        "Escape should close the version popover"
    )
    assert page.url == detail_url, (
        "Escape on the version popover should not also trigger the page-level "
        "'Escape -> navigate home' shortcut"
    )
    assert page.url.rstrip("/") != server_url.rstrip("/")


# ---------------------------------------------------------------------------
# Command palette (Task 3: global Ctrl/Cmd+K search overlay)
# ---------------------------------------------------------------------------

def test_palette_opens_filters_and_navigates(page, server_url):
    page.goto(server_url)
    page.keyboard.press("Control+k")
    page.locator("#cmd-palette").wait_for(state="visible", timeout=2000)
    page.fill("#cmd-palette-input", "pdf")
    page.wait_for_timeout(200)
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"/skills/pdf/"))
    assert "/skills/pdf/" in page.url


def test_palette_escape_closes_and_restores_focus(page, server_url):
    page.goto(server_url)
    page.locator("#palette-trigger").click()
    page.locator("#cmd-palette").wait_for(state="visible", timeout=2000)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    assert "hidden" in (page.locator("#cmd-palette").get_attribute("class") or "")
    assert page.evaluate("document.activeElement.id") == "palette-trigger"


def test_palette_escape_on_detail_does_not_navigate_home(page, server_url):
    _open_detail(page, server_url, "pdf")
    page.keyboard.press("Control+k")
    page.locator("#cmd-palette").wait_for(state="visible", timeout=2000)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    assert "hidden" in (page.locator("#cmd-palette").get_attribute("class") or "")
    assert "/skills/pdf" in page.url
