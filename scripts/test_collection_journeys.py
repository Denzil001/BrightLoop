"""Persisted list filters, SQL sorting and an intentionally delayed old response."""
from urllib.parse import parse_qs, urlparse
import uuid

from playwright.sync_api import expect, sync_playwright
from test_subscription_journeys import API, WEB, api, login


def run():
    prefix = f"List audit {uuid.uuid4().hex[:8]}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        login(page, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        page.goto(f"{WEB}/app/customers")
        page.get_by_role("button", name="New Customer", exact=True).click()
        page.get_by_label("Customer / Primary Name").fill(prefix)
        page.get_by_label("Email Address", exact=False).fill("bad@domain")
        page.locator("form").get_by_role("button", name="Save Customer", exact=True).click()
        expect(page.locator("#customer-create-error")).to_contain_text("email")
        expect(page.locator("#customer-create-error")).to_contain_text("valid")
        expect(page.get_by_label("Email Address", exact=False)).to_have_value("bad@domain")
        expect(page.get_by_label("Customer / Primary Name")).to_have_value(prefix)
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.get_by_role("button", name="Cancel", exact=True).click()
        expect(page.get_by_label("Email Address", exact=False)).to_have_value("bad@domain")
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="Cancel", exact=True).click()
        expect(page.get_by_label("Email Address", exact=False)).to_have_count(0)
        print("PASS: Invalid customer email has actionable feedback and preserves form input")
        alpha, zulu = f"{prefix} Alpha", f"{prefix} Zulu"
        for index, name in enumerate((alpha, zulu)):
            api(context, "/customers", {"name": name, "email": f"list_{uuid.uuid4().hex}_{index}@brightloop.test"})
        page.goto(f"{WEB}/app/customers")
        search = page.get_by_placeholder("Search by name, company, or email...")
        search.fill(prefix)
        expect(page.locator("tbody tr")).to_have_count(2)
        page.get_by_role("combobox", name="Sort by", exact=True).select_option("name")
        page.get_by_role("checkbox", name="Descending", exact=True).uncheck()
        expect(page.locator("tbody tr").first.get_by_role("link", name=alpha, exact=True)).to_be_visible()
        page.get_by_role("link", name=alpha, exact=True).click()
        expect(page.get_by_role("heading", name=alpha, exact=True)).to_be_visible()
        page.go_back()
        expect(search).to_have_value(prefix)
        expect(page.get_by_role("combobox", name="Sort by", exact=True)).to_have_value("name")
        expect(page.get_by_role("checkbox", name="Descending", exact=True)).not_to_be_checked()
        expect(page.locator("tbody tr").first.get_by_role("link", name=alpha, exact=True)).to_be_visible()
        print("PASS: SQL customer ordering and filters survive detail/back navigation")

        held = []
        def delay_old(route):
            value = parse_qs(urlparse(route.request.url).query).get("search", [""])[0]
            if value == alpha and not held:
                held.append((route, route.fetch()))
            else:
                route.continue_()
        page.route("**/api/v1/customers?**", delay_old)
        search.fill(alpha)
        for _ in range(100):
            if held:
                break
            page.wait_for_timeout(20)
        assert held, "The old request was not intercepted."
        search.fill(zulu)
        expect(page.get_by_role("link", name=zulu, exact=True)).to_be_visible()
        held[0][0].fulfill(response=held[0][1])
        page.wait_for_timeout(200)
        expect(page.locator("tbody")).not_to_contain_text(alpha)
        expect(page.get_by_role("link", name=zulu, exact=True)).to_be_visible()
        page.unroute("**/api/v1/customers?**")
        page.reload()
        expect(search).to_have_value(zulu)
        expect(page.locator("tbody tr")).to_have_count(1)
        print("PASS: Delayed old response cannot replace newer results; reload restores the selected view")

        payment = context.request.get(f"{API}/payments?page_size=1").json()["items"][0]
        page.goto(f"{WEB}/app/payments")
        ledger_search = page.get_by_label("Invoice / reference search", exact=True)
        ledger_search.fill(payment["invoice_number"])
        page.get_by_role("combobox", name="Payment method filter", exact=True).select_option(payment["method"])
        page.get_by_role("link", name=payment["invoice_number"], exact=True).first.click()
        expect(page.get_by_role("heading", name=payment["invoice_number"], exact=True)).to_be_visible()
        page.go_back()
        expect(ledger_search).to_have_value(payment["invoice_number"])
        expect(page.get_by_role("combobox", name="Payment method filter", exact=True)).to_have_value(payment["method"])
        print("PASS: Payment method/search survive invoice source navigation")

        invoice = context.request.get(f"{API}/invoices/{payment['invoice_id']}").json()
        page.goto(f"{WEB}/app/invoices")
        page.get_by_label("Search", exact=True).fill(invoice["number"])
        page.get_by_role("combobox", name="Invoice status", exact=True).select_option(invoice["state"])
        page.get_by_role("combobox", name="Invoice sort", exact=True).select_option("due_date")
        page.get_by_role("checkbox", name="Descending", exact=True).uncheck()
        page.get_by_label("Issued from", exact=True).fill(invoice["invoice_date"])
        page.get_by_label("Issued through", exact=True).fill(invoice["invoice_date"])
        page.get_by_role("link", name=invoice["number"], exact=True).click()
        expect(page.get_by_role("heading", name=invoice["number"], exact=True)).to_be_visible()
        page.go_back()
        page.reload()
        expect(page.get_by_label("Search", exact=True)).to_have_value(invoice["number"])
        expect(page.get_by_role("combobox", name="Invoice status", exact=True)).to_have_value(invoice["state"])
        expect(page.get_by_role("combobox", name="Invoice sort", exact=True)).to_have_value("due_date")
        expect(page.get_by_label("Issued from", exact=True)).to_have_value(invoice["invoice_date"])
        expect(page.get_by_role("checkbox", name="Descending", exact=True)).not_to_be_checked()
        expect(page.get_by_role("link", name=invoice["number"], exact=True)).to_be_visible()
        assert not errors, errors
        print("PASS: Invoice status/date/order filters survive detail/back/reload without script errors")
        browser.close()
    print("Collection browser journeys: 5 passed, 0 skipped.")


if __name__ == "__main__":
    run()
