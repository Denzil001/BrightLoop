"""Live role dashboard/report reconciliation and filtered source navigation."""
from datetime import datetime, timedelta
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright
from test_subscription_journeys import API, WEB, api, login


def run():
    suffix = uuid.uuid4().hex[:8]
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    start = today - timedelta(days=40)
    customer_name, customer_email = f"Report customer {suffix}", f"report_{suffix}@brightloop.test"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        customer_context = browser.new_context()
        api(customer_context, "/auth/register", {"name": customer_name, "email": customer_email, "password": "Customer@Secure123"})
        customer = customer_context.new_page()
        login(customer, customer_email, "Customer@Secure123", "/portal")
        expect(customer.get_by_role("heading", name="My overview", exact=True)).to_be_visible()
        admin_context = browser.new_context()
        admin = admin_context.new_page()
        login(admin, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        expect(admin.get_by_role("heading", name="Operational overview", exact=True)).to_be_visible()
        customer_id = admin_context.request.get(f"{API}/customers?search={customer_email}").json()["items"][0]["id"]
        tax = api(admin_context, "/taxes", {"name": f"Report GST {suffix}", "classification": "GST", "rate": "18.00"})
        plan = api(admin_context, "/plans", {"name": f"Report plan {suffix}", "base_fee": "1000.00", "minimum_seats": 5,
                   "extra_seat_unit_price": "100.00", "interval": "MONTHLY", "tax_rule_ids": [tax["id"]]})
        draft = {"customer_id": customer_id, "plan_id": plan["id"], "seat_quantity": 7,
                 "start_date": start.isoformat(), "expiry_date": (today + timedelta(days=25)).isoformat()}
        sub = api(admin_context, "/subscriptions?issue=true", draft)
        for action in ("CONFIRM", "ACTIVATE"):
            sub = api(admin_context, f"/subscriptions/{sub['id']}/commands", {"action": action, "expected_version": sub["version"], "request_key": uuid.uuid4().hex})
        billing = api(admin_context, "/billing-runs", {"as_of_date": start.isoformat(), "subscription_id": sub["id"]})
        invoice_id = admin_context.request.get(f"{API}/billing-runs/{billing['id']}").json()["outcomes"][0]["invoice_id"]
        invoice = admin_context.request.get(f"{API}/invoices/{invoice_id}").json()
        api(admin_context, f"/invoices/{invoice_id}/commands", {"action": "CONFIRM", "expected_version": invoice["version"], "request_key": uuid.uuid4().hex})
        api(admin_context, f"/invoices/{invoice_id}/payments", {"amount": "1000.00", "method": "BANK_TRANSFER", "payment_date": today.isoformat(), "note": "Report source payment", "request_key": uuid.uuid4().hex})
        quote = api(admin_context, "/subscriptions?issue=true", {**draft, "start_date": today.isoformat()})
        staff_email = f"report_staff_{suffix}@brightloop.test"
        api(admin_context, "/staff", {"name": f"Report staff {suffix}", "email": staff_email, "initial_password": "Staff@Secure123"})
        admin.goto(f"{WEB}/app/reports")
        admin.get_by_label("Find customer", exact=True).fill(customer_name)
        admin.get_by_role("combobox", name="Report customer", exact=True).select_option(customer_id)
        admin.get_by_label("Find plan", exact=True).fill(plan["name"])
        admin.get_by_role("combobox", name="Report plan", exact=True).select_option(plan["id"])
        expect(admin.get_by_text("Received in selected range", exact=True).locator("..").get_by_text("₹1000.00", exact=True)).to_be_visible()
        expect(admin.get_by_text("Current outstanding", exact=True).locator("..").get_by_text("₹416.00", exact=True)).to_be_visible()
        expect(admin.get_by_text("Current overdue", exact=True).locator("..").get_by_text("₹416.00", exact=True)).to_be_visible()
        admin.get_by_role("button", name="Outstanding", exact=True).click()
        expect(admin.get_by_text("1 records · Page 1", exact=True)).to_be_visible()
        admin.get_by_role("link", name=invoice["number"], exact=True).click()
        expect(admin.get_by_role("heading", name=invoice["number"], exact=True)).to_be_visible()
        admin.go_back()
        expect(admin.get_by_role("combobox", name="Report customer", exact=True)).to_have_value(customer_id)
        admin.get_by_label("Payments from", exact=True).fill((today - timedelta(days=1)).isoformat())
        admin.get_by_label("Payments through", exact=True).fill((today - timedelta(days=1)).isoformat())
        expect(admin.get_by_text("Received in selected range", exact=True).locator("..").get_by_text("₹0.00", exact=True)).to_be_visible()
        expect(admin.get_by_text("Current outstanding", exact=True).locator("..").get_by_text("₹416.00", exact=True)).to_be_visible()
        metrics = admin_context.request.get(f"{API}/reports/summary?customer_id={customer_id}&plan_id={plan['id']}").json()
        print(f"PASS: Filtered report reconciles receipts/balances and source links; SQL summary {metrics['query_time_ms']} ms")
        staff_context = browser.new_context()
        staff = staff_context.new_page()
        login(staff, staff_email, "Staff@Secure123", "/app")
        expect(staff.get_by_text("Quotes awaiting confirmation", exact=True)).to_be_visible()
        expect(staff.get_by_role("link", name="Reports", exact=True)).to_have_count(0)
        expect(staff.get_by_text("Payments received in range", exact=True)).to_have_count(0)
        staff.get_by_role("link", name="Quotes awaiting confirmation", exact=False).click()
        expect(staff.get_by_role("combobox", name="Status", exact=True)).to_have_value("QUOTATION")
        staff.get_by_label("Search", exact=True).fill(quote["number"])
        expect(staff.get_by_role("link", name=quote["number"], exact=True)).to_be_visible()
        staff.goto(f"{WEB}/app/reports")
        expect(staff.get_by_role("heading", name="Access restricted", exact=True)).to_be_visible()
        assert staff_context.request.get(f"{API}/reports/summary").status == 403
        print("PASS: Staff dashboard exposes operational queues and filtered quote source, without finance report access")
        customer.goto(f"{WEB}/portal")
        expect(customer.get_by_text("Current outstanding", exact=True).locator("..").get_by_text("₹416.00", exact=True)).to_be_visible()
        customer.get_by_role("link", name="Current outstanding", exact=False).click()
        expect(customer.get_by_label("Outstanding only", exact=True)).to_be_checked()
        expect(customer.get_by_role("link", name=invoice["number"], exact=True)).to_be_visible()
        customer.goto(f"{WEB}/portal")
        customer.get_by_role("link", name="Active service today", exact=False).click()
        expect(customer.get_by_label("Active service today (excludes paused/ended)", exact=True)).to_be_checked()
        expect(customer.get_by_text("1 subscriptions · Page 1", exact=True)).to_be_visible()
        customer.goto(f"{WEB}/portal")
        expect(customer.get_by_text("Current outstanding", exact=True).locator("..").get_by_text("₹416.00", exact=True)).to_be_visible()
        customer.set_viewport_size({"width": 390, "height": 844})
        output = Path("test-results"); output.mkdir(exist_ok=True)
        customer.screenshot(path=str(output / "dashboard-customer-mobile.png"), full_page=True)
        assert customer.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Dashboard overflows mobile viewport"
        assert customer_context.request.get(f"{API}/reports/details").status == 403
        print("PASS: Customer overview owns its metrics and active/outstanding drill-downs; mobile viewport fits")
        print("Reporting browser journeys: 3 passed, 0 skipped.")
        browser.close()


if __name__ == "__main__":
    run()
