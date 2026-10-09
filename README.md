# Healthcare Python QA Automation

Industry-style QA automation portfolio project for a demo healthcare application.

## Stack

- Python 3.12
- Selenium
- Playwright
- Pytest
- Behave
- Requests
- PyMySQL
- Flask demo application
- Docker
- GitHub Actions

## Architecture

The framework separates page objects, API clients, database utilities, drivers, configuration, test data and tests.

## Quick Start

### 1. Create virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start demo healthcare application

```bash
python app/app.py
```

The application runs at:

`http://127.0.0.1:5000`

### 4. Run API tests

```bash
pytest -m api
```

### 5. Run UI tests

```bash
pytest -m ui
```

### 6. Run smoke tests

```bash
pytest -m smoke
```

### 7. Run BDD tests

```bash
behave
```

### 8. Generate HTML report

```bash
pytest --html=reports/report.html --self-contained-html
```

## Demo Credentials

Patient:
`patient@example.com`

Password:
`Password123`

Doctor:
`doctor@example.com`

Password:
`Password123`

Admin:
`admin@example.com`

Password:
`Password123`

These are demo-only credentials.

## Patient allergy list

Patients can review and update their allergy list after signing in. The API accepts
`PUT /api/patients/<patient_id>/allergies` with a JSON body such as
`{"allergies": ["penicillin", "latex"]}`. Only the authenticated patient can
update their own list; updates are validated, de-duplicated, and recorded in the
audit log. Prescription creation checks this list before saving a medication.

## GitHub

Suggested repository name:

`Healthcare-Python-QA-Automation`

## Future Enhancements

- Full patient/doctor UI
- Real MySQL integration in Docker
- Allure reporting
- Selenium Grid
- API schema validation
- OAuth/JWT authentication
- Performance testing with Locust
- Security testing
