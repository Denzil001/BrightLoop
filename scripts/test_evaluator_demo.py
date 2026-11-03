"""One linked, real-UI evaluator rehearsal using uniquely named synthetic data.

Requires the documented local admin, production app, Chrome and Mailpit. Catalog
configuration, registration, quotation, billing, payments and requests use the
actual pages. API reads independently reconcile persisted results; only staff
provisioning is a preflight API write. No presenter participation is fabricated.
"""
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import sys
import time
import uuid
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright
from pypdf import PdfReader
from test_subscription_journeys import API, WEB, api, login

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.calendar import boundary


def get(context, path):
    response = context.request.get(f"{API}{path}", max_retries=2)
    assert response.ok, f"Demo read {path}: HTTP {response.status}"
    return response.json()


def tax_assignment(dialog, name):
    dialog.get_by_label("Find tax rule", exact=True).fill(name)
    dialog.get_by_role("checkbox", name=re.compile(re.escape(name))).check()


def catalog(page, prefix):
    tax_name, product_name = f"{prefix} GST", f"{prefix} server"
    plan_name, discount_name, template_name = f"{prefix} monthly", f"{prefix} ten percent", f"{prefix} template"
    page.goto(f"{WEB}/app/taxes")
    page.get_by_role("button", name="New Tax Rule", exact=True).click()
    dialog = page.get_by_role("dialog", name="Create New Tax Rule", exact=True)
    dialog.get_by_placeholder("e.g. Standard GST 18%", exact=True).fill(tax_name)
    dialog.get_by_placeholder("e.g. GST, VAT, SALES_TAX", exact=True).fill("GST")
    dialog.get_by_placeholder("18.0000", exact=True).fill("18.0000")
    dialog.get_by_role("button", name="Save Rule", exact=True).click()
    expect(dialog).not_to_be_visible()

    page.goto(f"{WEB}/app/products")
    page.get_by_role("button", name="New Product", exact=True).click()
    dialog = page.get_by_role("dialog", name="Create New Product", exact=True)
    dialog.get_by_placeholder("e.g. Cloud Server Hosting", exact=True).fill(product_name)
    dialog.get_by_placeholder("e.g. INFRASTRUCTURE, ADDON, SERVICE", exact=True).fill("SERVER")
    dialog.locator('input[type="number"]').nth(0).fill("200.00")
    dialog.locator('input[type="number"]').nth(1).fill("80.00")
    dialog.locator("textarea").fill("Synthetic internal vendor information")
    tax_assignment(dialog, tax_name)
    dialog.get_by_role("button", name="Create Product", exact=True).click()
    expect(dialog).not_to_be_visible()
    page.locator('input[placeholder^="Search"]').first.fill(product_name)
    page.get_by_role("row").filter(has_text=product_name).get_by_role("link", name="Manage", exact=True).click()
    page.wait_for_url(re.compile(r"/app/products/[0-9a-f-]+$"))
    product_id = page.url.rsplit("/", 1)[1]
    page.get_by_role("button", name="Add Variant", exact=True).click()
    dialog = page.get_by_role("dialog", name="Add Product Variant", exact=True)
    dialog.get_by_placeholder("e.g. 24/7 Dedicated SOC / High Memory", exact=True).fill("High memory")
    dialog.get_by_placeholder("e.g. 560.00", exact=True).fill("560.00")
    expect(dialog.get_by_text("₹760.00", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="Save Variant", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_text("₹760.00", exact=True)).to_be_visible()

    page.goto(f"{WEB}/app/plans")
    page.get_by_role("button", name="New Plan", exact=True).click()
    dialog = page.get_by_role("dialog", name="Create New Subscription Plan", exact=True)
    dialog.get_by_placeholder("e.g. Standard Business Plan", exact=True).fill(plan_name)
    for index, value in enumerate(("1000.00", "5", "100.00")):
        dialog.locator('input[type="number"]').nth(index).fill(value)
    dialog.locator("select").first.select_option("MONTHLY")
    tax_assignment(dialog, tax_name)
    dialog.get_by_role("button", name="Create Plan", exact=True).click()
    expect(dialog).not_to_be_visible()
    page.locator('input[placeholder^="Search"]').first.fill(plan_name)
    page.get_by_role("row").filter(has_text=plan_name).get_by_role("link", name="Manage", exact=True).click()
    page.wait_for_url(re.compile(r"/app/plans/[0-9a-f-]+$"))
    plan_id = page.url.rsplit("/", 1)[1]

    page.goto(f"{WEB}/app/discounts")
    page.get_by_role("button", name="New Discount Rule", exact=True).click()
    dialog = page.get_by_role("dialog", name="Create New Discount Rule", exact=True)
    dialog.get_by_placeholder("e.g. Annual Subscription 10% Off", exact=True).fill(discount_name)
    dialog.get_by_placeholder("Leave empty for unlimited redemptions", exact=True).fill("50")
    dialog.locator("select").nth(0).select_option("SUBSCRIPTION")
    dialog.locator("select").nth(1).select_option("PERCENT")
    dialog.locator('input[type="number"]').nth(1).fill("10.00")
    dialog.get_by_role("button", name="Create Rule", exact=True).click()
    expect(dialog).not_to_be_visible()

    page.goto(f"{WEB}/app/quotation-templates")
    page.get_by_role("button", name="New Template", exact=True).click()
    dialog = page.get_by_role("dialog", name="Create Quotation Template", exact=True)
    dialog.get_by_placeholder("e.g. Standard SaaS Onboarding", exact=True).fill(template_name)
    dialog.get_by_label("Find template plan", exact=True).fill(plan_name)
    dialog.locator("select").select_option(label=plan_name)
    dialog.locator('input[type="number"]').fill("30")
    dialog.get_by_role("button", name="Create & Configure Lines", exact=True).click()
    page.wait_for_url(re.compile(r"/app/quotation-templates/[0-9a-f-]+$"))
    template_id = page.url.rsplit("/", 1)[1]
    page.get_by_role("button", name="Add Template Line", exact=True).click()
    dialog = page.get_by_role("dialog", name="Add Line Item to Template", exact=True)
    dialog.locator("select").nth(0).select_option("ADDON")
    dialog.get_by_label("Find template product", exact=True).fill(product_name)
    dialog.locator("select").nth(1).select_option(label=f"{product_name} (₹200.00)")
    dialog.locator("select").nth(2).select_option(label="High memory (+₹560.00)")
    dialog.locator('input[type="number"]').fill("2")
    dialog.get_by_role("button", name="Add Line", exact=True).click()
    expect(dialog).not_to_be_visible()
    page.locator("#tplActive").check()
    page.get_by_role("button", name="Save Template", exact=True).click()
    expect(page.get_by_text("Quotation template saved successfully.", exact=True)).to_be_visible()
    return {"product_id": product_id, "plan_id": plan_id, "template_id": template_id,
            "plan_name": plan_name, "discount_name": discount_name, "template_name": template_name}


def payment(page, amount, method, note):
    page.get_by_role("button", name="Record payment", exact=True).click()
    dialog = page.get_by_role("dialog", name="Record payment", exact=True)
    dialog.get_by_label("Amount received (₹)", exact=True).fill(amount)
    dialog.get_by_role("combobox", name="Payment method", exact=True).select_option(method)
    dialog.get_by_label("Customer-visible payment note", exact=False).fill(note)
    dialog.get_by_role("button", name="Save payment", exact=True).click()
    expect(page.get_by_text("Payment recorded.", exact=True)).to_be_visible()
    expect(dialog).not_to_be_visible()


def run():
    suffix = uuid.uuid4().hex[:8]
    prefix = f"Rehearsal {suffix}"
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    output = ROOT / "test-results"
    output.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        admin_context = browser.new_context()
        admin = admin_context.new_page()
        admin.on("dialog", lambda prompt: prompt.accept())
        login(admin, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        assert admin_context.request.get("http://127.0.0.1:8025/api/v1/messages").ok
        configured = catalog(admin, prefix)
        print("PASS: Admin configured tax, product/cost, +560 variant, taxed monthly plan, 10% discount and active two-unit template through the UI")
        staff_email = f"rehearsal_staff_{suffix}@brightloop.test"
        api(admin_context, "/staff", {"name": f"{prefix} staff", "email": staff_email, "initial_password": "Staff@Secure123"})
        customer_email, customer_name = f"rehearsal_{suffix}@brightloop.test", f"{prefix} customer"
        customer_context = browser.new_context()
        customer = customer_context.new_page()
        customer.on("dialog", lambda prompt: prompt.accept())
        customer.goto(f"{WEB}/register")
        customer.locator("#name").fill(customer_name)
        customer.locator("#email").fill("invalid-email")
        customer.locator("#password").fill("Customer@Secure123")
        customer.locator("#confirmPassword").fill("Customer@Secure123")
        customer.get_by_role("button", name="Sign up", exact=True).click()
        assert customer.locator("#email").evaluate("element => element.validity.typeMismatch && !!element.validationMessage")
        assert customer.url.endswith("/register")
        customer.locator("#email").fill(customer_email)
        customer.get_by_role("button", name="Sign up", exact=True).click()
        customer.wait_for_url(re.compile(r"/login(?:\?.*)?$"))
        login(customer, customer_email, "Customer@Secure123", "/portal")
        customer_id = get(admin_context, f"/customers?search={customer_email}")["items"][0]["id"]
        assert customer_context.request.get(f"{API}/products").status == 403
        print("PASS: Invalid email feedback preserves registration, valid signup creates the owned portal, customer cannot access configuration")

        staff_context = browser.new_context()
        staff = staff_context.new_page()
        staff.on("dialog", lambda prompt: prompt.accept())
        login(staff, staff_email, "Staff@Secure123", "/app")
        staff.goto(f"{WEB}/app/subscriptions/new")
        staff.get_by_label("Find customer", exact=True).fill(customer_name)
        staff.get_by_role("combobox", name="Customer", exact=True).select_option(label=customer_name)
        staff.get_by_label("Find plan", exact=True).fill(configured["plan_name"])
        staff.get_by_role("combobox", name="Plan", exact=True).select_option(label=f"{configured['plan_name']} · MONTHLY")
        staff.get_by_label("Find quotation template", exact=True).fill(configured["template_name"])
        staff.get_by_role("combobox", name="Quotation template", exact=True).select_option(label=configured["template_name"])
        staff.get_by_label("Seat quantity", exact=True).fill("7")
        staff.get_by_label("Service start", exact=True).fill(today.isoformat())
        staff.get_by_label("Service expiry (exclusive)", exact=True).fill((today + timedelta(days=365)).isoformat())
        staff.get_by_label("Find discount rule", exact=True).fill(configured["discount_name"])
        staff.get_by_role("listbox", name="Discount rules", exact=True).select_option(label=configured["discount_name"])
        staff.get_by_role("button", name="Preview pricing", exact=True).click()
        expect(staff.get_by_text("Estimated total ₹2888.64", exact=True)).to_be_visible()
        staff.get_by_role("button", name="Save & issue quotation", exact=True).click()
        staff.wait_for_url(re.compile(r"/app/subscriptions/[0-9a-f-]+$"))
        subscription_id = staff.url.rsplit("/", 1)[1]
        for action in ("Confirm agreement", "Activate service"):
            staff.get_by_role("button", name=action, exact=True).click()
        expect(staff.get_by_text(re.compile("ACTIVE · 7 seats"))).to_be_visible()
        print("PASS: Staff used the configured template and discount, previewed 2,888.64, issued/confirmed the existing subscription and activated service")

        run_url = f"{WEB}/app/billing-runs?subscription_id={subscription_id}"
        admin.goto(run_url)
        admin.get_by_role("button", name="Run billing now", exact=True).click()
        expect(admin.get_by_text("Billing run finished.", exact=True)).to_be_visible()
        admin.get_by_role("link", name="View invoice", exact=True).click()
        admin.wait_for_url(re.compile(r"/app/invoices/[0-9a-f-]+$"))
        invoice_id = admin.url.rsplit("/", 1)[1]
        expect(admin.get_by_text("₹2888.64", exact=True)).to_be_visible()
        assert customer_context.request.get(f"{API}/invoices/{invoice_id}").status == 404
        admin.get_by_role("button", name="Confirm invoice", exact=True).click()
        admin.get_by_role("button", name="Send invoice email", exact=True).click()
        expect(admin.get_by_text("Invoice email sent.", exact=True)).to_be_visible()
        invoice_number = admin.locator("h1").inner_text()
        deadline, message = time.monotonic() + 15, None
        while time.monotonic() < deadline:
            inbox = admin_context.request.get("http://127.0.0.1:8025/api/v1/messages").json().get("messages", [])
            message = next((item for item in inbox if invoice_number in item["Subject"] and
                            any(to["Address"] == customer_email for to in item.get("To", []))), None)
            if message:
                break
            time.sleep(.2)
        assert message, "Demo invoice was not captured by Mailpit"
        captured = admin_context.request.get(f"http://127.0.0.1:8025/api/v1/message/{message['ID']}").json()
        assert any(item.get("FileName", item.get("Filename", "")).endswith(".pdf") for item in captured.get("Attachments", []))
        print("PASS: Scoped UI billing created one exact invoice; confirmation and real Mailpit PDF delivery completed")

        staff.goto(f"{WEB}/app/invoices/{invoice_id}")
        payment(staff, "1000.00", "BANK_TRANSFER", "Rehearsal first installment")
        partial = get(admin_context, f"/invoices/{invoice_id}")
        assert partial["paid"] == "1000.00" and partial["remaining"] == "1888.64"
        payment(staff, "1888.64", "UPI", "Rehearsal final installment")
        settled = get(admin_context, f"/invoices/{invoice_id}")
        assert settled["state"] == "PAID" and settled["paid"] == "2888.64" and settled["remaining"] == "0.00"
        assert settled["payment_count"] == 2
        customer.goto(f"{WEB}/portal/invoices/{invoice_id}")
        expect(customer.get_by_role("button", name="Record payment", exact=True)).to_have_count(0)
        with customer.expect_download() as download:
            customer.get_by_role("button", name="Download PDF", exact=True).click()
        download.value.save_as(str(output / "evaluator-invoice.pdf"))
        text = "\n".join(page.extract_text() for page in PdfReader(output / "evaluator-invoice.pdf").pages)
        assert "INR 2,888.64" in text and customer_name in text
        customer.goto(f"{WEB}/portal/payments?invoice_id={invoice_id}")
        payment_id = settled["payments"][0]["id"]
        customer.get_by_role("button", name=payment_id, exact=True).click()
        drawer = customer.get_by_role("dialog", name="Payment details", exact=True)
        expect(drawer.get_by_text("Recorded by / at", exact=True)).to_have_count(0)
        with customer.expect_download() as receipt:
            drawer.get_by_role("button", name="Download receipt", exact=True).click()
        receipt.value.save_as(str(output / "evaluator-receipt.pdf"))
        drawer.get_by_role("button", name="Close payment details", exact=True).click()
        print("PASS: Two staff payments reconcile exactly; customer sees owned paid history and authorized invoice/receipt downloads")

        customer.goto(f"{WEB}/portal/subscriptions/{subscription_id}")
        customer.get_by_role("combobox", name="Action", exact=True).select_option("PAUSE")
        customer.get_by_role("textbox", name="Reason / note", exact=True).fill("Rehearsal travel pause")
        customer.get_by_label("Effective date", exact=True).fill(boundary(today, "MONTHLY", 1).isoformat())
        customer.get_by_role("button", name="Submit request", exact=True).click()
        expect(customer.get_by_text(re.compile("PAUSE · PENDING"))).to_be_visible()
        staff.goto(f"{WEB}/app/subscriptions/{subscription_id}")
        staff.get_by_role("button", name="Review request", exact=True).click()
        staff.get_by_label("Review reason", exact=True).fill("Review travel dates and resubmit")
        staff.get_by_role("button", name="Reject", exact=True).click()
        expect(staff.get_by_text(re.compile("PAUSE · REJECTED"))).to_be_visible()
        customer.reload()
        expect(customer.get_by_text("Team response: Review travel dates and resubmit", exact=True)).to_be_visible()
        customer.get_by_role("button", name="Prepare new request", exact=True).click()
        customer.get_by_role("button", name="Submit request", exact=True).click()
        expect(customer.get_by_text(re.compile("PAUSE · PENDING"))).to_be_visible()
        customer.get_by_role("button", name="Cancel request", exact=True).click()
        expect(customer.get_by_text(re.compile("PAUSE · CANCELLED"))).to_be_visible()
        expect(customer.get_by_text(re.compile("ACTIVE · 7 seats"))).to_be_visible()

        admin.goto(f"{WEB}/app/reports?customer_id={customer_id}&plan_id={configured['plan_id']}")
        expect(admin.get_by_text("Received in selected range", exact=True).locator("..").get_by_text("₹2888.64", exact=True)).to_be_visible()
        expect(admin.get_by_text("Current outstanding", exact=True).locator("..").get_by_text("₹0.00", exact=True)).to_be_visible()
        metrics = get(admin_context, f"/reports/summary?customer_id={customer_id}&plan_id={configured['plan_id']}")
        assert metrics["received"] == "2888.64" and metrics["outstanding"] == "0.00" and metrics["active_subscriptions"] == 1
        admin.goto(run_url)
        admin.get_by_role("button", name="Run billing now", exact=True).click()
        expect(admin.get_by_text("Billing run finished.", exact=True)).to_be_visible()
        expect(admin.get_by_role("cell", name="EXISTING", exact=True)).to_be_visible()
        assert get(admin_context, f"/invoices?subscription_id={subscription_id}")["total"] == 1
        assert get(admin_context, f"/invoices/{invoice_id}")["payment_count"] == 2
        customer.set_viewport_size({"width": 390, "height": 844})
        customer.goto(f"{WEB}/portal/invoices/{invoice_id}")
        expect(customer.get_by_text("₹2888.64", exact=True).first).to_be_visible()
        assert customer.evaluate("document.documentElement.scrollWidth <= innerWidth")
        customer.screenshot(path=str(output / "evaluator-customer-mobile.png"), full_page=True)
        record = {"timestamp": datetime.now(ZoneInfo("UTC")).isoformat(), "kind": "automated linked UI rehearsal",
            "build_id": (ROOT / "frontend/.next/BUILD_ID").read_text(encoding="utf-8").strip(),
            "customer_id": customer_id, "subscription_id": subscription_id, "invoice_id": invoice_id,
            "catalog": configured, "invoice_total": "2888.64", "payment_count": 2,
            "received": metrics["received"], "outstanding": metrics["outstanding"], "status": "PASS",
            "human_presenters": "Not simulated; use the team handoff guide"}
        (output / "evaluator-rehearsal.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print("PASS: Customer request rejection/resubmission/cancellation, reconciled report, billing replay and mobile history remain consistent")
        browser.close()
    print("Evaluator linked UI rehearsal: PASS.")


if __name__ == "__main__":
    run()
