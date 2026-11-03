"""Real browser payment acceptance, including a lost response and reload retry."""
from datetime import datetime, timedelta
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright
from pypdf import PdfReader
from test_subscription_journeys import API, WEB, api, login


def check_dialog_focus(page, dialog):
    for key in ("Tab", "Shift+Tab"):
        for _ in range(dialog.locator("a, input,select,textarea,button").count() + 2):
            page.keyboard.press(key)
            assert page.evaluate("!!document.activeElement.closest('dialog[open]')"), "Payment focus left its dialog"


def run():
    suffix = uuid.uuid4().hex[:8]
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    email, name = f"payment_{suffix}@brightloop.test", f"Payment customer {suffix}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        customer_context = browser.new_context()
        api(customer_context, "/auth/register", {"name": name, "email": email, "password": "Customer@Secure123"})
        customer = customer_context.new_page()
        login(customer, email, "Customer@Secure123", "/portal/profile")
        admin_context = browser.new_context()
        admin = admin_context.new_page()
        login(admin, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app/customers")
        customer_id = admin_context.request.get(f"{API}/customers?search={email}").json()["items"][0]["id"]
        tax = api(admin_context, "/taxes", {"name": f"Payment GST {suffix}", "classification": "GST", "rate": "18.00"})
        product = api(admin_context, "/products", {"name": f"Payment server {suffix}", "type": "SERVER", "sales_price": "200.00", "cost_price": "80.00", "tax_rule_ids": [tax["id"]]})
        variant = api(admin_context, f"/products/{product['id']}/variants", {"name": "High memory", "price_adjustment": "560.00"})
        plan = api(admin_context, "/plans", {"name": f"Payment plan {suffix}", "base_fee": "1000.00", "minimum_seats": 5, "extra_seat_unit_price": "100.00", "interval": "MONTHLY", "tax_rule_ids": [tax["id"]]})
        discount = api(admin_context, "/discounts", {"name": f"Payment discount {suffix}", "initial_revision": {"type": "PERCENT", "rate": "10.00", "scope": "SUBSCRIPTION", "valid_from": today.isoformat(), "valid_to": (today + timedelta(days=365)).isoformat(), "product_ids": []}})
        sub = api(admin_context, "/subscriptions?issue=true", {"customer_id": customer_id, "plan_id": plan["id"], "seat_quantity": 7, "start_date": today.isoformat(), "expiry_date": (today + timedelta(days=365)).isoformat(), "lines": [{"product_id": product["id"], "variant_id": variant["id"], "quantity": 2}], "discount_id": discount["id"]})
        for action in ("CONFIRM", "ACTIVATE"):
            sub = api(admin_context, f"/subscriptions/{sub['id']}/commands", {"action": action, "expected_version": sub["version"], "request_key": uuid.uuid4().hex})
        billing = api(admin_context, "/billing-runs", {"as_of_date": today.isoformat(), "subscription_id": sub["id"]})
        outcome = admin_context.request.get(f"{API}/billing-runs/{billing['id']}").json()["outcomes"][0]
        invoice_id = outcome["invoice_id"]
        invoice = admin_context.request.get(f"{API}/invoices/{invoice_id}").json()
        api(admin_context, f"/invoices/{invoice_id}/commands", {"action": "CONFIRM", "expected_version": invoice["version"], "request_key": uuid.uuid4().hex})
        staff_name, staff_email = f"Payment staff {suffix}", f"payment_staff_{suffix}@brightloop.test"
        api(admin_context, "/staff", {"name": staff_name, "email": staff_email, "initial_password": "Staff@Secure123"})
        staff_context = browser.new_context()
        staff = staff_context.new_page()
        login(staff, staff_email, "Staff@Secure123", "/app/customers")
        staff.goto(f"{WEB}/app/invoices/{invoice_id}")
        staff.get_by_role("button", name="Record payment", exact=True).click()
        dialog = staff.get_by_role("dialog", name="Record payment", exact=True)
        dialog.get_by_label("Amount received (₹)", exact=True).fill("1000.00")
        dialog.get_by_role("combobox", name="Payment method", exact=True).select_option("BANK_TRANSFER")
        dialog.get_by_label("Customer-visible payment note", exact=False).fill("First installment received")
        dialog.get_by_label("Reference (optional)", exact=True).fill(f"BANK-{suffix}")
        check_dialog_focus(staff, dialog)
        staff.once("dialog", lambda prompt: prompt.dismiss())
        dialog.get_by_role("button", name="Close", exact=True).click()
        expect(dialog).to_be_visible()
        expect(dialog.get_by_label("Amount received (₹)", exact=True)).to_have_value("1000.00")
        staff.once("dialog", lambda prompt: prompt.dismiss())
        staff.keyboard.press("Escape")
        expect(dialog).to_be_visible()
        staff.once("dialog", lambda prompt: prompt.accept())
        dialog.get_by_role("button", name="Close", exact=True).click()
        expect(dialog).not_to_be_visible()
        assert admin_context.request.get(f"{API}/payments?invoice_id={invoice_id}").json()["total"] == 0
        staff.get_by_role("button", name="Record payment", exact=True).click()
        expect(dialog.get_by_label("Amount received (₹)", exact=True)).to_have_value("1000.00")
        staff.on("dialog", lambda prompt: prompt.accept())
        print("PASS: Unsaved payment close/Escape protection preserves details and creates no payment")
        lost = {"once": False}

        def lose_first_response(route):
            if route.request.method != "POST":
                route.continue_()
                return
            if not lost["once"]:
                lost["once"] = True
                actual = route.fetch()
                assert actual.status == 201, actual.text()
                route.abort("failed")
            else:
                route.continue_()

        staff.route(f"**/api/v1/invoices/{invoice_id}/payments", lose_first_response)
        dialog.get_by_role("button", name="Save payment", exact=True).click()
        expect(dialog.get_by_role("alert")).to_be_visible()
        expect(dialog.get_by_label("Amount received (₹)", exact=True)).to_have_value("1000.00")
        recorded = admin_context.request.get(f"{API}/payments?invoice_id={invoice_id}").json()
        assert recorded["total"] == 1
        payment_id = recorded["items"][0]["id"]
        staff.reload()
        staff.get_by_role("button", name="Record payment", exact=True).click()
        dialog = staff.get_by_role("dialog", name="Record payment", exact=True)
        expect(dialog.get_by_label("Amount received (₹)", exact=True)).to_have_value("1000.00")
        expect(dialog.get_by_text("Your previous payment entry was restored. Review and retry to confirm its result.", exact=True)).to_be_visible()
        dialog.get_by_role("button", name="Save payment", exact=True).click()
        expect(staff.get_by_text("Payment recorded.", exact=True)).to_be_visible()
        after = admin_context.request.get(f"{API}/invoices/{invoice_id}").json()
        assert after["payment_count"] == 1 and after["remaining"] == "1888.64"
        print("PASS: Staff partial payment, lost response, restored form and same-key retry after reload create one payment")
        staff.goto(f"{WEB}/app/payments?invoice_id={invoice_id}")
        staff.get_by_role("combobox", name="Payment method filter", exact=True).select_option("BANK_TRANSFER")
        staff.get_by_role("button", name=payment_id, exact=True).click()
        drawer = staff.get_by_role("dialog", name="Payment details", exact=True)
        expect(drawer.get_by_text("First installment received", exact=True)).to_be_visible()
        expect(drawer.get_by_text("Recorded by / at", exact=True)).to_be_visible()
        check_dialog_focus(staff, drawer)
        staff.keyboard.press("Escape")
        customer.goto(f"{WEB}/portal/payments?invoice_id={invoice_id}")
        customer.get_by_role("button", name=payment_id, exact=True).click()
        drawer = customer.get_by_role("dialog", name="Payment details", exact=True)
        expect(drawer.get_by_text("First installment received", exact=True)).to_be_visible()
        expect(drawer.get_by_text("Recorded by / at", exact=True)).to_have_count(0)
        check_dialog_focus(customer, drawer)
        with customer.expect_download() as download_info:
            drawer.get_by_role("button", name="Download receipt", exact=True).click()
        output = Path("test-results")
        output.mkdir(exist_ok=True)
        download_info.value.save_as(str(output / "payment-browser.pdf"))
        receipt = "\n".join(page.extract_text() for page in PdfReader(output / "payment-browser.pdf").pages)
        assert "INR 1,000.00" in receipt and name in receipt
        customer.set_viewport_size({"width": 390, "height": 844})
        customer.screenshot(path=str(output / "payment-customer-mobile.png"), full_page=True)
        assert customer.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Payment drawer overflows mobile viewport"
        customer.keyboard.press("Escape")
        print("PASS: Staff/customer ledger filters, read-only drawer, customer-safe metadata, receipt download and mobile viewport")
        staff.goto(f"{WEB}/app/invoices/{invoice_id}")
        staff.get_by_role("button", name="Record payment", exact=True).click()
        dialog = staff.get_by_role("dialog", name="Record payment", exact=True)
        expect(dialog.get_by_label("Amount received (₹)", exact=True)).to_have_value("1888.64")
        dialog.get_by_role("combobox", name="Payment method", exact=True).select_option("UPI")
        dialog.get_by_label("Customer-visible payment note", exact=False).fill("Final installment received")
        dialog.get_by_label("Reference (optional)", exact=True).fill(f"UPI-{suffix}")
        dialog.get_by_role("button", name="Save payment", exact=True).click()
        expect(staff.get_by_text("Payment recorded.", exact=True)).to_be_visible()
        expect(staff.get_by_role("button", name="Record payment", exact=True)).to_have_count(0)
        settled = admin_context.request.get(f"{API}/invoices/{invoice_id}", max_retries=2).json()
        assert settled["state"] == "PAID" and settled["remaining"] == "0.00"
        assert settled["paid"] == "2888.64" and settled["payment_count"] == 2
        customer.goto(f"{WEB}/portal/invoices/{invoice_id}")
        expect(customer.get_by_role("button", name="Record payment", exact=True)).to_have_count(0)
        customer.goto(f"{WEB}/portal/payments?invoice_id={invoice_id}")
        customer.get_by_role("combobox", name="Payment method filter", exact=True).select_option("UPI")
        expect(customer.get_by_text("₹1888.64", exact=True)).to_be_visible()
        expect(customer.get_by_text("1 payments · Page 1", exact=True)).to_be_visible()
        print("PASS: Final payment reconciles invoice to PAID with two immutable payments and owner-scoped history")
        print("Payment browser journeys: 4 passed, 0 skipped.")
        browser.close()


if __name__ == "__main__":
    run()
