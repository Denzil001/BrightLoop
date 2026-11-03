"""Real PostgreSQL-backed admin choices beyond the first 100 records.

Reuses explicitly named synthetic catalog fixtures; never creates financial data.
"""
import re
import uuid

from playwright.sync_api import expect, sync_playwright
from test_subscription_journeys import API, WEB, api, login


def records(context, endpoint, prefix, values):
    existing = {}
    page = 1
    while True:
        response = context.request.get(f"{API}{endpoint}", params={"search": prefix, "page_size": 100, "page": page})
        assert response.ok, response.text()
        result = response.json()
        existing.update({item["name"]: item for item in result["items"]})
        if page * 100 >= result["total"]:
            break
        page += 1
    for index in range(105):
        name = f"{prefix} {index:03d}"
        if name not in existing:
            existing[name] = api(context, endpoint, {"name": name, **values})
    return [existing[f"{prefix} {index:03d}"] for index in range(105)]


def patch(context, endpoint, payload):
    csrf = next(cookie["value"] for cookie in context.cookies() if cookie["name"] == "brightloop_csrf")
    result = context.request.patch(f"{API}{endpoint}", data=payload, headers={"X-CSRF-Token": csrf, "Origin": WEB})
    assert result.ok, result.text()


def save(page, label, endpoint):
    with page.expect_response(lambda response: response.url == f"{API}{endpoint}" and response.request.method == "PATCH") as saved:
        page.get_by_role("button", name=label, exact=True).click()
    assert saved.value.ok, saved.value.text()


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("dialog", lambda dialog: dialog.accept())
        login(page, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        products = records(context, "/products", "Selector QA product", {"type": "ADDON", "sales_price": "10.00", "cost_price": "1.00"})
        taxes = records(context, "/taxes", "Selector QA tax", {"classification": "QA", "rate": "3.00"})
        plans = records(context, "/plans", "Selector QA plan", {"interval": "MONTHLY", "base_fee": "100.00", "minimum_seats": 1})
        product, tax, plan = products[-1], taxes[-1], plans[-1]
        patch(context, f"/products/{product['id']}", {"tax_rule_ids": [tax["id"]]})
        patch(context, f"/plans/{plan['id']}", {"items": [], "tax_rule_ids": [tax["id"]]})
        for endpoint, target in (("products", product), ("taxes", tax), ("plans", plan)):
            first = context.request.get(f"{API}/{endpoint}?sort=name&descending=false&page_size=100").json()
            assert target["id"] not in {item["id"] for item in first["items"]}, endpoint

        page.goto(f"{WEB}/app/products/{product['id']}")
        selected_tax = page.get_by_role("checkbox", name=re.compile(re.escape(tax["name"])))
        expect(selected_tax).to_be_checked()
        page.get_by_label("Find tax rule", exact=True).fill(taxes[0]["name"])
        expect(page.get_by_role("checkbox", name=re.compile(re.escape(taxes[0]["name"])))) .to_be_visible()
        expect(selected_tax).to_be_checked()
        save(page, "Save Product Details", f"/products/{product['id']}")
        expect(selected_tax).to_be_checked()
        print("PASS: Product tax assignments beyond 100 hydrate and survive search/save")
        tax_search = page.get_by_label("Find tax rule", exact=True)
        tax_search.fill("Selector QA tax")
        expect(page.get_by_role("checkbox", name=re.compile(re.escape(taxes[49]["name"])))) .to_be_visible()
        expect(page.get_by_role("checkbox", name=re.compile(re.escape(taxes[103]["name"])))) .to_have_count(0)
        page.get_by_role("button", name="Load more choices", exact=True).click()
        expect(page.get_by_role("checkbox", name=re.compile(re.escape(taxes[99]["name"])))) .to_be_visible()
        page.get_by_role("button", name="Load more choices", exact=True).click()
        expect(page.get_by_role("checkbox", name=re.compile(re.escape(taxes[103]["name"])))) .to_be_visible()
        expect(selected_tax).to_be_checked()
        page.route("**/api/v1/taxes?**", lambda route: route.fulfill(status=503, json={"error": {"code": "UNAVAILABLE", "message": "Temporary lookup failure"}}))
        tax_search.fill("Retry lookup")
        expect(page.get_by_text("Temporary lookup failure", exact=False)).to_be_visible()
        expect(selected_tax).to_be_checked()
        page.unroute("**/api/v1/taxes?**")
        page.get_by_role("button", name="Retry choices", exact=True).click()
        expect(page.get_by_text("Temporary lookup failure", exact=False)).to_have_count(0)
        expect(selected_tax).to_be_checked()
        print("PASS: Choice pagination reaches the third page; lookup failure/retry preserves selections")

        page.goto(f"{WEB}/app/plans/{plan['id']}")
        expect(page.get_by_role("checkbox", name=re.compile(re.escape(tax["name"])))) .to_be_checked()
        page.get_by_role("button", name="Add Included Product", exact=True).click()
        page.get_by_label("Find bundle product", exact=True).fill(product["name"])
        bundle = page.get_by_role("combobox", name="Bundle product", exact=True)
        expect(bundle.locator(f"option[value='{product['id']}']")).to_have_count(1)
        bundle.select_option(product["id"])
        page.get_by_label("Find bundle product", exact=True).fill("No such selector product")
        expect(bundle.locator("option:checked")).to_contain_text(product["name"])
        page.get_by_role("button", name="Add to Plan", exact=True).click()
        save(page, "Save Plan Configuration", f"/plans/{plan['id']}")
        expect(page.get_by_text(product["name"], exact=True)).to_be_visible()
        persisted = context.request.get(f"{API}/plans/{plan['id']}").json()
        assert persisted["items"][0]["product_id"] == product["id"]
        assert persisted["tax_rule_ids"] == [tax["id"]]
        print("PASS: Plan bundle search retains selected product and persists bundle/tax IDs")

        template = api(context, "/quotation-templates", {"name": f"Selector QA template {uuid.uuid4().hex[:8]}", "plan_id": plan["id"], "active": False, "lines": []})
        page.goto(f"{WEB}/app/quotation-templates/{template['id']}")
        template_plan = page.get_by_role("combobox", name="Template base plan", exact=True)
        expect(template_plan.locator("option:checked")).to_contain_text(plan["name"])
        page.get_by_label("Find template plan", exact=True).fill(plans[0]["name"])
        expect(template_plan.locator(f"option[value='{plans[0]['id']}']")).to_have_count(1)
        expect(template_plan.locator("option:checked")).to_contain_text(plan["name"])
        page.get_by_role("button", name="Add Template Line", exact=True).click()
        page.get_by_label("Find template product", exact=True).fill(product["name"])
        template_product = page.get_by_role("combobox", name="Template product", exact=True)
        expect(template_product.locator(f"option[value='{product['id']}']")).to_have_count(1)
        template_product.select_option(product["id"])
        page.get_by_label("Find template product", exact=True).fill("No matching item")
        expect(template_product.locator("option:checked")).to_contain_text(product["name"])
        page.get_by_role("button", name="Add Line", exact=True).click()
        save(page, "Save Template", f"/quotation-templates/{template['id']}")
        saved = context.request.get(f"{API}/quotation-templates/{template['id']}").json()
        assert saved["plan_id"] == plan["id"] and saved["lines"][0]["product_id"] == product["id"]
        print("PASS: Template plan/product choices beyond 100 retain selection and save correctly")

        page.goto(f"{WEB}/app/quotation-templates")
        page.get_by_role("button", name="New Template", exact=True).click()
        page.get_by_label("Find template plan", exact=True).fill(plan["name"])
        create_plan = page.get_by_role("combobox", name="Template base plan", exact=True)
        expect(create_plan.locator(f"option[value='{plan['id']}']")).to_have_count(1)
        create_plan.select_option(plan["id"])
        page.get_by_label("Find template plan", exact=True).fill("Nothing matches")
        expect(create_plan.locator("option:checked")).to_have_text(plan["name"])
        print("PASS: New template metadata can choose and retain a plan beyond the initial page")

        page.goto(f"{WEB}/app/discounts")
        page.get_by_role("button", name="New Discount Rule", exact=True).click()
        page.get_by_role("combobox", name="Discount scope", exact=True).select_option("PRODUCT")
        search = page.get_by_label("Find eligible product", exact=True)
        search.fill(product["name"])
        eligible = page.get_by_role("checkbox", name=product["name"], exact=True)
        eligible.check()
        search.fill("No matching eligible product")
        expect(eligible).to_be_checked()
        assert not errors, errors
        print("PASS: Product-scoped discount retains checked eligibility through search without script errors")
        browser.close()
    print("Admin choice journeys: 6 passed, 0 skipped.")


if __name__ == "__main__":
    run()
