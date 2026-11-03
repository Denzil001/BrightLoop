"""End-to-End browser journey test suite using Playwright and local Mailpit."""

import json
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path

# Add project root and backend directory to path
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend"))

from playwright.sync_api import expect, sync_playwright

FRONTEND_URL = "http://localhost:3000"
MAILPIT_API_URL = "http://127.0.0.1:8025/api/v1/messages"


def is_mailpit_available() -> bool:
    try:
        req = urllib.request.Request(MAILPIT_API_URL)
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_mailpit_messages():
    req = urllib.request.Request(MAILPIT_API_URL)
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("messages", [])


def get_message_detail(message_id: str):
    url = f"http://127.0.0.1:8025/api/v1/message/{message_id}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_email_for_recipient(recipient: str, max_wait: float = 8.0):
    start = time.time()
    while time.time() - start < max_wait:
        messages = get_mailpit_messages()
        for msg in messages:
            to_list = [addr.get("Address") for addr in msg.get("To", [])]
            if recipient.lower() in [t.lower() for t in to_list if t]:
                # Fetch full message body
                return get_message_detail(msg["ID"])
        time.sleep(0.5)
    raise TimeoutError(f"No email arrived in Mailpit for {recipient} after {max_wait}s")


def run_e2e_tests():
    if not is_mailpit_available():
        raise RuntimeError("Mailpit is required: start the inbox before acceptance tests. No journeys were run.")
    print("Starting Playwright E2E Browser Journey Tests...")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context()
        page = context.new_page()

        # ----------------------------------------------------------------------
        # Test 1: Journey F01 - Customer Registration & Direct Portal Sign-in
        # ----------------------------------------------------------------------
        print("\n--- Test 1: F01 Customer Registration & Portal Flow ---")
        cust_uid = uuid.uuid4().hex[:8]
        cust_email = f"customer_{cust_uid}@brightloop.test"
        cust_name = f"Customer {cust_uid}"
        cust_password = "Valid@Password123"

        page.goto(f"{FRONTEND_URL}/register")
        page.wait_for_selector("h1:has-text('Create Customer Account')")

        page.fill("input#name", cust_name)
        page.fill("input#email", cust_email)
        page.fill("input#company", "Automated Testing Corp")
        page.fill("input#password", cust_password)
        page.fill("input#confirmPassword", cust_password)

        # Verify live password checklist criteria are all satisfied
        checklist_items = page.locator(".space-y-0\\.5 li")
        assert checklist_items.count() == 4
        for i in range(4):
            expect(checklist_items.nth(i)).to_contain_text("✓")

        # Submit registration
        page.click("button[type='submit']")

        # Should redirect to login page
        page.wait_for_url("**/login*")
        print("PASS: Registration form submitted and redirected to /login")

        # Fill login form
        page.fill("input#email", cust_email)
        page.fill("input#password", cust_password)
        page.click("button[type='submit']")

        # Should redirect to /portal/profile
        page.wait_for_url("**/portal")
        page.goto(f"{FRONTEND_URL}/portal/profile")
        page.wait_for_selector(f"span:has-text('{cust_email}')")
        print("PASS: Signed in as customer and landed on /portal/profile")

        # Update customer billing address
        page.fill("input[placeholder='Street address or P.O. Box']", "42 Test Drive")
        page.fill("input[value=''][type='text']", "Bengaluru")
        page.click("button:has-text('Save Profile & Address')")
        page.wait_for_selector("text='Your profile and billing details have been updated successfully.'")
        print("PASS: Customer updated own profile and address successfully")

        # Sign out
        page.click("button:has-text('Sign Out')")
        page.wait_for_url("**/login*")
        print("PASS: Customer sign out verified")

        # ----------------------------------------------------------------------
        # Test 2: Journey F01 - Unlinked Operational Customer Linking with Mailpit
        # ----------------------------------------------------------------------
        print("\n--- Test 2: F01 Unlinked Customer Verification & Linking ---")
        link_uid = uuid.uuid4().hex[:8]
        link_email = f"unlinked_{link_uid}@brightloop.test"
        link_name = f"Corporate Client {link_uid}"

        # Bootstrap an admin to create the operational customer
        from scripts.bootstrap_admin import bootstrap_admin
        bootstrap_admin("admin_bootstrap@brightloop.test", "Admin Master", "Admin@Secure123", force=True)

        # Obtain pre-auth CSRF
        csrf_req = urllib.request.Request("http://127.0.0.1:8000/api/v1/auth/csrf")
        with urllib.request.urlopen(csrf_req) as resp:
            preauth_data = json.loads(resp.read().decode("utf-8"))
            preauth_csrf = preauth_data["csrf_token"]
            preauth_cookie = resp.headers.get("Set-Cookie")

        # Login as admin to get session
        admin_login_req = urllib.request.Request(
            "http://127.0.0.1:8000/api/v1/auth/login",
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": preauth_csrf,
                "Cookie": preauth_cookie,
                "Origin": "http://localhost:3000",
            },
            data=json.dumps({
                "email": "admin_bootstrap@brightloop.test",
                "password": "Admin@Secure123",
            }).encode("utf-8"),
        )
        with urllib.request.urlopen(admin_login_req) as admin_resp:
            admin_cookie = admin_resp.headers.get("Set-Cookie")
            admin_data = json.loads(admin_resp.read().decode("utf-8"))
            csrf_token = admin_data["csrf_token"]

        # Admin creates operational customer (without portal login)
        cust_create_req = urllib.request.Request(
            "http://127.0.0.1:8000/api/v1/customers",
            headers={
                "Content-Type": "application/json",
                "Cookie": admin_cookie,
                "X-CSRF-Token": csrf_token,
                "Origin": "http://localhost:3000",
            },
            data=json.dumps({
                "name": link_name,
                "email": link_email,
                "company": "Link Target Corp",
            }).encode("utf-8"),
        )
        with urllib.request.urlopen(cust_create_req) as res:
            assert res.status == 201
            print(f"PASS: Created operational customer record for {link_email}")

        # Now client attempts to register on frontend with link_email
        page.goto(f"{FRONTEND_URL}/register")
        page.fill("input#name", link_name)
        page.fill("input#email", link_email)
        page.fill("input#password", "Linked@Password123")
        page.fill("input#confirmPassword", "Linked@Password123")
        page.click("button[type='submit']")

        # Must see the "Verification Required" notification
        page.wait_for_selector("h3:has-text('Verification Required')")
        print("PASS: Registration UI displayed 'Verification Required' challenge state")

        # Check Mailpit for the verification email
        email_msg = find_email_for_recipient(link_email)
        assert "Verify and connect your Brightloop account" in email_msg["Subject"]
        email_body = email_msg["Text"]

        # Extract token link from email
        match = re.search(r"http://localhost:3000/register\?token=([a-zA-Z0-9_\-]+)", email_body)
        assert match is not None, "Verification link not found in email"
        verify_url = match.group(0)
        print(f"PASS: Mailpit captured verification email with token link")

        # Navigate to verification URL
        page.goto(verify_url)
        page.wait_for_selector("text='Account Verified and Connected!'")
        print("PASS: Verification token consumed and confirmed in browser")

        # Sign in with newly verified account
        page.click("a:has-text('Sign in to your account')")
        page.wait_for_url("**/login*")
        page.fill("input#email", link_email)
        page.fill("input#password", "Linked@Password123")
        page.click("button[type='submit']")

        page.wait_for_url("**/portal")
        page.goto(f"{FRONTEND_URL}/portal/profile")
        page.wait_for_selector(f"span:has-text('{link_email}')")
        print("PASS: Verified linked customer signed in and accessed /portal/profile")

        page.click("button:has-text('Sign Out')")
        page.wait_for_url("**/login*")

        # ----------------------------------------------------------------------
        # Test 3: Journey F02 - Forgot Password & Reset via Mailpit
        # ----------------------------------------------------------------------
        print("\n--- Test 3: F02 Forgot Password & Reset Flow ---")
        page.goto(f"{FRONTEND_URL}/forgot-password")
        page.fill("input#email", cust_email)
        page.click("button:has-text('Send reset link')")

        page.wait_for_selector("h3:has-text('Check your email')")
        print("PASS: Forgot password generic confirmation displayed")

        # Retrieve reset email from Mailpit
        reset_msg = find_email_for_recipient(cust_email)
        assert "Reset your Brightloop password" in reset_msg["Subject"]
        reset_body = reset_msg["Text"]

        match_reset = re.search(r"http://localhost:3000/reset-password\?token=([a-zA-Z0-9_\-]+)", reset_body)
        assert match_reset is not None, "Reset link not found in email body"
        reset_url = match_reset.group(0)
        print("PASS: Mailpit captured password reset email with secure token")

        # Navigate to reset password page
        page.goto(reset_url)
        page.wait_for_selector("h1:has-text('Set New Password')")
        page.fill("input#newPassword", "New@Password456")
        page.fill("input#confirmPassword", "New@Password456")
        page.click("button:has-text('Reset password')")

        page.wait_for_selector("text='Password Reset Successful'")
        print("PASS: Password reset completed successfully")

        # Test login with old password fails
        page.goto(f"{FRONTEND_URL}/login")
        page.fill("input#email", cust_email)
        page.fill("input#password", cust_password)
        page.click("button[type='submit']")
        page.wait_for_selector("text='Invalid email or password.'")
        print("PASS: Old password rejected after reset")

        # Test login with new password succeeds
        page.fill("input#password", "New@Password456")
        page.click("button[type='submit']")
        page.wait_for_url("**/portal")
        page.goto(f"{FRONTEND_URL}/portal/profile")
        print("PASS: Signed in with new password successfully")

        page.click("button:has-text('Sign Out')")
        page.wait_for_url("**/login*")

        # ----------------------------------------------------------------------
        # Test 4: Journey F03 - Admin Staff Provisioning & Deactivation
        # ----------------------------------------------------------------------
        print("\n--- Test 4: F03 Admin Staff Provisioning & Deactivation ---")
        # Sign in as Admin
        page.goto(f"{FRONTEND_URL}/login")
        page.fill("input#email", "admin_bootstrap@brightloop.test")
        page.fill("input#password", "Admin@Secure123")
        page.click("button[type='submit']")

        page.wait_for_url("**/app")
        print("PASS: Admin signed in and landed on operational shell")

        # Go to Staff Management
        page.goto(f"{FRONTEND_URL}/app/staff")
        page.wait_for_selector("h1:has-text('Staff Management')")

        # Click Provision Staff
        staff_uid = uuid.uuid4().hex[:8]
        staff_email = f"staff_{staff_uid}@brightloop.test"
        staff_name = f"Staff Officer {staff_uid}"

        page.click("button:has-text('Provision Staff')")
        page.wait_for_selector("h2:has-text('Provision Staff Account')")

        page.fill("input[placeholder='Staff member full name']", staff_name)
        page.fill("input[placeholder='staff@brightloop.test']", staff_email)
        page.fill("form input[placeholder='•••••••••'] >> nth=0", "Staff@Pass1234")
        page.fill("form input[placeholder='•••••••••'] >> nth=1", "Staff@Pass1234")
        page.click("button:has-text('Provision Staff') >> nth=1")

        # Verify staff appears in list
        page.wait_for_selector(f"p:has-text('{staff_name}')")
        print(f"PASS: Staff {staff_name} provisioned and visible in table")

        # In separate browser context, test staff login
        staff_context = browser.new_context()
        staff_page = staff_context.new_page()
        staff_page.goto(f"{FRONTEND_URL}/login")
        staff_page.fill("input#email", staff_email)
        staff_page.fill("input#password", "Staff@Pass1234")
        staff_page.click("button[type='submit']")
        staff_page.wait_for_url("**/app")
        print("PASS: Staff member logged in and accessed operational customers")

        # Now in admin page: deactivate this staff member
        # Find the row with staff_email and click Deactivate
        row = page.locator("tr", has_text=staff_email)
        row.locator("button:has-text('Deactivate')").click()

        # Confirmation modal
        page.wait_for_selector("h3:has-text('Deactivate Staff Member?')")
        page.click("button:has-text('Confirm Deactivation')")

        # Verify status changes to Deactivated
        page.wait_for_selector("span:has-text('Deactivated')")
        print("PASS: Staff member deactivated by administrator")

        # In staff browser: try to navigate or perform action -> session revoked!
        staff_page.reload()
        staff_page.wait_for_url("**/login*")
        print("PASS: Deactivated staff member active session revoked immediately on refresh")

        # Try logging in as deactivated staff member
        staff_page.fill("input#email", staff_email)
        staff_page.fill("input#password", "Staff@Pass1234")
        staff_page.click("button[type='submit']")
        staff_page.wait_for_selector("text=Account has been deactivated")
        print("PASS: Deactivated staff member login blocked with actionable message")
        staff_context.close()

        # ----------------------------------------------------------------------
        # Test 5: Operational Customer Directory & Detail Editing
        # ----------------------------------------------------------------------
        print("\n--- Test 5: Operational Customer CRUD & Detail ---")
        page.goto(f"{FRONTEND_URL}/app/customers")
        page.wait_for_selector("h1:has-text('Customers')")

        # Create customer
        co_uid = uuid.uuid4().hex[:8]
        co_name = f"Enterprise Corp {co_uid}"
        co_email = f"billing_{co_uid}@enterprisecorp.test"

        page.click("button:has-text('New Customer')")
        page.wait_for_selector("h2:has-text('Create Operational Customer')")
        page.fill("input[placeholder='e.g. Acme Corporation or John Smith']", co_name)
        page.fill("input[placeholder='billing@company.com']", co_email)
        page.fill("input[placeholder='Acme Global Ltd']", "Enterprise Corp Group")
        page.fill("input[placeholder='Address Line 1']", "100 Industrial Estate")
        page.fill("input[placeholder='City']", "Chennai")
        page.click("button:has-text('Save Customer')")

        # Search for created customer
        page.wait_for_selector(f"a:has-text('{co_name}')")
        page.click(f"a:has-text('{co_name}')")

        # Customer Detail page
        page.wait_for_selector(f"h1:has-text('{co_name}')")
        page.wait_for_selector("text=Chennai")
        page.wait_for_selector("text=Unlinked")
        print("PASS: Customer detail opened, displayed Unlinked badge and location")

        # Edit Customer Details
        page.click("button:has-text('Edit Profile')")
        page.wait_for_selector("h3:has-text('Edit Customer Profile')")
        page.locator("label:has-text('City') + input").fill("Madras (Chennai)")
        page.click("button:has-text('Save Changes')")

        page.wait_for_selector("text=Madras (Chennai)")
        print("PASS: Customer details edited and persisted successfully")

        browser.close()

    print("\n=======================================================")
    print("Browser journeys: 5 passed, 0 failed, 0 skipped.")
    print("=======================================================")


from browser_test_errors import install_redaction
install_redaction()


if __name__ == "__main__":
    run_e2e_tests()
