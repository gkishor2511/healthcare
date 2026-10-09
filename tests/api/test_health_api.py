import pytest
from src.api.api_client import APIClient

@pytest.mark.api
@pytest.mark.smoke
def test_health_endpoint(config):
    response = APIClient(config["api_base_url"]).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"

@pytest.mark.api
def test_valid_login(config):
    client = APIClient(config["api_base_url"])
    response = client.post("/login", json={"email": "patient@example.com", "password": "Password123"})
    assert response.status_code == 200
    assert response.json()["role"] == "patient"

@pytest.mark.api
@pytest.mark.negative
def test_invalid_login(config):
    client = APIClient(config["api_base_url"])
    response = client.post("/login", json={"email": "patient@example.com", "password": "bad"})
    assert response.status_code == 401

@pytest.mark.api
def test_create_and_update_appointment(config):
    client = APIClient(config["api_base_url"])
    create = client.post("/appointments", json={"patient_id": 1, "doctor_id": 1, "date": "2026-10-10"})
    assert create.status_code == 201
    appt_id = create.json()["id"]
    update = client.put(f"/appointments/{appt_id}", json={"date": "2026-10-11"})
    assert update.status_code == 200
    assert update.json()["date"] == "2026-10-11"
    cancel = client.delete(f"/appointments/{appt_id}")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "CANCELLED"
