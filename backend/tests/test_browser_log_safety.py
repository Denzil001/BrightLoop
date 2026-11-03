from scripts.browser_test_errors import redact


def test_browser_failure_redacts_credentials_and_keeps_diagnostic_context():
    message = '''GET /invoices/example (ECONNRESET)
    - cookie: brightloop_session=private-session; brightloop_csrf=private-csrf
    - authorization: Bearer private-bearer
    - x-csrf-token: private-header
    https://localhost/reset-password?token=private-reset&mode=reset
    {"password": "private-password", "new_password": "private-new"}
    postgresql+psycopg://app:private-database@localhost/database
    '''
    clean = redact(message)
    assert "private-" not in clean
    assert "ECONNRESET" in clean and "/invoices/example" in clean
    assert "[redacted]" in clean
