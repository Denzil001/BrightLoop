"""Local browser probes: escaped content, session cookies, logout and scheduler."""
from datetime import datetime, timedelta
from pathlib import Path
import re
import subprocess
import sys
import uuid
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright
from test_subscription_journeys import API, WEB, api, login


def run():
    suffix = uuid.uuid4().hex[:8]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        anonymous = browser.new_context()
        for path in ("/customers", "/staff", "/products", "/plans", "/taxes", "/discounts", "/quotation-templates",
                     "/subscriptions", "/invoices", "/payments", "/billing-runs", "/dashboard", "/reports/summary"):
            response = anonymous.request.get(f"{API}{path}")
            assert response.status == 401, f"Unauthenticated endpoint exposed: {path}"
        print("PASS: All 13 protected collection/dashboard routes deny anonymous access")
        context = browser.new_context()
        page = context.new_page()
        dialogs = []
        page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
        login(page, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        cookies = {cookie["name"]: cookie for cookie in context.cookies()}
        session_token = cookies["brightloop_session"]["value"]
        assert cookies["brightloop_session"]["httpOnly"] is True
        assert cookies["brightloop_session"]["sameSite"] == "Lax"
        assert "brightloop_session" not in page.evaluate("document.cookie")
        name = f"<img src=x onerror=alert(1)> security {suffix}"
        customer = api(context, "/customers", {"name": name, "email": f"security_{suffix}@brightloop.test"})
        page.goto(f"{WEB}/app/customers/{customer['id']}")
        expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
        assert page.locator('img[src="x"]').count() == 0
        assert not dialogs
        assert context.request.get(f"{API}/customers", params={"search": "' OR 1=1;--"}).json()["total"] == 0
        response = page.request.get(f"{WEB}/app")
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        print("PASS: HttpOnly session, escaped stored HTML, injection-shaped search and browser headers")
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        plan = api(context, "/plans", {"name": f"Scheduler browser {suffix}", "base_fee": "1000.00",
            "minimum_seats": 1, "extra_seat_unit_price": "0.00", "interval": "MONTHLY"})
        sub = api(context, "/subscriptions?issue=true", {"customer_id": customer["id"], "plan_id": plan["id"],
            "seat_quantity": 1, "start_date": today.isoformat(), "expiry_date": (today + timedelta(days=365)).isoformat()})
        api(context, f"/subscriptions/{sub['id']}/commands", {"action": "CONFIRM", "expected_version": sub["version"], "request_key": uuid.uuid4().hex})
        for _ in range(2):
            result = subprocess.run([sys.executable, "scripts/run_scheduler.py", "--once", "--subscription-id", sub["id"]],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=40)
            assert result.returncode == 0, "Scoped scheduler verification failed."
        listing = context.request.get(f"{API}/invoices?subscription_id={sub['id']}").json()
        assert listing["total"] == 1
        status = context.request.get(f"{API}/billing-runs").json()
        assert status["scheduler"]["state"] == "STOPPED"
        assert status["items"][0]["trigger"] == "SCHEDULED"
        assert status["items"][0]["summary"]["created"] == 0
        page.goto(f"{WEB}/app/billing-runs")
        expect(page.get_by_text("Worker is stopped or its heartbeat is stale;", exact=False)).to_be_visible()
        expect(page.get_by_role("cell", name="SCHEDULED", exact=True).first).to_be_visible()
        print("PASS: Actual scoped scheduler creates one invoice, replay creates none; runtime UI reports stopped worker")
        page.route("**/api/v1/auth/logout", lambda route: route.abort())
        page.get_by_role("button", name="Sign out", exact=True).click()
        expect(page.get_by_role("alert").filter(has_text="Sign out could not be confirmed")).to_have_text("Sign out could not be confirmed. Check your connection and try again.")
        assert context.request.get(f"{API}/auth/me").status == 200
        page.unroute("**/api/v1/auth/logout")
        page.get_by_role("button", name="Sign out", exact=True).click()
        page.wait_for_url(re.compile(r".*/login(?:\?.*)?$"))
        assert context.request.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {session_token}"}).status == 401
        print("PASS: Failed sign-out remains visible and authenticated; successful retry revokes the original session")
        browser.close()
    print("Hardening browser journeys: 4 passed, 0 skipped.")


if __name__ == "__main__":
    run()
