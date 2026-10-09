import pytest
from playwright.sync_api import sync_playwright

@pytest.mark.ui
@pytest.mark.smoke
def test_login_with_playwright(config):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(config["base_url"])
        page.locator("#email").fill("patient@example.com")
        page.locator("#password").fill("Password123")
        page.locator("button[type='submit']").click()
        assert page.locator("#message").inner_text() == "Login successful"
        browser.close()
