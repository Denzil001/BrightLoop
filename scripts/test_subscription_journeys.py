"""Real-browser Phase 4 quote acceptance and customer request review.

Requires local backend, production frontend, and the documented demo admin.
Creates only uniquely named synthetic .test records in the development database.
"""
from datetime import datetime, timedelta
import re
import sys
import time
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright
from browser_test_errors import install_redaction

install_redaction()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WEB = "http://localhost:3000"
API = "http://localhost:8000/api/v1"


def wait_for_retry_after(response):
    """Respect a confirmed pre-operation throttle; never retry ambiguous writes."""
    seconds = int(response.headers.get("retry-after", "0"))
    assert 1 <= seconds <= 300, "Missing or out-of-range authentication Retry-After"
    print(f"Authentication throttle observed; respecting Retry-After ({seconds}s) before one retry.", flush=True)
    while seconds:
        delay = min(seconds, 30)
        time.sleep(delay)
        seconds -= delay


def login(page, email, password, landing):
    page.goto(f"{WEB}/login")
    page.locator("#email").fill(email)
    page.locator("#password").fill(password)
    for attempt in range(2):
        with page.expect_response(lambda r: r.request.method == "POST" and r.url == f"{API}/auth/login") as result:
            page.get_by_role("button", name="Sign in", exact=True).click()
        response = result.value
        if response.status == 429 and attempt == 0:
            wait_for_retry_after(response)
            assert page.locator("#email").input_value() == email, "Throttled sign-in lost the email input"
            assert page.locator("#password").input_value() == password, "Throttled sign-in lost the password input"
            continue
        assert response.ok, f"Browser sign-in failed: HTTP {response.status}"
        break
    expected = {"/app/customers": "/app", "/portal/profile": "/portal"}.get(landing, landing)
    page.wait_for_url(f"**{expected}")


def api(context, path, payload):
    cookies = {c["name"]: c["value"] for c in context.cookies()}
    csrf = cookies.get("brightloop_csrf")
    if not csrf:
        csrf = context.request.get(f"{API}/auth/csrf").json()["csrf_token"]
    for attempt in range(2):
        response = context.request.post(f"{API}{path}", data=payload,
                                        headers={"X-CSRF-Token": csrf, "Origin": WEB})
        if response.status == 429 and path.startswith("/auth/") and attempt == 0:
            wait_for_retry_after(response)
            continue
        break
    assert response.ok, f"{path}: {response.status} {response.text()}"
    return response.json()


