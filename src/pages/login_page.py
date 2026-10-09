from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class LoginPage:
    EMAIL = (By.ID, "email")
    PASSWORD = (By.ID, "password")
    LOGIN = (By.CSS_SELECTOR, "button[type='submit']")
    MESSAGE = (By.ID, "message")

    def __init__(self, driver):
        self.driver = driver

    def open(self, url):
        self.driver.get(url)
        return self

    def login(self, email, password):
        wait = WebDriverWait(self.driver, 10)
        wait.until(EC.visibility_of_element_located(self.EMAIL)).send_keys(email)
        self.driver.find_element(*self.PASSWORD).send_keys(password)
        self.driver.find_element(*self.LOGIN).click()
        return wait.until(EC.visibility_of_element_located(self.MESSAGE)).text
