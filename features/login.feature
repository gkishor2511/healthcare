Feature: Patient login

  @smoke
  Scenario: Successful patient login
    Given the healthcare application is running
    When the patient logs in with valid credentials
    Then the login should be successful
