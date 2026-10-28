"""Desktop/mobile browser check for the focused dashboard.

Start Streamlit locally, then: python tests/dashboard/browser_qa.py
"""
from pathlib import Path
import json
import zipfile

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "figures" / "dashboard" / "redesign"
SHOTS.mkdir(parents=True, exist_ok=True)


def choose(page, control: str, value: str):
    page.get_by_role("combobox", name=control).click()
    page.get_by_role("option", name=value, exact=True).click()
    page.wait_for_timeout(250)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://localhost:8501", wait_until="domcontentloaded", timeout=60000)
    page.get_by_text("Thermal exposure simulator").wait_for(timeout=45000)
    page.get_by_text("15.05 °C·h", exact=False).wait_for(timeout=45000)
    page.locator(".js-plotly-plot").first.wait_for(timeout=45000)
    page.screenshot(path=str(SHOTS / "01_baseline_desktop.png"), full_page=True)

    choose(page, "Scenario", "Road Failure")
    page.get_by_text("Settings changed.", exact=False).wait_for()
    page.get_by_role("button", name="Run simulation").click()
    page.get_by_text("70.85 °C·h", exact=False).wait_for(timeout=45000)
    page.get_by_text("Download this run").wait_for()
    page.screenshot(path=str(SHOTS / "02_road_failure_desktop.png"), full_page=True)

    page.get_by_role("tab", name="Compare scenarios").click()
    page.get_by_text("Configured scenarios").wait_for()
    page.screenshot(path=str(SHOTS / "03_compare_desktop.png"), full_page=True)

    choose(page, "Temperature source", "Citrus proxy shape")
    choose(page, "Comparison reference", "4 °C")
    choose(page, "Channel", "Assumed product lag")
    choose(page, "Route", "Sea")
    page.get_by_role("tab", name="Simulation").click()
    page.get_by_text("Settings changed.", exact=False).wait_for()
    page.get_by_role("button", name="Run simulation").click()
    page.get_by_text("Download this run").wait_for(timeout=45000)
    page.get_by_text("Sea route", exact=False).wait_for(timeout=45000)
    page.screenshot(path=str(SHOTS / "04_sea_proxy_product_desktop.png"), full_page=True)

    with page.expect_download() as download_info:
        page.get_by_role("button", name="Download this run").click()
    download = download_info.value
    download_path = SHOTS / "selected_run.zip"
    download.save_as(str(download_path))
    with zipfile.ZipFile(download_path) as archive:
        bundle = json.loads(archive.read("complete_result.json"))
        assert bundle["selection"] == {"channel": "estimated_product", "reference_c": 4.0}
        assert bundle["selected_result"]["request"]["route"] == "sea"
        assert bundle["selected_result"]["request"]["mode"] == "proxy_citrus"

    mobile = browser.new_page(viewport={"width": 390, "height": 844})
    mobile.on("pageerror", lambda error: errors.append(str(error)))
    mobile.goto("http://localhost:8501", wait_until="domcontentloaded", timeout=60000)
    mobile.get_by_text("Thermal exposure simulator").wait_for(timeout=45000)
    mobile.locator(".js-plotly-plot").first.wait_for(timeout=45000)
    mobile.screenshot(path=str(SHOTS / "05_baseline_mobile.png"), full_page=True)
    width = mobile.evaluate("document.documentElement.scrollWidth")
    assert width <= 390, f"Mobile horizontal overflow: {width}px"
    assert not errors, errors
    print(json.dumps({"screenshots": 5, "download": download.suggested_filename,
                      "mobile_scroll_width": width, "page_errors": errors}))
    browser.close()
