"""Staff lifecycle browser journeys with genuine, bounded historical fixtures.

Run from the repository root against the documented local development services.
Only synthetic .test customer records are created. Historical dates are patched
in this fixture process, never in the running API; no future billing is invoked.
"""
from datetime import datetime, time, timedelta
from pathlib import Path
import re
import sys
from unittest.mock import patch
import uuid
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright
from test_subscription_journeys import API, WEB, api, login

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import app.models  # noqa: E402,F401 — register all mapped relationships
from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.users import User
from app.schemas.subscriptions import LifecycleIntent, SubscriptionCommand, SubscriptionDraft
from app.services.billing import process_next_period
from app.services.lifecycle import schedule_intent
from app.services.subscriptions import create_draft, execute_command


def historical_subscription(actor_id, customer_id, plan_id, start, expiry, pause=None):
    now = datetime.combine(start, time.min, ZoneInfo("Asia/Kolkata"))
    with SessionLocal() as db:
        assert db.execute(text("SELECT current_database(), current_schema()")).one() == ("brightloop_dev", "public")
        actor = db.get(User, uuid.UUID(actor_id))
        assert actor.email_normalized.endswith("@brightloop.test") and actor.role == "STAFF"
        with patch("app.services.subscriptions.get_business_today", return_value=start), \
                patch("app.services.subscriptions.get_business_now", return_value=now):
            sub = create_draft(db, SubscriptionDraft(customer_id=customer_id, plan_id=plan_id,
                seat_quantity=1, start_date=start, expiry_date=expiry, lines=[]), actor)
            for action in ("ISSUE", "CONFIRM", "ACTIVATE"):
                execute_command(db, sub, SubscriptionCommand(action=action,
                    expected_version=sub.version, request_key=uuid.uuid4().hex), actor)
        sub_id = sub.id
        if pause:
            approval = pause - timedelta(days=1)
            with patch("app.services.lifecycle.get_business_today", return_value=approval), \
                    patch("app.services.lifecycle.get_business_now", return_value=datetime.combine(approval, time.min, ZoneInfo("Asia/Kolkata"))):
                schedule_intent(db, sub, LifecycleIntent(action="PAUSE", effective_date=pause,
                    reason="Synthetic historical travel pause"), actor)
        db.commit()
    # Process each historical period in its own real transaction, just like CLI.
    for _ in range(40):
        with SessionLocal() as db:
            result = process_next_period(db, sub_id, pause or datetime.now(ZoneInfo("Asia/Kolkata")).date(), actor_id=uuid.UUID(actor_id))
            db.commit()
            if result.state != "CREATED":
                return str(sub_id)
    raise AssertionError("Synthetic historical fixture exceeded its bounded period count")


def get(context, path):
    response = context.request.get(f"{API}{path}", max_retries=2)
    assert response.ok, f"GET {path}: {response.status}"
    return response.json()


def patch_api(context, path, payload):
    csrf = next(c["value"] for c in context.cookies() if c["name"] == "brightloop_csrf")
    response = context.request.patch(f"{API}{path}", data=payload,
        headers={"X-CSRF-Token": csrf, "Origin": WEB})
    assert response.ok, f"PATCH {path}: {response.status} {response.text()}"
    return response.json()


def invoices(context, sub_id):
    items = get(context, f"/invoices?subscription_id={sub_id}&page_size=100")["items"]
    return {i["id"]: get(context, f"/invoices/{i['id']}") for i in items}


def preserved(context, sub_id, before, added):
    after = invoices(context, sub_id)
    assert len(after) == len(before) + added
    for invoice_id, original in before.items():
        assert after[invoice_id] == original, "An existing invoice snapshot changed"
    identities = [i["period_start"] for i in after.values()]
    assert len(identities) == len(set(identities)), "Duplicate billing period"
    return after


def reconcile(context, sub_id, today, created):
    run = api(context, "/billing-runs", {"as_of_date": today.isoformat(), "subscription_id": sub_id})
    assert run["state"] == "COMPLETED" and run["summary"]["created"] == created
    assert run["summary"]["failed"] == 0


def begin(page, sub_id, action, reason):
    page.goto(f"{WEB}/app/subscriptions/{sub_id}")
    page.get_by_role("combobox", name="Action", exact=True).select_option(action)
    page.get_by_role("textbox", name="Reason / note", exact=True).fill(reason)


def schedule(page, date):
    page.get_by_label("Effective date", exact=True).fill(date.isoformat())
    page.get_by_role("button", name="Schedule change", exact=True).click()


def pending(page):
    expect(page.get_by_text("A scheduled change is awaiting its effective date.", exact=True)).to_be_visible()


