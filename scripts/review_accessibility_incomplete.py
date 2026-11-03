"""Resolve the known glyph/scroll-clipping contrast checks using rendered DOM.

Fails on an unrecognized case; does not suppress axe rules or change its report.
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from test_subscription_journeys import API, WEB, login

ROOT = Path(__file__).resolve().parents[1]


def run():
    reports = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        admin = browser.new_context(bypass_csp=True)
        login(admin.new_page(), "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        customer = admin.request.get(f"{API}/customers?search=payment_&page_size=1").json()["items"][0]
        staff = admin.request.get(f"{API}/staff?search=payment_staff_&page_size=1").json()["items"][0]
        subscription = admin.request.get(f"{API}/subscriptions?customer_id={customer['id']}&page_size=1").json()["items"][0]
        product = admin.request.get(f"{API}/products?search=Selector%20QA%20product%20104").json()["items"][0]
        contexts = {"admin": admin, "public": browser.new_context(bypass_csp=True)}
        for role, email, password, landing in (("customer", customer["email"], "Customer@Secure123", "/portal"),
                                               ("staff", staff["email"], "Staff@Secure123", "/app")):
            contexts[role] = browser.new_context(bypass_csp=True)
            login(contexts[role].new_page(), email, password, landing)
        cases = [(code, width, path, "public") for width in (1440, 390) for code, path in
                 (("P02", "/register"), ("P04", "/reset-password?token=synthetic-audit-form-mode"))]
        cases += [("I06", 390, f"/app/subscriptions/{subscription['id']}", "admin"),
                  ("staff:I06", 390, f"/app/subscriptions/{subscription['id']}", "staff"),
                  ("C03", 390, f"/portal/subscriptions/{subscription['id']}", "customer"),
                  ("A03", 390, f"/app/products/{product['id']}", "admin")]
        for code, width, path, role in cases:
            page = contexts[role].new_page()
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(WEB + path)
            page.wait_for_load_state("networkidle")
            page.add_script_tag(path=str(ROOT / "frontend/node_modules/axe-core/axe.min.js"))
            result = page.evaluate("""async () => {
              const scan = await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});
              const color = text => {const values = text.match(/[\\d.]+/g)?.map(Number); if (!values || values.length < 3) throw Error('Unknown color'); return [...values.slice(0,3),values[3] ?? 1];};
              const luminance = values => values.slice(0,3).map(value=>{value/=255;return value<=0.04045?value/12.92:((value+0.055)/1.055)**2.4;}).reduce((sum,value,index)=>sum+value*[0.2126,0.7152,0.0722][index],0);
              const checks = [];
              for (const rule of scan.incomplete) for (const node of rule.nodes) {
                if(rule.id!=='color-contrast'||node.target.length!==1) throw Error('Unrecognized incomplete rule');
                const element = document.querySelector(node.target[0]);
                if(!element) throw Error('Missing incomplete target');
                const glyph = /^[○✓]$/.test(element.textContent.trim()) && !!element.closest('li');
                const region = element.closest('.overflow-x-auto');
                const rect=element.getBoundingClientRect(), bounds=region?.getBoundingClientRect();
                const clipped = !!region && region.tabIndex>=0 && region.scrollWidth>region.clientWidth && (rect.right>bounds.right||rect.left<bounds.left);
                if(!glyph&&!clipped) throw Error('Incomplete target needs further review');
                const foreground=color(getComputedStyle(element).color);
                let ancestor=element, background=null;
                while(ancestor) {const candidate=color(getComputedStyle(ancestor).backgroundColor);if(candidate[3]>0){background=candidate;break;}ancestor=ancestor.parentElement;}
                background ||= [255,255,255,1];
                if(foreground[3]!==1||background[3]!==1) throw Error('Translucent color needs review');
                const first=luminance(foreground), second=luminance(background), contrast=(Math.max(first,second)+0.05)/(Math.min(first,second)+0.05);
                const required=4.5;
                if(contrast<required) throw Error('Rendered contrast is insufficient');
                checks.push({kind:glyph?'status glyph':'clipped scrollable table',target:node.target,contrast,required,foreground,background});
              }
              return {violations:scan.violations.map(rule=>rule.id),checks};
            }""")
            assert not result["violations"], result["violations"]
            if code.endswith("I06") or code in ("C03", "A03"):
                region = page.get_by_role("region", name="Scrollable table", exact=True).first
                region.focus()
                before = region.evaluate("element=>element.scrollLeft")
                for _ in range(12):
                    page.keyboard.press("ArrowRight")
                page.wait_for_function("element=>element.scrollLeft>0", arg=region.element_handle())
                assert region.evaluate("element=>element.scrollLeft") > before
                result["keyboard_scroll"] = True
                region.evaluate("element=>{element.scrollLeft=element.scrollWidth-element.clientWidth;}")
                if role == "admin":
                    region.screenshot(path=str(ROOT / f"test-results/accessibility-review-{code}.png"))
            elif code == "P02" and width == 390:
                page.get_by_text("Password requirements:", exact=True).locator("..").screenshot(path=str(ROOT / "test-results/accessibility-review-password.png"))
            reports.append({"page": code, "width": width, "role": role, **result})
            print(f"PASS: {code} {width} classified {len(result['checks'])} contrast targets", flush=True)
            page.close()
        browser.close()
    (ROOT / "test-results/accessibility-incomplete-review.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print("Incomplete review: 8 observations passed; no axe rules disabled.")


if __name__ == "__main__":
    run()
