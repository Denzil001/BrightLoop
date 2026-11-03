"""Live Phase 5 browser acceptance; all created identities use synthetic .test data."""
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
import json
import re
import time
import uuid
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright
from pypdf import PdfReader
from test_subscription_journeys import API, WEB, api, login


def run():
    suffix = uuid.uuid4().hex[:8]
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    email, name = f"billing_{suffix}@brightloop.test", f"Billing customer {suffix}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        customer_context = browser.new_context()
        assert customer_context.request.get("http://127.0.0.1:8025/api/v1/messages").ok, "Mailpit is required; no email checks are skipped."
        api(customer_context, "/auth/register", {"name": name, "email": email, "password": "Customer@Secure123"})
        customer = customer_context.new_page()
        login(customer, email, "Customer@Secure123", "/portal/profile")
        admin_context = browser.new_context()
        admin = admin_context.new_page()
        admin.on("dialog", lambda dialog: dialog.accept())
        login(admin, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app/customers")
        customer_id = admin_context.request.get(f"{API}/customers?search={email}").json()["items"][0]["id"]
        tax = api(admin_context, "/taxes", {"name": f"Billing GST {suffix}", "classification": "GST", "rate": "18.00"})
        product = api(admin_context, "/products", {"name": f"Billing server {suffix}", "type": "SERVER",
            "sales_price": "200.00", "cost_price": "80.00", "tax_rule_ids": [tax["id"]]})
        variant = api(admin_context, f"/products/{product['id']}/variants", {"name": "High memory", "price_adjustment": "560.00"})
        plan = api(admin_context, "/plans", {"name": f"Billing monthly {suffix}", "base_fee": "1000.00", "minimum_seats": 5,
            "extra_seat_unit_price": "100.00", "interval": "MONTHLY", "tax_rule_ids": [tax["id"]]})
        discount = api(admin_context, "/discounts", {"name": f"Billing discount {suffix}", "initial_revision": {
            "type": "PERCENT", "rate": "10.00", "scope": "SUBSCRIPTION", "valid_from": today.isoformat(),
            "valid_to": (today + timedelta(days=365)).isoformat(), "product_ids": []}})
        subscription = api(admin_context, "/subscriptions?issue=true", {"customer_id": customer_id, "plan_id": plan["id"],
            "seat_quantity": 7, "start_date": today.isoformat(), "expiry_date": (today + timedelta(days=365)).isoformat(),
            "lines": [{"product_id": product["id"], "variant_id": variant["id"], "quantity": 2}], "discount_id": discount["id"]})
        for action in ("CONFIRM", "ACTIVATE"):
            subscription = api(admin_context, f"/subscriptions/{subscription['id']}/commands", {"action": action,
                "expected_version": subscription["version"], "request_key": uuid.uuid4().hex})
        scope_url = f"{WEB}/app/billing-runs?subscription_id={subscription['id']}"
        admin.goto(scope_url)
        admin.get_by_role("button", name="Run billing now", exact=True).click()
        expect(admin.get_by_text("Billing run finished.", exact=True)).to_be_visible(timeout=30000)
        admin.get_by_role("link", name="View invoice", exact=True).click()
        admin.wait_for_url(re.compile(r"/app/invoices/[0-9a-f-]+$"))
        invoice_id = admin.url.rsplit("/", 1)[1]
        expect(admin.get_by_text("Draft preview. This invoice has not been issued and is not payable.", exact=True)).to_be_visible()
        expect(admin.get_by_text("₹2888.64", exact=True)).to_be_visible()
        assert customer_context.request.get(f"{API}/invoices/{invoice_id}").status == 404
        print("PASS: Bounded admin run generated the INR 2,888.64 snapshot; customer cannot read draft")
        admin.get_by_role("button", name="Correct billing metadata", exact=True).click()
        admin.get_by_label("Due date", exact=True).fill((today + timedelta(days=20)).isoformat())
        admin.get_by_label("Correction reason", exact=True).fill("Agreed twenty-day payment term for this invoice")
        admin.get_by_role("button", name="Save correction", exact=True).click()
        expect(admin.get_by_text("Invoice updated.", exact=True)).to_be_visible()
        admin.get_by_role("button", name="Confirm invoice", exact=True).click()
        expect(admin.get_by_role("button", name="Send invoice email", exact=True)).to_be_visible()
        admin.get_by_role("button", name="Send invoice email", exact=True).click()
        expect(admin.get_by_text("Invoice email sent.", exact=True)).to_be_visible(timeout=30000)
        invoice_number = admin.locator("h1").inner_text()
        deadline, message = time.monotonic() + 15, None
        while time.monotonic() < deadline:
            messages = admin_context.request.get("http://127.0.0.1:8025/api/v1/messages").json().get("messages", [])
            message = next((item for item in messages if invoice_number in item["Subject"] and any(to["Address"] == email for to in item.get("To", []))), None)
            if message:
                break
            time.sleep(0.2)
        assert message, "Invoice email was not captured by Mailpit"
        captured = admin_context.request.get(f"http://127.0.0.1:8025/api/v1/message/{message['ID']}").json()
        assert any(item.get("FileName", item.get("Filename", "")).endswith(".pdf") for item in captured.get("Attachments", [])), "Invoice PDF attachment missing"
        print("PASS: Draft metadata correction, confirmation and real Mailpit delivery with PDF attachment")
        customer.goto(f"{WEB}/portal/invoices")
        customer.get_by_role("link", name=invoice_number, exact=True).click()
        expect(customer.get_by_text("₹2888.64", exact=True).first).to_be_visible()
        expect(customer.get_by_role("button", name="Confirm invoice", exact=True)).to_have_count(0)
        expect(customer.get_by_role("button", name="Send invoice email", exact=True)).to_have_count(0)
        with customer.expect_download() as download_info:
            customer.get_by_role("button", name="Download PDF", exact=True).click()
        output = Path("test-results")
        output.mkdir(exist_ok=True)
        download_info.value.save_as(str(output / "invoice-browser.pdf"))
        text = "\n".join(page.extract_text() for page in PdfReader(output / "invoice-browser.pdf").pages)
        assert "INR 2,888.64" in text
        assert name in text
        customer.emulate_media(media="print")
        assert not customer.locator("header").is_visible()
        customer.emulate_media(media="screen")
        customer.set_viewport_size({"width": 390, "height": 844})
        customer.screenshot(path=str(output / "invoice-customer-mobile.png"), full_page=True)
        assert customer.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Invoice overflows mobile viewport"
        print("PASS: Customer issued invoice, authorized PDF download, print styling and mobile viewport")
        admin.get_by_label("Cancellation reason", exact=True).fill("Synthetic demonstration cancellation")
        admin.get_by_role("button", name="Cancel invoice", exact=True).click()
        expect(admin.get_by_text("Cancelled invoice. Retained as history and excluded from payable balances.", exact=True)).to_be_visible()
        customer.reload()
        expect(customer.get_by_text("Cancelled invoice. Retained as history and excluded from payable balances.", exact=True)).to_be_visible()
        document = customer_context.request.get(f"{API}/invoices/{invoice_id}/document")
        assert "CANCELLED" in PdfReader(BytesIO(document.body())).pages[0].extract_text()
        admin.goto(scope_url)
        admin.get_by_role("button", name="Run billing now", exact=True).click()
        expect(admin.get_by_text("Billing run finished.", exact=True)).to_be_visible(timeout=30000)
        expect(admin.get_by_role("cell", name="EXISTING", exact=True)).to_be_visible()
        records = admin_context.request.get(f"{API}/invoices?subscription_id={subscription['id']}").json()
        assert records["total"] == 1 and records["items"][0]["id"] == invoice_id
        (output / "billing-browser-ids.json").write_text(json.dumps({"subscription_id": subscription["id"], "invoice_id": invoice_id}), encoding="utf-8")
        print("PASS: Cancelled issued copy remains visible; replay preserves its period without replacement")
        print("Billing browser journeys: 4 passed, 0 skipped.")
        browser.close()


if __name__ == "__main__":
    run()
