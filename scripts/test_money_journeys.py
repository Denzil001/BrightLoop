"""Browser-to-PostgreSQL decimal transport, edit hydration and validation."""
import re
import uuid
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright
from test_subscription_journeys import API, WEB, api, login
from browser_test_errors import redact


def submit(page, button, endpoint, method="POST"):
    with page.expect_response(lambda response: response.url == f"{API}{endpoint}" and response.request.method == method) as waiting:
        button.click()
    response = waiting.value
    assert response.ok, response.text()
    return response.json(), response.request.post_data_json


def run():
    suffix = uuid.uuid4().hex[:8]
    name, amount = f"Money integrity {suffix}", "90071992547409.93"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        login(page, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        try:
            page.goto(f"{WEB}/app/products")
            page.get_by_role("button", name="New Product", exact=True).click()
            dialog = page.get_by_role("dialog", name="Create New Product", exact=True)
            dialog.get_by_placeholder("e.g. Cloud Server Hosting", exact=True).fill(name)
            dialog.get_by_label(re.compile(r"^Sales Price")).fill(amount)
            dialog.get_by_label(re.compile(r"^Cost Price")).fill(amount)
            product, sent = submit(page, dialog.get_by_role("button", name="Create Product", exact=True), "/products")
            assert sent["sales_price"] == sent["cost_price"] == amount
            assert product["sales_price"] == product["cost_price"] == amount
            expect(dialog).to_have_count(0)
            page.get_by_placeholder("Search products by name or type...", exact=True).fill(name)
            expect(page.get_by_role("cell", name=f"₹{amount}", exact=True)).to_have_count(2)
            page.get_by_role("link", name="Manage", exact=True).click()
            sales = page.get_by_label(re.compile(r"^(?:Base )?Sales Price"))
            expect(sales).to_have_value(amount)
            sales.fill("90071992547409.94")
            page.get_by_role("button", name="Add Variant", exact=True).click()
            variant_dialog = page.get_by_role("dialog")
            variant_dialog.get_by_placeholder("e.g. 24/7 Dedicated SOC / High Memory", exact=True).fill("One cent")
            variant_dialog.get_by_placeholder("e.g. 560.00", exact=True).fill("0.01")
            expect(variant_dialog.get_by_text("₹90071992547409.94", exact=True)).to_be_visible()
            variant, sent = submit(page, variant_dialog.get_by_role("button", name="Save Variant", exact=True), f"/products/{product['id']}/variants")
            assert sent["price_adjustment"] == "0.01" and variant["effective_sales_price"] == "90071992547409.94"
            expect(variant_dialog).to_have_count(0)
            expect(sales).to_have_value("90071992547409.94")
            prompts = []
            page.once("dialog", lambda prompt: (prompts.append(prompt.message), prompt.dismiss()))
            page.get_by_role("navigation").get_by_role("link", name="Customers", exact=True).click()
            assert len(prompts) == 1
            expect(sales).to_have_value("90071992547409.94")
            updated, sent = submit(page, page.get_by_role("button", name="Save Product Details", exact=True), f"/products/{product['id']}", "PATCH")
            assert sent["sales_price"] == updated["sales_price"] == "90071992547409.94"
            page.wait_for_load_state("networkidle")
            expect(sales).to_have_value("90071992547409.94")
            print("PASS: Product/cost transport, display and edit hydration retain cents beyond floating-point precision")
            page.set_viewport_size({"width": 390, "height": 1000})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.set_viewport_size({"width": 1440, "height": 1100})
            print("PASS: Variant preview uses saved base price; cent-only dirty edits survive variant save and cancelled navigation")

            page.goto(f"{WEB}/app/plans")
            page.get_by_role("button", name="New Plan", exact=True).click()
            dialog = page.get_by_role("dialog", name="Create New Subscription Plan", exact=True)
            dialog.get_by_placeholder("e.g. Standard Business Plan", exact=True).fill(name)
            dialog.get_by_label(re.compile(r"^Base Recurring Fee")).fill(amount)
            dialog.get_by_label(re.compile(r"^Excess Seat Unit Price")).fill("0.01")
            plan, sent = submit(page, dialog.get_by_role("button", name="Create Plan", exact=True), "/plans")
            assert sent["base_fee"] == plan["base_fee"] == amount and sent["extra_seat_unit_price"] == "0.01"
            expect(dialog).to_have_count(0)
            page.goto(f"{WEB}/app/plans/{plan['id']}")
            expect(page.get_by_label(re.compile(r"^Base Fee"))).to_have_value(amount)
            print("PASS: Large plan fees retain exact transport and saved form values")

            page.goto(f"{WEB}/app/discounts")
            page.get_by_role("button", name="New Discount Rule", exact=True).click()
            dialog = page.get_by_role("dialog", name="Create New Discount Rule", exact=True)
            dialog.get_by_placeholder("e.g. Annual Subscription 10% Off", exact=True).fill(name)
            dialog.get_by_role("combobox", name="Discount type", exact=True).select_option("FIXED")
            dialog.get_by_label(re.compile(r"^Fixed Discount Amount")).fill(amount)
            dialog.get_by_label(re.compile(r"^Min Purchase")).fill(amount)
            discount, sent = submit(page, dialog.get_by_role("button", name="Create Rule", exact=True), "/discounts")
            assert sent["initial_revision"]["amount"] == sent["initial_revision"]["minimum_purchase"] == amount
            assert discount["revisions"][0]["amount"] == discount["revisions"][0]["minimum_purchase"] == amount
            expect(dialog).to_have_count(0)
            print("PASS: Fixed discount and purchase threshold preserve exact decimal strings")

            page.goto(f"{WEB}/app/customers")
            page.get_by_role("button", name="New Customer", exact=True).click()
            page.get_by_label("Customer / Primary Name").fill("   ")
            email = f"money_invalid_{suffix}@brightloop.test"
            page.get_by_label("Email Address").fill(email)
            with page.expect_response(lambda response: response.url == f"{API}/customers" and response.request.method == "POST") as waiting:
                page.get_by_role("button", name="Save Customer", exact=True).click()
            assert waiting.value.status == 422
            expect(page.locator("#customer-create-error")).to_contain_text("non-whitespace")
            expect(page.get_by_label("Email Address")).to_have_value(email)
            assert context.request.get(f"{API}/customers?search={email}").json()["total"] == 0
            assert not errors, errors
            print("PASS: Whitespace-only customer name has actionable feedback, preserves input and creates no record")
        finally:
            failed = sys.exc_info()[0] is not None
            cleanup_errors = []
            for endpoint in ("products", "plans", "discounts"):
                try:
                    response = context.request.get(f"{API}/{endpoint}", params={"search": name, "page_size": 100}, max_retries=2)
                    assert response.ok
                    for item in response.json()["items"]:
                        if item["name"] != name:
                            continue
                        if endpoint == "discounts":
                            if not item["disabled_from"]:
                                api(context, f"/discounts/{item['id']}/deactivate", {"disabled_from": datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(), "reason": "Synthetic decimal verification completed"})
                        elif item["active"]:
                            assert api(context, f"/{endpoint}/{item['id']}/archive", {})["active"] is False
                except Exception as error:
                    cleanup_errors.append(redact(str(error)))
            browser.close()
            if cleanup_errors:
                if failed:
                    print("Synthetic fixture cleanup also failed:", cleanup_errors)
                else:
                    raise RuntimeError("Synthetic fixture cleanup failed: " + "; ".join(cleanup_errors))
    print("Money browser journeys: 5 passed, 0 skipped.")


if __name__ == "__main__":
    run()
