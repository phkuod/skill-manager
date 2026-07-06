"""
Playwright e2e tests for the Skill Market web UI.
"""
import re


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