def run():
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    tomorrow = today + timedelta(days=1)
    suffix = uuid.uuid4().hex[:8]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        admin_context = browser.new_context()
        admin = admin_context.new_page()
        login(admin, "admin_bootstrap@brightloop.test", "Admin@Secure123", "/app")
        email = f"lifecycle_{suffix}@brightloop.test"
        customer_context = browser.new_context()
        api(customer_context, "/auth/register", {"name": f"Lifecycle customer {suffix}", "email": email, "password": "Customer@Secure123"})
        customer_id = get(admin_context, f"/customers?search={email}")["items"][0]["id"]
        staff_email = f"lifecycle_staff_{suffix}@brightloop.test"
        staff = api(admin_context, "/staff", {"name": f"Lifecycle staff {suffix}", "email": staff_email, "initial_password": "Staff@Secure123"})
        plan = api(admin_context, "/plans", {"name": f"Lifecycle daily {suffix}", "base_fee": "100.00", "minimum_seats": 1,
            "extra_seat_unit_price": "10.00", "interval": "DAILY"})
        product = api(admin_context, "/products", {"name": f"Lifecycle add-on {suffix}", "type": "ADDON", "sales_price": "25.00", "cost_price": "0.00"})
        staff_context = browser.new_context()
        page = staff_context.new_page()
        page.on("dialog", lambda dialog: dialog.accept())
        login(page, staff_email, "Staff@Secure123", "/app")

        paused_id = historical_subscription(staff["id"], customer_id, plan["id"], today - timedelta(days=5), today + timedelta(days=10), pause=today - timedelta(days=2))
        old = invoices(admin_context, paused_id)
        assert len(old) == 3 and get(staff_context, f"/subscriptions/{paused_id}")["state"] == "PAUSED"
        begin(page, paused_id, "RESUME", "Returned from historical travel")
        schedule(page, today)
        pending(page)
        assert get(staff_context, f"/subscriptions/{paused_id}")["state"] == "PAUSED"
        reconcile(admin_context, paused_id, today, 1)
        resumed = get(staff_context, f"/subscriptions/{paused_id}")
        assert resumed["state"] == "ACTIVE" and resumed["next_billing_date"] == tomorrow.isoformat()
        assert resumed["terms"][0]["expiry_date"] == (today + timedelta(days=12)).isoformat()
        preserved(admin_context, paused_id, old, 1)
        begin(page, paused_id, "PAUSE", "Next daily boundary pause")
        schedule(page, tomorrow)
        pending(page)
        assert get(staff_context, f"/subscriptions/{paused_id}")["state"] == "ACTIVE"
        reconcile(admin_context, paused_id, today, 0)
        preserved(admin_context, paused_id, old, 1)
        print("PASS: Staff resume extends expiry exactly, restarts anchor, and future pause remains pending; old invoices unchanged")

        addon_id = historical_subscription(staff["id"], customer_id, plan["id"], today, today + timedelta(days=14))
        old = invoices(admin_context, addon_id)
        patch_api(admin_context, f"/plans/{plan['id']}", {"allow_pause": False})
        begin(page, addon_id, "ADDON_CHANGE", "Two add-ons and three seats next boundary")
        retained = page.get_by_role("region", name="Existing term policies retained", exact=True)
        expect(retained.get_by_text("Pause:", exact=True).locator("..")).to_have_text("Pause:Allowed")
        page.get_by_label("Service start", exact=True).fill(tomorrow.isoformat())
        page.get_by_label("Seat quantity", exact=True).fill("3")
        page.get_by_label("Find product", exact=True).fill(product["name"])
        page.get_by_role("button", name="Add product", exact=True).click()
        page.get_by_role("combobox", name="Product", exact=True).select_option(product["id"])
        page.get_by_label("Quantity", exact=True).fill("2")
        page.get_by_role("button", name="Preview pricing", exact=True).click()
        expect(page.get_by_text("Estimated total ₹170.00", exact=True)).to_be_visible()
        page.get_by_label("Service expiry (exclusive)", exact=True).fill((today + timedelta(days=15)).isoformat())
        page.get_by_role("button", name="Accept & schedule change", exact=True).click()
        expect(page.get_by_role("alert").filter(has_text="cannot change the term expiry")).to_be_visible()
        expect(page.get_by_role("textbox", name="Reason / note", exact=True)).to_have_value("Two add-ons and three seats next boundary")
        page.get_by_label("Service expiry (exclusive)", exact=True).fill((today + timedelta(days=14)).isoformat())
        page.get_by_role("button", name="Accept & schedule change", exact=True).click()
        pending(page)
        changed = get(staff_context, f"/subscriptions/{addon_id}")
        assert changed["seat_quantity"] == 1
        current = next(a for a in changed["agreements"] if not a["pending_change"] and a["state"] == "ACCEPTED")
        assert current["pricing_estimate"]["total"] == "100.00"
        assert changed["agreements"][0]["pricing_estimate"]["total"] == "170.00"
        assert changed["agreements"][0]["pending_change"]
        assert changed["agreements"][0]["policies"]["allow_pause"] is True
        reconcile(admin_context, addon_id, today, 0)
        preserved(admin_context, addon_id, old, 0)
        print("PASS: Add-on preview, expiry validation and preserved inputs; future seats/prices do not alter current agreement/invoice")

        # The historical renewal fixture predates the later policy revision.
        patch_api(admin_context, f"/plans/{plan['id']}", {"allow_pause": True})
        renewal_id = historical_subscription(staff["id"], customer_id, plan["id"], today - timedelta(days=5), today - timedelta(days=1))
        old = invoices(admin_context, renewal_id)
        assert len(old) == 4 and get(staff_context, f"/subscriptions/{renewal_id}")["state"] == "CLOSED"
        patch_api(admin_context, f"/plans/{plan['id']}", {"base_fee": "150.00", "allow_pause": False})
        begin(page, renewal_id, "RENEW", "New dated term with current plan price")
        proposed = page.get_by_role("region", name="Proposed term policies", exact=True)
        expect(proposed.get_by_text("Pause:", exact=True).locator("..")).to_have_text("Pause:Not allowed")
        page.get_by_label("Service start", exact=True).fill(today.isoformat())
        page.get_by_label("Service expiry (exclusive)", exact=True).fill((today + timedelta(days=30)).isoformat())
        page.get_by_label("Seat quantity", exact=True).fill("2")
        page.get_by_role("button", name="Preview pricing", exact=True).click()
        expect(page.get_by_text("Estimated total ₹160.00", exact=True)).to_be_visible()
        page.get_by_role("button", name="Accept & schedule change", exact=True).click()
        pending(page)
        assert get(staff_context, f"/subscriptions/{renewal_id}")["state"] == "CLOSED"
        reconcile(admin_context, renewal_id, today, 1)
        renewed = get(staff_context, f"/subscriptions/{renewal_id}")
        assert renewed["state"] == "ACTIVE" and renewed["seat_quantity"] == 2
        assert len(renewed["terms"]) == 2 and renewed["terms"][0]["policies"]["allow_pause"]
        assert not renewed["terms"][1]["policies"]["allow_pause"]
        after = preserved(admin_context, renewal_id, old, 1)
        assert next(i for key, i in after.items() if key not in old)["total"] == "160.00"
        page.reload()
        expect(page.get_by_role("combobox", name="Action", exact=True).locator("option[value='PAUSE']")).to_have_count(0)
        reconcile(admin_context, renewal_id, today, 0)
        preserved(admin_context, renewal_id, old, 1)
        print("PASS: Closed-term renewal adopts new price/policies, creates one dated term/invoice, preserves historical documents, safe replay")

        close_id = historical_subscription(staff["id"], customer_id, plan["id"], today, today + timedelta(days=14))
        old = invoices(admin_context, close_id)
        begin(page, close_id, "EARLY_CLOSE", "Close at tomorrow's unbilled boundary")
        schedule(page, today)
        expect(page.get_by_role("alert").filter(has_text="future billing boundary")).to_be_visible()
        expect(page.get_by_role("textbox", name="Reason / note", exact=True)).to_have_value("Close at tomorrow's unbilled boundary")
        schedule(page, tomorrow)
        pending(page)
        closing = get(staff_context, f"/subscriptions/{close_id}")
        assert closing["state"] == "ACTIVE" and closing["terms"][0]["expiry_date"] == (today + timedelta(days=14)).isoformat()
        reconcile(admin_context, close_id, today, 0)
        preserved(admin_context, close_id, old, 0)
        customer = customer_context.new_page()
        login(customer, email, "Customer@Secure123", "/portal")
        customer.goto(f"{WEB}/portal/subscriptions/{renewal_id}")
        expect(customer.get_by_role("combobox", name="Action", exact=True).locator("option[value='EARLY_CLOSE']")).to_have_count(0)
        customer.set_viewport_size({"width": 390, "height": 844})
        assert customer.evaluate("document.documentElement.scrollWidth <= innerWidth")
        print("PASS: Closure rejects billed/current boundary, preserves reason, schedules future only; customer has no closure action")
        browser.close()
    print("Operational lifecycle journeys: 4 passed, 0 skipped.")


if __name__ == "__main__":
    run()
