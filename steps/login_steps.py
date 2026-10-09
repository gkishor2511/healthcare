import requests
from behave import given, when, then

BASE_URL = "http://127.0.0.1:5000"

@given("the healthcare application is running")
def step_running(context):
    response = requests.get(BASE_URL + "/api/health", timeout=5)
    assert response.status_code == 200

@when("the patient logs in with valid credentials")
def step_login(context):
    context.response = requests.post(
        BASE_URL + "/api/login",
        json={"email": "patient@example.com", "password": "Password123"},
        timeout=5,
    )

@then("the login should be successful")
def step_success(context):
    assert context.response.status_code == 200
    assert context.response.json()["role"] == "patient"
