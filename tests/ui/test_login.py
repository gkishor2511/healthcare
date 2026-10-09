import pytest
from src.pages.login_page import LoginPage

@pytest.mark.ui
@pytest.mark.smoke
def test_patient_can_login(driver, config):
    page = LoginPage(driver).open(config["base_url"])
    message = page.login("patient@example.com", "Password123")
    assert message == "Login successful"

@pytest.mark.ui
@pytest.mark.negative
def test_invalid_login_is_rejected(driver, config):
    page = LoginPage(driver).open(config["base_url"])
    message = page.login("patient@example.com", "WrongPassword")
    assert message == "Invalid credentials"
