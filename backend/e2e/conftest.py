import os
import subprocess
import time

import pytest
import requests


CHROMIUM_EXEC = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
SKILL_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../skill_repo"))
PORT = 8799
BASE_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="session")
def server_url():
    env = os.environ.copy()
    env["SKILL_REPO_PATH"] = SKILL_REPO
    env["DJANGO_SETTINGS_MODULE"] = "skill_market.settings"

    venv_python = os.path.join(os.path.dirname(__file__), "../venv/bin/python")
    manage_py = os.path.join(os.path.dirname(__file__), "../manage.py")

    proc = subprocess.Popen(
        [venv_python, manage_py, "runserver", f"127.0.0.1:{PORT}", "--noreload"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait until server is up (max 10s)
    for _ in range(20):
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=1)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("Django dev server did not start in time")

    yield BASE_URL  # noqa: PT022

    proc.terminate()
    proc.wait()


@pytest.fixture(scope="session")
def browser_instance():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_EXEC,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        yield browser
        browser.close()


@pytest.fixture
def page(browser_instance):
    ctx = browser_instance.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()
