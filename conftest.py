import pytest
from src.drivers.driver_factory import create_driver
from src.utils.config_reader import load_config

@pytest.fixture(scope="session")
def config():
    return load_config()

@pytest.fixture
def driver(config):
    driver = create_driver(config["browser"], config["headless"])
    yield driver
    driver.quit()
