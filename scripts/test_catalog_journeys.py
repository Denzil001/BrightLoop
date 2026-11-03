"""End-to-End browser journey test suite for Phase 3 Catalog, Pricing, and Templates (A02-A09)."""

import json
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path

# Add project root and backend directory to path
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

FRONTEND_URL = "http://localhost:3000"


def run_catalog_e2e_tests():
    print("Starting Playwright E2E Catalog & Templates Journey Tests (A02-A09)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context()
        page = context.new_page()

        # ----------------------------------------------------------------------
        # Setup: Sign in as Administrator
        # ----------------------------------------------------------------------
        print("\n--- Step 1: Sign in as Administrator ---")
        page.goto(f"{FRONTEND_URL}/login")
        page.fill("input#email", "admin_bootstrap@brightloop.test")
        page.fill("input#password", "Admin@Secure123")
        page.click("button[type='submit']")

        page.wait_for_url("**/app")
        print("PASS: Administrator signed in successfully")

        # ----------------------------------------------------------------------
        # Journey Step 2: A06 Tax Rules Management (/app/taxes)
        # ----------------------------------------------------------------------
        print("\n--- Step 2: A06 Tax Rules Management ---")
        tax_suffix = uuid.uuid4().hex[:6]
        tax_name = f"GST 18%_{tax_suffix}"

        page.goto(f"{FRONTEND_URL}/app/taxes")
        page.wait_for_selector("h1:has-text('Tax Rules')")

        page.click("button:has-text('New Tax Rule')")
        page.wait_for_selector("h2:has-text('Create New Tax Rule')")

        page.fill("input[placeholder='e.g. Standard GST 18%']", tax_name)
        page.fill("input[placeholder='e.g. GST, VAT, SALES_TAX']", "GST")
        page.fill("input[placeholder='18.0000']", "18.0000")
        page.click("button:has-text('Save Rule')")
        page.wait_for_selector("h2:has-text('Create New Tax Rule')", state="hidden")

        page.locator("input[placeholder^='Search']").first.fill(tax_name)

        # Verify tax rule appears in table
        page.wait_for_selector(f"span:has-text('{tax_name}')")
        tax_row = page.locator("tr", has_text=tax_name)
        assert "18%" in tax_row.text_content()
        print(f"PASS: Tax rule '{tax_name}' created and visible in table")

        # ----------------------------------------------------------------------
        # Journey Step 3: A02 & A03 Products and 560 Variant (/app/products)
        # ----------------------------------------------------------------------
        print("\n--- Step 3: A02 & A03 Products and Variant Price Adjustment ---")
        prod_suffix = uuid.uuid4().hex[:6]
        prod_name = f"Cloud Compute Pack_{prod_suffix}"

        page.goto(f"{FRONTEND_URL}/app/products")
        page.wait_for_selector("h1:has-text('Products Catalog')")

        page.click("button:has-text('New Product')")
        page.wait_for_selector("h2:has-text('Create New Product')")

        page.fill("input[placeholder='e.g. Cloud Server Hosting']", prod_name)
        page.fill("input[placeholder='e.g. INFRASTRUCTURE, ADDON, SERVICE']", "SERVER")
        page.fill("input[type='number'] >> nth=0", "200.00") # sales price
        page.fill("input[type='number'] >> nth=1", "80.00")  # cost price
        page.fill("textarea", "Internal dedicated host cluster")

        page.get_by_label("Find tax rule", exact=True).fill(tax_name)
        tax_checkbox = page.locator(f"label:has-text('{tax_name}') input[type='checkbox']")
        tax_checkbox.check()

        page.click("button:has-text('Create Product')")
        page.wait_for_selector("h2:has-text('Create New Product')", state="hidden")

        page.locator("input[placeholder^='Search']").first.fill(prod_name)

        # Verify product appears in catalog list
        page.wait_for_selector(f"span:has-text('{prod_name}')")
        print(f"PASS: Product '{prod_name}' created with base sales price ₹200.00")

        # Click Manage to open A03 Product Detail
        prod_row = page.locator("tr", has_text=prod_name)
        prod_row.locator("a:has-text('Manage')").click()

        page.wait_for_url("**/app/products/*")
        page.wait_for_selector(f"h1:has-text('{prod_name}')")
        print("PASS: Landed on A03 Product Detail page")

        # Add Variant with 560 adjustment
        page.click("button:has-text('Add Variant')")
        page.wait_for_selector("h2:has-text('Add Product Variant')")

        page.fill("input[placeholder='e.g. 24/7 Dedicated SOC / High Memory']", "High Memory 560")
        page.fill("input[placeholder='e.g. 560.00']", "560.00")

        # Check live calculation preview box
        page.wait_for_selector("span:has-text('₹760.00')")
        print("PASS: Live effective sales price preview calculated ₹760.00 (₹200 + ₹560)")

        page.click("button:has-text('Save Variant')")

        # Verify variant in variants table
        page.wait_for_selector("span:has-text('High Memory 560')")
        var_row = page.locator("tr", has_text="High Memory 560")
        assert "+₹560.00" in var_row.text_content()
        assert "₹760.00" in var_row.text_content()
        print("PASS: Variant 'High Memory 560' saved with +₹560.00 and ₹760.00 effective price")

        # ----------------------------------------------------------------------
        # Journey Step 4: A04 & A05 Plans & Included Items (/app/plans)
        # ----------------------------------------------------------------------
        print("\n--- Step 4: A04 & A05 Plans and Included Bundles ---")
        plan_suffix = uuid.uuid4().hex[:6]
        plan_name = f"Enterprise Scale_{plan_suffix}"

        page.goto(f"{FRONTEND_URL}/app/plans")
        page.wait_for_selector("h1:has-text('Subscription Plans')")

        page.click("button:has-text('New Plan')")
        page.wait_for_selector("h2:has-text('Create New Subscription Plan')")

        page.fill("input[placeholder='e.g. Standard Business Plan']", plan_name)
        page.fill("input[type='number'] >> nth=0", "1000.00") # base fee
        page.fill("input[type='number'] >> nth=1", "5")       # minimum seats
        page.fill("input[type='number'] >> nth=2", "100.00")  # excess seat unit price
        page.select_option("form select >> nth=0", "MONTHLY")
        page.get_by_label("Find tax rule", exact=True).fill(tax_name)
        page.locator(f"label:has-text('{tax_name}') input[type='checkbox']").check()

        page.click("button:has-text('Create Plan')")
        page.wait_for_selector("h2:has-text('Create New Subscription Plan')", state="hidden")
        page.locator("input[placeholder^='Search']").first.fill(plan_name)

        # Verify plan in list
        page.wait_for_selector(f"span:has-text('{plan_name}')")
        print(f"PASS: Plan '{plan_name}' created (Base: ₹1000, 5 seats, ₹100 excess)")

        # Open Plan Detail (A05)
        plan_row = page.locator("tr", has_text=plan_name)
        plan_row.locator("a:has-text('Manage')").click()

        page.wait_for_url("**/app/plans/*")
        page.wait_for_selector(f"h1:has-text('{plan_name}')")
        print("PASS: Landed on A05 Plan Detail page")

        # Add Included Product Bundle
        page.click("button:has-text('Add Included Product')")
        page.wait_for_selector("h2:has-text('Add Included Product Bundle')")

        page.get_by_label("Find bundle product", exact=True).fill(prod_name)
        page.select_option("div.fixed select >> nth=0", label=prod_name)
        time.sleep(0.5)
        page.fill("div.fixed input[type='number']", "1")
        page.click("button:has-text('Add to Plan')")

        # Save Plan configuration
        page.click("button:has-text('Save Plan Configuration')")
        page.wait_for_selector("text='Plan configuration updated successfully.'")
        print("PASS: Included product bundle added and plan configuration saved")

        # ----------------------------------------------------------------------
        # Journey Step 5: A07 Discount Rules & Revisions (/app/discounts)
        # ----------------------------------------------------------------------
        print("\n--- Step 5: A07 Discounts and Versioned Revisions ---")
        disc_suffix = uuid.uuid4().hex[:6]
        disc_name = f"Promo Special_{disc_suffix}"

        page.goto(f"{FRONTEND_URL}/app/discounts")
        page.wait_for_selector("h1:has-text('Discount Rules')")

        page.click("button:has-text('New Discount Rule')")
        page.wait_for_selector("h2:has-text('Create New Discount Rule')")

        page.fill("input[placeholder='e.g. Annual Subscription 10% Off']", disc_name)
        page.fill("input[placeholder='Leave empty for unlimited redemptions']", "50")
        page.select_option("div.fixed select >> nth=0", "SUBSCRIPTION")
        page.select_option("div.fixed select >> nth=1", "PERCENT")
        page.fill("div.fixed input[type='number'] >> nth=1", "10.00") # 10%
        page.click("button:has-text('Create Rule')")
        page.wait_for_selector("h2:has-text('Create New Discount Rule')", state="hidden")

        page.locator("input[placeholder^='Search']").first.fill(disc_name)

        # Verify discount rule in list
        page.wait_for_selector(f"span:has-text('{disc_name}')")
        disc_row = page.locator("tr", has_text=disc_name)
        assert "10%" in disc_row.text_content()
        assert "Revision 1" in disc_row.text_content()
        print(f"PASS: Discount rule '{disc_name}' created with Revision 1 (10%)")

        # Add Revision 2 (bump to 15%)
        disc_row.locator("button:has-text('New Revision')").click()
        page.wait_for_selector("h2:has-text('Publish New Revision')")

        page.fill("div.fixed input[type='number'] >> nth=0", "15.00") # 15%
        page.click("button:has-text('Publish Revision')")

        # Verify revision 2 is active
        page.wait_for_selector(f"tr:has-text('{disc_name}'):has-text('Revision 2')")
        disc_row2 = page.locator("tr", has_text=disc_name)
        assert "15%" in disc_row2.text_content()
        print("PASS: Published Revision 2 with updated 15% discount")

        # ----------------------------------------------------------------------
        # Journey Step 6: A08 & A09 Quotation Templates & Live Pricing Preview
        # ----------------------------------------------------------------------
        print("\n--- Step 6: A08 & A09 Quotation Templates and Pricing Preview ---")
        tpl_suffix = uuid.uuid4().hex[:6]
        tpl_name = f"Enterprise Onboarding_{tpl_suffix}"

        page.goto(f"{FRONTEND_URL}/app/quotation-templates")
        page.wait_for_selector("h1:has-text('Quotation Templates')")

        page.click("button:has-text('New Template')")
        page.wait_for_selector("h2:has-text('Create Quotation Template')")

        page.fill("input[placeholder='e.g. Standard SaaS Onboarding']", tpl_name)
        page.get_by_label("Find template plan", exact=True).fill(plan_name)
        page.select_option("div.fixed select", label=plan_name)
        page.fill("div.fixed input[type='number']", "45") # 45 days validity
        page.click("button:has-text('Create & Configure Lines')")

        # Should automatically route to A09 editor
        page.wait_for_url("**/app/quotation-templates/*")
        page.wait_for_selector(f"h1:has-text('{tpl_name}')")
        print("PASS: Created template and navigated to A09 Template Editor")

        # Add Line Item to Template (Paid add-on)
        page.click("button:has-text('Add Template Line')")
        page.wait_for_selector("h2:has-text('Add Line Item to Template')")

        page.select_option("div.fixed select >> nth=0", "ADDON")
        page.get_by_label("Find template product", exact=True).fill(prod_name)
        page.select_option("div.fixed select >> nth=1", label=f"{prod_name} (₹200.00)")
        time.sleep(0.5)

        # Select variant
        var_select = page.locator("div.fixed select >> nth=2")
        var_select.select_option(label="High Memory 560 (+₹560.00)")

        page.fill("div.fixed input[type='number']", "2")
        page.click("button:has-text('Add Line')")

        # Verify line in table
        page.wait_for_selector(f"td:has-text('{prod_name}')")
        print("PASS: Added paid add-on line (2 units of variant High Memory 560)")

        # Click Live Pricing Estimate Preview button!
        page.click("button:has-text('Preview Live Pricing Estimate')")

        # Verify pricing breakdown appears
        page.wait_for_selector("h3:has-text('Authoritative Pricing Preview')")
        preview_box = page.locator("div:has-text('Authoritative Pricing Preview')").last
        box_text = preview_box.text_content() or ""
        print(f"DEBUG preview_box text: {box_text}")
        assert "Authoritative Pricing Preview" in box_text
        page.get_by_text("₹2973.60", exact=True).wait_for()
        print("PASS: Authoritative live pricing estimate preview calculated successfully")

        # Activate template and save
        page.check("input#tplActive")
        page.click("button:has-text('Save Template')")
        page.wait_for_selector("text='Quotation template saved successfully.'")
        page.wait_for_selector("span:has-text('Active Template')")
        print("PASS: Activated and saved quotation template")

        # ----------------------------------------------------------------------
        # Journey Step 7: Staff Role Verification & Authorization Boundaries
        # ----------------------------------------------------------------------
        print("\n--- Step 7: Staff Role Boundaries Verification ---")

        # Admin provisions a staff account
        staff_uid = uuid.uuid4().hex[:6]
        staff_email = f"staff_cat_{staff_uid}@brightloop.test"
        staff_name = f"Catalog Staff {staff_uid}"
        page.goto(f"{FRONTEND_URL}/app/staff")
        page.click("button:has-text('Provision Staff')")
        page.fill("input[placeholder='Staff member full name']", staff_name)
        page.fill("input[placeholder='staff@brightloop.test']", staff_email)
        page.fill("form input[placeholder='•••••••••'] >> nth=0", "Staff@Pass1234")
        page.fill("form input[placeholder='•••••••••'] >> nth=1", "Staff@Pass1234")
        page.click("button:has-text('Provision Staff') >> nth=1")
        page.locator("input[placeholder^='Search']").first.fill(staff_name)
        page.wait_for_selector(f"p:has-text('{staff_name}')")
        print(f"PASS: Provisioned staff account {staff_email}")

        staff_context = browser.new_context()
        staff_page = staff_context.new_page()

        staff_page.goto(f"{FRONTEND_URL}/login")
        staff_page.fill("input#email", staff_email)
        staff_page.fill("input#password", "Staff@Pass1234")
        staff_page.click("button[type='submit']")
        staff_page.wait_for_url("**/app")

        # Verify staff navigation does NOT contain admin configuration links
        nav_text = staff_page.locator("nav").text_content() or ""
        assert "Products" not in nav_text
        assert "Plans" not in nav_text
        assert "Taxes" not in nav_text
        assert "Discounts" not in nav_text
        assert "Templates" not in nav_text
        assert "Staff" not in nav_text
        print("PASS: Staff navigation hides admin-only configuration pages")

        # Verify visiting admin product page directly shows Access Restricted
        staff_page.goto(f"{FRONTEND_URL}/app/products")
        staff_page.wait_for_selector("h2:has-text('Access Restricted')")
        print("PASS: Direct navigation by staff to /app/products blocked with Access Restricted")

        print("\n=======================================================")
        print("ALL PLAYWRIGHT CATALOG JOURNEYS (A02-A09) PASSED (100%)")
        print("=======================================================\n")
        browser.close()


from browser_test_errors import install_redaction
install_redaction()


if __name__ == "__main__":
    run_catalog_e2e_tests()
