# Healthcare QA Automation - Test Cases

| ID | Module | Scenario | Type | Priority |
|---|---|---|---|---|
| TC001 | Login | Valid patient login | Functional | High |
| TC002 | Login | Invalid password | Negative | High |
| TC003 | Login | Unknown email | Negative | High |
| TC004 | Login | Empty credentials | Boundary | Medium |
| TC005 | Doctor | Get doctor list | API | High |
| TC006 | Doctor | Verify available doctor | Functional | High |
| TC007 | Patient | Get patient list | API | High |
| TC008 | Patient | Create patient | API | High |
| TC009 | Patient | Missing patient name | Negative | High |
| TC010 | Appointment | Create appointment | Functional | Critical |
| TC011 | Appointment | Missing doctor | Negative | High |
| TC012 | Appointment | Missing date | Negative | High |
| TC013 | Appointment | Reschedule appointment | Functional | High |
| TC014 | Appointment | Cancel appointment | Functional | Critical |
| TC015 | Appointment | Cancel unknown appointment | Negative | Medium |
| TC016 | UI | Login page loads | Smoke | Critical |
| TC017 | UI | Successful login message | Smoke | Critical |
| TC018 | UI | Failed login message | Negative | High |
| TC019 | API | Health endpoint | Smoke | Critical |
| TC020 | API | Login status code | API | Critical |
| TC021 | API | Login response role | API | High |
| TC022 | API | Invalid login status | Negative | High |
| TC023 | API | Create appointment response | API | Critical |
| TC024 | API | Update appointment | API | High |
| TC025 | API | Delete appointment | API | Critical |
| TC026 | Security | Invalid credentials rejected | Security | Critical |
| TC027 | Security | Missing required fields rejected | Security | High |
| TC028 | Integration | UI login backed by API | Integration | High |
| TC029 | Regression | Patient login regression | Regression | High |
| TC030 | Regression | Appointment lifecycle | Regression | Critical |
