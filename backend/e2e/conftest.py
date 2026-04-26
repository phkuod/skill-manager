import os
import subprocess
import sys
import time

import pytest
import requests


CHROMIUM_EXEC = os.environ.get("CHROMIUM_EXEC")
SKILL_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../skill_repo"))
PORT = 8799
BASE_URL = f"http://127.0.0.1:{PORT}"


def _venv_python():
    """Project venv (matched to the current OS) first, else the active interpreter.

    Gated by sys.platform so a Windows-side venv exposed via a Linux bind mount
    isn't picked up inside a Linux container — the .exe exists as a file but
    isn't executable. sys.executable fallback covers CI / Docker / fresh
    checkouts that have no checked-in venv."""
    base = os.path.join(os.path.dirname(__file__), "../venv")
    candidate = (
        os.path.join(base, "Scripts", "python.exe")
        if sys.platform == "win32"
        else os.path.join(base, "bin", "python")
    )
    if os.path.isfile(candidate):
        return candidate
    return sys.executable


@pytest.fixture(scope="session")
def server_url():
    env = os.environ.copy()
    env["SKILL_REPO_PATH"] = SKILL_REPO
    env["DJANGO_SETTINGS_MODULE"] = "skill_market.settings"

    venv_python = _venv_python()
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
        launch_kwargs = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }
        if CHROMIUM_EXEC:
            launch_kwargs["executable_path"] = CHROMIUM_EXEC
        browser = pw.chromium.launch(**launch_kwargs)
        yield browser
        browser.close()


@pytest.fixture
def page(browser_instance):
    ctx = browser_instance.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()