def run():
    suffix = uuid.uuid4().hex[:8]
    email, name = f"subscription_{suffix}@brightloop.test", f"Subscription customer {suffix}"
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        customer_context = browser.new_context()
        api(customer_context, "/auth/register", {"name": name, "email": email, "password": "Customer@Secure123"})
        customer = customer_context.new_page()
        customer.on("dialog", lambda dialog: dialog.accept())
        login(customer, email, "Customer@Secure123", "/portal/profile")
        admin_context = browser.new_context()
        admin = admin_context.new_page()
        admin.on("dialog", lambda dialog: dialog.accept())
        login(admin, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app/customers")
        plan = api(admin_context, "/plans", {"name": f"Subscription daily {suffix}", "base_fee": "1000.00",
                   "minimum_seats": 5, "extra_seat_unit_price": "100.00", "interval": "DAILY"})
        products, discounts = [], []
        for i, price in enumerate(["100.00", "200.00"]):
            product = api(admin_context, "/products", {"name": f"Subscription add-on {suffix} {i}",
                "type": "ADDON", "sales_price": price, "cost_price": "10.00"})
            products.append(product)
            discounts.append(api(admin_context, "/discounts", {"name": f"Subscription discount {suffix} {i}",
                "initial_revision": {"type": "PERCENT" if i == 0 else "FIXED",
                    **({"rate": "10.00"} if i == 0 else {"amount": "30.00"}), "scope": "PRODUCT",
                    "valid_from": today.isoformat(), "valid_to": (today + timedelta(days=365)).isoformat(),
                    "product_ids": [product["id"]]}}))
        customer_data = admin_context.request.get(f"{API}/customers?search={email}").json()["items"][0]
        staff_email = f"subscription_staff_{suffix}@brightloop.test"
        api(admin_context, "/staff", {"name": f"Subscription staff {suffix}", "email": staff_email,
                                     "initial_password": "Staff@Secure123"})
        staff_context = browser.new_context()
        admin = staff_context.new_page()
        admin.on("dialog", lambda dialog: dialog.accept())
        login(admin, staff_email, "Staff@Secure123", "/app/customers")
        admin.goto(f"{WEB}/app/subscriptions/new")
        admin.get_by_label("Find customer", exact=True).fill(name)
        admin.get_by_label("Find plan", exact=True).fill(plan["name"])
        admin.get_by_role("combobox", name=re.compile(r"^Customer")).select_option(customer_data["id"])
        admin.get_by_role("combobox", name=re.compile(r"^Plan")).select_option(plan["id"])
        admin.get_by_label("Seat quantity", exact=True).fill("7")
        admin.get_by_label("Service expiry (exclusive)", exact=True).fill((today + timedelta(days=365)).isoformat())
        admin.get_by_label("Find product", exact=True).fill(f"Subscription add-on {suffix}")
        for i, product in enumerate(products):
            admin.get_by_role("button", name="Add product", exact=True).click()
            admin.get_by_role("combobox", name=re.compile(r"^Product")).nth(i).select_option(product["id"])
        admin.get_by_role("listbox", name="Discount rules", exact=True).select_option([d["id"] for d in discounts])
        admin.get_by_role("button", name="Preview pricing", exact=True).click()
        expect(admin.get_by_text("Estimated total ₹1460.00", exact=True)).to_be_visible()
        admin.get_by_role("button", name="Save draft", exact=True).click()
        admin.wait_for_url(re.compile(r"/app/subscriptions/[0-9a-f-]+$"))
        subscription_id = admin.url.rsplit("/", 1)[1]
        admin.get_by_role("button", name="Issue quotation", exact=True).click()
        expect(admin.get_by_role("button", name="Confirm agreement", exact=True)).to_be_visible()
        quoted = staff_context.request.get(f"{API}/subscriptions/{subscription_id}").json()["agreements"][0]
        assert quoted["state"] == "ISSUED"
        admin.get_by_role("button", name="Revise quotation", exact=True).click()
        admin.get_by_label("Payment term (days)", exact=True).fill("20")
        admin.get_by_role("button", name="Save draft", exact=True).click()
        expect(admin.get_by_text("Draft saved.", exact=True)).to_be_visible()
        admin.get_by_role("button", name="Issue quotation", exact=True).click()
        expect(admin.get_by_role("button", name="Confirm agreement", exact=True)).to_be_visible()
        revised = staff_context.request.get(f"{API}/subscriptions/{subscription_id}").json()["agreements"]
        original = next(a for a in revised if a["id"] == quoted["id"])
        assert original["state"] == "SUPERSEDED" and original["payment_term_days"] == 15, "Original quotation state/terms did not match the completed revision"
        assert original["lines"] == quoted["lines"], "Revising a quote changed its historical lines"
        assert revised[0]["payment_term_days"] == 20 and revised[0]["sequence"] == quoted["sequence"] + 1
        for button in ("Confirm agreement", "Activate service"):
            admin.get_by_role("button", name=button, exact=True).click()
        expect(admin.get_by_text(re.compile(r"ACTIVE · 7 seats"))).to_be_visible()
        print("PASS: Staff editor/preview, issue/revise with immutable quote history, confirm and activate")

        customer.goto(f"{WEB}/portal/subscriptions")
        customer.get_by_role("link", name=re.compile("SUB-")).click()
        expect(customer.get_by_text("Recurring estimate ₹1460.00", exact=True)).to_be_visible()
        expect(customer.get_by_role("button", name="Confirm agreement", exact=True)).to_have_count(0)
        customer.get_by_role("combobox", name=re.compile(r"^Action")).select_option("ADDON_CHANGE")
        for index, product in enumerate(products):
            expect(customer.get_by_role("group", name=f"Line {index + 1}", exact=True)).to_be_visible()
        customer.get_by_label("Find product", exact=True).fill("No matching product for selected hydration")
        for index, product in enumerate(products):
            select = customer.get_by_role("group", name=f"Line {index + 1}", exact=True).get_by_role("combobox", name=re.compile(r"^Product"))
            expect(select.locator("option:checked")).to_have_text(product["name"])
        customer.get_by_role("combobox", name=re.compile(r"^Action")).select_option("PAUSE")
        customer.get_by_label("Reason / note", exact=True).fill("Pause while travelling")
        customer.get_by_label("Effective date", exact=True).fill((today + timedelta(days=1)).isoformat())
        customer.get_by_role("button", name="Submit request", exact=True).click()
        expect(customer.get_by_text(re.compile(r"PAUSE · PENDING"))).to_be_visible()
        print("PASS: Customer-owned subscription, safe estimate and pending request")

        admin.reload()
        admin.get_by_role("button", name="Review request", exact=True).click()
        admin.get_by_label("Review reason", exact=True).fill("Please review the effective date before resubmitting")
        admin.get_by_role("button", name="Reject", exact=True).click()
        expect(admin.get_by_text(re.compile(r"PAUSE · REJECTED"))).to_be_visible()
        customer.reload()
        expect(customer.get_by_text("Team response: Please review the effective date before resubmitting", exact=True)).to_be_visible()
        expect(customer.get_by_text(re.compile(r"Reviewed by Subscription staff"))).to_be_visible()
        customer.get_by_role("button", name="Prepare new request", exact=True).click()
        expect(customer.get_by_role("textbox", name="Reason / note", exact=True)).to_have_value("Pause while travelling")
        expect(customer.get_by_label("Effective date", exact=True)).to_have_value((today + timedelta(days=1)).isoformat())
        customer.get_by_role("textbox", name="Reason / note", exact=True).fill("Revised pause request")
        customer.get_by_role("button", name="Submit request", exact=True).click()
        expect(customer.get_by_text(re.compile(r"PAUSE · PENDING"))).to_be_visible()
        customer.get_by_role("button", name="Cancel request", exact=True).click()
        expect(customer.get_by_text(re.compile(r"PAUSE · CANCELLED"))).to_be_visible()
        expect(customer.get_by_text(re.compile(r"ACTIVE · 7 seats"))).to_be_visible()
        print("PASS: Rejection context, request prefill/resubmission and customer cancellation preserve service")
        customer.get_by_role("combobox", name=re.compile(r"^Action")).select_option("PAUSE")
        customer.get_by_label("Reason / note", exact=True).fill("Pause while travelling")
        customer.get_by_label("Effective date", exact=True).fill((today + timedelta(days=1)).isoformat())
        customer.get_by_role("button", name="Submit request", exact=True).click()
        expect(customer.get_by_text(re.compile(r"PAUSE · PENDING"))).to_be_visible()
        admin.reload()
        admin.get_by_role("button", name="Review request", exact=True).click()
        admin.get_by_label("Review reason", exact=True).fill("Approved at the next daily boundary")
        admin.get_by_role("button", name="Approve", exact=True).click()
        expect(admin.get_by_text(re.compile(r"PAUSE · APPROVED"))).to_be_visible()
        expect(admin.get_by_text("A scheduled change is awaiting its effective date.", exact=True)).to_be_visible()
        customer.reload()
        expect(customer.get_by_text("Team response: Approved at the next daily boundary", exact=True)).to_be_visible()
        expect(customer.get_by_text(re.compile(r"ACTIVE · 7 seats"))).to_be_visible()
        print("PASS: Operational review, customer feedback, no premature state change")
        output = Path("test-results")
        output.mkdir(exist_ok=True)
        admin.screenshot(path=str(output / "subscriptions-staff.png"), full_page=True)
        customer.set_viewport_size({"width": 390, "height": 844})
        customer.screenshot(path=str(output / "subscriptions-customer-mobile.png"), full_page=True)
        assert customer.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Customer page overflows mobile viewport"
        print("Subscription browser journeys: 4 passed, 0 skipped.")
        browser.close()


if __name__ == "__main__":
    run()
