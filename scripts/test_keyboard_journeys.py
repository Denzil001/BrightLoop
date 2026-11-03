"""Native dialog focus/Escape and same-document dirty browser Back checks."""
from pathlib import Path
import re

from playwright.sync_api import expect, sync_playwright
from test_subscription_journeys import API, WEB, login

ROOT = Path(__file__).resolve().parents[1]


def run():
    scans = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, bypass_csp=True)
        page = context.new_page()
        login(page, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        cases = [
            ("products", "New Product", "Create New Product", "e.g. Cloud Server Hosting"),
            ("plans", "New Plan", "Create New Subscription Plan", "e.g. Standard Business Plan"),
            ("taxes", "New Tax Rule", "Create New Tax Rule", "e.g. Standard GST 18%"),
            ("discounts", "New Discount Rule", "Create New Discount Rule", "e.g. Annual Subscription 10% Off"),
            ("quotation-templates", "New Template", "Create Quotation Template", "e.g. Standard SaaS Onboarding"),
            ("staff", "Provision Staff", "Provision Staff Account", "Staff member full name"),
        ]
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 1000})
            for resource, button, title, placeholder in cases:
                page.goto(f"{WEB}/app/{resource}")
                opener = page.get_by_role("button", name=button, exact=True)
                opener.click()
                dialog = page.get_by_role("dialog", name=title, exact=True)
                expect(dialog).to_be_visible()
                count = dialog.locator("input:not([type=hidden]),select,textarea,button").count()
                for key in ("Tab", "Shift+Tab"):
                    for _ in range(count + 2):
                        page.keyboard.press(key)
                        assert page.evaluate("!!document.activeElement.closest('dialog[open]')"), (resource, width, key)
                field = dialog.get_by_placeholder(placeholder, exact=True)
                field.fill("Keyboard draft")
                page.once("dialog", lambda prompt: prompt.dismiss())
                page.keyboard.press("Escape")
                expect(field).to_have_value("Keyboard draft")
                page.add_script_tag(path=str(ROOT / "frontend/node_modules/axe-core/axe.min.js"))
                violations = page.evaluate("""async () => (await axe.run(document, {runOnly: {type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(rule=>({id:rule.id,targets:rule.nodes.map(node=>node.target)}))""")
                scans.append({"resource": resource, "width": width, "violations": violations})
                page.once("dialog", lambda prompt: prompt.accept())
                page.keyboard.press("Escape")
                expect(dialog).to_have_count(0)
                expect(opener).to_be_focused()
        print("PASS: Twelve desktop/mobile dialogs contain focus, guard dirty Escape and restore trigger focus")

        page.set_viewport_size({"width": 1440, "height": 1000})
        page.goto(f"{WEB}/app/products")
        search = page.get_by_placeholder("Search products by name or type...", exact=True)
        search.fill("Selector QA product 104")
        page.get_by_role("link", name="Manage", exact=True).click()
        field = page.get_by_label("Product Name", exact=True)
        expect(field).to_have_value("Selector QA product 104")
        field.fill("Keyboard history draft")
        current = page.url
        prompts = []
        page.once("dialog", lambda prompt: (prompts.append(prompt.message), prompt.dismiss()))
        page.evaluate("history.back()")
        for _ in range(100):
            if prompts:
                break
            page.wait_for_timeout(20)
        assert len(prompts) == 1 and "unsaved changes" in prompts[0], prompts
        assert page.url == current
        expect(field).to_have_value("Keyboard history draft")
        page.once("dialog", lambda prompt: prompt.accept())
        page.evaluate("history.back()")
        page.wait_for_url(re.compile(r"/app/products\?"))
        expect(search).to_have_value("Selector QA product 104")
        page.evaluate("history.forward()")
        page.wait_for_url(current)
        expect(field).to_have_value("Selector QA product 104")
        print("PASS: Dirty browser Back stays on cancel, discards on acceptance and forward loads persisted fields")
        result = context.request.get(f"{API}/health")
        assert result.ok
        context.close()
        browser.close()
    import json
    output = ROOT / "test-results/dialog-accessibility.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(scans, indent=2), encoding="utf-8")
    assert not any(item["violations"] for item in scans), "Inspect test-results/dialog-accessibility.json"
    print("PASS: Twelve opened dialogs have no automated WCAG A/AA violations")
    print("Keyboard journeys: 3 passed, 0 skipped.")


if __name__ == "__main__":
    run()
