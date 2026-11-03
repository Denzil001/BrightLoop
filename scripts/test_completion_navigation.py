"""Read-only benchmark-schema checks for final navigation and large selectors."""
import json
import re
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
API, WEB = "http://localhost:8001/api/v1", "http://localhost:3001"


def login(context, role):
    csrf = context.request.get(f"{API}/auth/csrf").json()["csrf_token"]
    response = context.request.post(f"{API}/auth/login", data={"email": f"benchmark_{role}@brightloop.test", "password": "Benchmark@Secure123"},
        headers={"X-CSRF-Token": csrf, "Origin": WEB})
    assert response.ok


def run():
    manifest = json.loads((ROOT / "test-results/benchmark-manifest.json").read_text())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        public = browser.new_context()
        page = public.new_page()
        page.goto(WEB)
        page.wait_for_url("**/login")
        admin = browser.new_context(viewport={"width": 1440, "height": 1000})
        login(admin, "admin")
        page = admin.new_page()
        page.goto(WEB)
        page.wait_for_url("**/app")
        expect(page.get_by_role("heading", name="Operational overview", exact=True)).to_be_visible()
        page.goto(f"{WEB}/app/subscriptions/new")
        page.get_by_role("combobox", name=re.compile(r"^Plan")).select_option(manifest["plan_id"])
        page.get_by_label("Find quotation template", exact=True).fill("0199")
        templates = page.get_by_role("combobox", name=re.compile(r"^Quotation template"))
        expect(templates.locator("option").filter(has_text="Benchmark template 0199")).to_have_count(1)
        templates.select_option(label="Benchmark template 0199")
        expect(page.get_by_role("combobox", name=re.compile(r"^Product")).locator("option:checked")).to_have_text("Benchmark product 0199")
        page.get_by_label("Find discount rule", exact=True).fill("0199")
        rules = page.get_by_role("listbox", name="Discount rules", exact=True)
        expect(rules.locator("option").filter(has_text="Benchmark discount 0199")).to_have_count(1)
        rules.select_option(label="Benchmark discount 0199")
        page.get_by_label("Find discount rule", exact=True).fill("0198")
        expect(rules.locator("option").filter(has_text="Benchmark discount 0198")).to_have_count(1)
        expect(rules.locator("option:checked")).to_have_text("Benchmark discount 0199")
        print("PASS: Template/product/discount beyond the first 100 records are selectable; selected rule survives searching")
        messages = []
        page.once("dialog", lambda dialog: (messages.append(dialog.message), dialog.dismiss()))
        page.get_by_role("link", name="Customers", exact=True).click()
        assert messages and "unsaved changes" in messages[0]
        assert page.url.endswith("/app/subscriptions/new")
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("link", name="Customers", exact=True).click()
        page.wait_for_url("**/app/customers")
        print("PASS: Internal navigation warns, cancel preserves the editor and confirmed discard navigates")
        customer = browser.new_context(viewport={"width": 390, "height": 844})
        login(customer, "customer")
        page = customer.new_page()
        page.goto(WEB)
        page.wait_for_url("**/portal")
        expect(page.get_by_role("heading", name="My overview", exact=True)).to_be_visible()
        nav = page.get_by_role("navigation", name="Workspace navigation", include_hidden=True)
        expect(nav).not_to_be_visible()
        page.get_by_role("button", name="Menu", exact=True).click()
        expect(nav).to_be_visible()
        nav.get_by_role("link", name="My subscriptions", exact=True).click()
        page.wait_for_url("**/portal/subscriptions")
        expect(page.locator("tbody tr").first).to_be_visible()
        expect(nav).not_to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        print("PASS: Public/admin/customer root redirects and collapsible mobile navigation work")
        browser.close()
    print("Completion navigation journeys: 3 passed, 0 skipped.")


from browser_test_errors import install_redaction
install_redaction()


if __name__ == "__main__":
    run()
