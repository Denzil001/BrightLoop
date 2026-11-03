"""Automated WCAG A/AA checks for all planned role/page variants, desktop/mobile.

Requires the local production app and synthetic payment/catalog browser fixtures.
An automated scan complements the separate keyboard and workflow checks.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import re

from playwright.sync_api import sync_playwright
from test_subscription_journeys import API, WEB, login

ROOT = Path(__file__).resolve().parents[1]


def get(context, path):
    result = context.request.get(f"{API}{path}")
    assert result.ok, f"Fixture lookup failed: {path} ({result.status})"
    return result.json()


def run():
    reports = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        browser_version = browser.version
        admin = browser.new_context()
        page = admin.new_page()
        login(page, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        customer = get(admin, "/customers?search=payment_&page_size=1")["items"][0]
        staff = get(admin, "/staff?search=payment_staff_&page_size=1")["items"][0]
        customer_context = browser.new_context()
        login(customer_context.new_page(), customer["email"], "Customer@Secure123", "/portal")
        subscription = get(customer_context, "/subscriptions?page_size=1")["items"][0]
        invoice = get(customer_context, f"/invoices?subscription_id={subscription['id']}&page_size=1")["items"][0]
        values = {"customerId": customer["id"], "subscriptionId": subscription["id"], "invoiceId": invoice["id"]}
        for parameter, endpoint, query in (("productId", "products", "Selector QA product 104"),
                                           ("planId", "plans", "Selector QA plan 104"),
                                           ("templateId", "quotation-templates", "Selector QA template")):
            values[parameter] = get(admin, f"/{endpoint}?search={query}&page_size=1")["items"][0]["id"]
        staff_context = browser.new_context()
        login(staff_context.new_page(), staff["email"], "Staff@Secure123", "/app")
        states = {"admin": admin.storage_state(), "staff": staff_context.storage_state(),
                  "customer": customer_context.storage_state(), "public": {"cookies": [], "origins": []}}
        rows = re.findall(r"\| ([PIAC]\d{2}) \| `([^`]+)`", (ROOT / "BUILD_GUIDE.md").read_text(encoding="utf-8"))
        assert len(rows) == 32
        planned = {path for _, path in rows}
        actual = {"/" + path.parent.relative_to(ROOT / "frontend/src/app").as_posix()
                  for path in (ROOT / "frontend/src/app").rglob("page.tsx")}
        actual.discard("/.")
        assert actual == planned, {"missing": sorted(planned - actual), "extra": sorted(actual - planned)}
        cases = []
        for code, path in rows:
            for key, value in values.items():
                path = path.replace(f"[{key}]", value)
            assert "[" not in path
            if code == "P04":
                path += "?token=synthetic-audit-form-mode"
            role = "public" if code.startswith("P") else "customer" if code.startswith("C") else "admin"
            cases.append((code, path, role))
            if code.startswith("I"):
                cases.append((f"staff:{code}", path, "staff"))
        for width in (1440, 390):
            for role, state in states.items():
                # Axe is test-only instrumentation; this is not a CSP/security test.
                context = browser.new_context(storage_state=state, viewport={"width": width, "height": 1000}, bypass_csp=True)
                page = context.new_page()
                for code, path, required_role in cases:
                    if required_role != role:
                        continue
                    response = page.goto(WEB + path)
                    assert response and response.ok, (code, response.status if response else None)
                    page.wait_for_function("""() => document.querySelector('h1,h2') && !/Loading[^\\n]*|Authenticating session|Opening your workspace/i.test(document.body.innerText)""")
                    page.wait_for_load_state("networkidle")
                    page.add_script_tag(path=str(ROOT / "frontend/node_modules/axe-core/axe.min.js"))
                    result = page.evaluate("""async () => {
                      const result = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa']}});
                      return {violations: result.violations.map(rule => ({id: rule.id, impact: rule.impact, description: rule.description,
                        nodes: rule.nodes.map(node => ({target: node.target, summary: node.failureSummary}))})), incomplete: result.incomplete.length,
                        incomplete_details: result.incomplete.map(rule => ({id: rule.id, nodes: rule.nodes.map(node => ({target: node.target, summary: node.failureSummary}))}))};
                    }""")
                    overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
                    reports.append({"page": code, "role": role, "width": width, "overflow": overflow, **result})
                    print(f"{code} {width}: {len(result['violations'])} rule violations; overflow={overflow}", flush=True)
                context.close()
        browser.close()
    output = ROOT / "test-results/accessibility-audit.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({"axe_version": "4.14.0", "browser_version": browser_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "build_id": (ROOT / "frontend/.next/BUILD_ID").read_text().strip(), "observations": reports}, indent=2), encoding="utf-8")
    violations = sum(len(report["violations"]) for report in reports)
    overflow = sum(report["overflow"] for report in reports)
    print(f"Accessibility audit: {len(reports)} observations, {violations} rule violations, {overflow} overflows.")
    assert len(reports) == 84
    assert violations == overflow == 0, "Inspect test-results/accessibility-audit.json"


if __name__ == "__main__":
    run()
