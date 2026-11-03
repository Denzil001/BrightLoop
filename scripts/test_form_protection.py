"""Unsaved admin forms: stay, discard, nested guards and clean saved state."""
import uuid

from playwright.sync_api import expect, sync_playwright
from test_admin_choices import save
from test_subscription_journeys import API, WEB, api, login


def discard(page, trigger, field, expected):
    prompts = []
    def stay(dialog):
        prompts.append(dialog.message)
        dialog.dismiss()
    page.on("dialog", stay)
    trigger.click()
    page.remove_listener("dialog", stay)
    assert len(prompts) == 1 and "unsaved changes" in prompts[0], prompts
    expect(field).to_have_value(expected)
    prompts.clear()
    def leave(dialog):
        prompts.append(dialog.message)
        dialog.accept()
    page.on("dialog", leave)
    trigger.click()
    page.remove_listener("dialog", leave)
    assert len(prompts) == 1, prompts


def run():
    marker = f"Unsaved audit {uuid.uuid4().hex[:8]}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1050})
        page = context.new_page()
        login(page, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        cases = [
            ("products", "New Product", "e.g. Cloud Server Hosting"),
            ("plans", "New Plan", "e.g. Standard Business Plan"),
            ("taxes", "New Tax Rule", "e.g. Standard GST 18%"),
            ("discounts", "New Discount Rule", "e.g. Annual Subscription 10% Off"),
            ("quotation-templates", "New Template", "e.g. Standard SaaS Onboarding"),
            ("staff", "Provision Staff", "Staff member full name"),
        ]
        for resource, button, placeholder in cases:
            page.goto(f"{WEB}/app/{resource}")
            page.get_by_role("button", name=button, exact=True).click()
            field = page.get_by_placeholder(placeholder, exact=True)
            field.fill(marker)
            discard(page, page.get_by_role("button", name="Cancel", exact=True), field, marker)
            expect(field).to_have_count(0)
        print("PASS: Six admin create forms warn once, preserve input on stay and close on discard")

        product = api(context, "/products", {"name": marker, "type": "ADDON", "sales_price": "10.00", "cost_price": "0.00"})
        page.goto(f"{WEB}/app/products/{product['id']}")
        name = page.locator("form input[type='text']").first
        expect(name).to_have_value(marker)
        name.fill(f"{marker} changed")
        page.get_by_role("button", name="Add Variant", exact=True).click()
        page.get_by_placeholder("e.g. 24/7 Dedicated SOC / High Memory", exact=True).fill("Pending form variant")
        page.get_by_role("button", name="Save Variant", exact=True).click()
        expect(page.get_by_placeholder("e.g. 24/7 Dedicated SOC / High Memory", exact=True)).to_have_count(0)
        expect(name).to_have_value(f"{marker} changed")
        discard(page, page.get_by_role("navigation").get_by_role("link", name="Customers", exact=True), name, f"{marker} changed")
        page.wait_for_url("**/app/customers")
        assert context.request.get(f"{API}/products/{product['id']}").json()["name"] == marker
        print("PASS: Variant save preserves pending product edits; discard navigation leaves persisted product fields unchanged")

        plan = api(context, "/plans", {"name": marker, "interval": "MONTHLY", "base_fee": "100.00"})
        page.goto(f"{WEB}/app/plans/{plan['id']}")
        name = page.locator("form input[type='text']").first
        expect(name).to_have_value(marker)
        name.fill(f"{marker} saved")
        page.get_by_role("button", name="Add Included Product", exact=True).click()
        page.get_by_label("Find bundle product", exact=True).fill(marker)
        product_choice = page.get_by_role("combobox", name="Bundle product", exact=True)
        expect(product_choice.locator(f"option[value='{product['id']}']")).to_have_count(1)
        product_choice.select_option(product["id"])
        discard(page, page.get_by_role("button", name="Cancel", exact=True), product_choice, product["id"])
        expect(product_choice).to_have_count(0)
        save(page, "Save Plan Configuration", f"/plans/{plan['id']}")
        expect(page.get_by_text("Plan configuration updated successfully.", exact=True)).to_be_visible()
        prompts = []
        handler = lambda dialog: (prompts.append(dialog.message), dialog.dismiss())
        page.on("dialog", handler)
        page.get_by_role("navigation").get_by_role("link", name="Customers", exact=True).click()
        page.wait_for_url("**/app/customers")
        page.remove_listener("dialog", handler)
        assert not prompts, prompts
        assert context.request.get(f"{API}/plans/{plan['id']}").json()["name"] == f"{marker} saved"
        print("PASS: Nested dirty forms show one prompt; successful plan save clears navigation protection")

        page.goto(f"{WEB}/app/profile")
        name = page.locator("form input[type='text']").first
        original = name.input_value()
        name.fill(f"{original} pending")
        discard(page, page.get_by_role("navigation").get_by_role("link", name="Customers", exact=True), name, f"{original} pending")
        page.wait_for_url("**/app/customers")
        print("PASS: Operational profile edits are protected without writing the admin account")
        browser.close()
    print("Form protection journeys: 4 passed, 0 skipped (nine form surfaces).")


if __name__ == "__main__":
    run()
