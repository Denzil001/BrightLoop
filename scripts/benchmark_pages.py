"""Real browser navigation-to-content timings for every planned page template.

Fresh browser contexts per observation; warm local production servers. Timing
includes authentication lookup, route rendering, initial API work and DOM data.
It excludes browser/context creation and login setup. No API-only proxy metric.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import hashlib
import math
from pathlib import Path
import platform
import re
import statistics
import time

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
API, WEB = "http://localhost:8001/api/v1", "http://localhost:3001"


def source_fingerprint():
    """Identify measured source without reading private environment files."""
    paths = [p for folder in ("backend/app", "backend/alembic/versions", "frontend/src")
             for p in (ROOT / folder).rglob("*")
             if p.is_file() and p.suffix in {".py", ".ts", ".tsx", ".css"}]
    paths.extend(ROOT / name for name in ("frontend/next.config.mjs", "frontend/package.json",
                                         "frontend/package-lock.json", "backend/requirements.txt"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def inventory(manifest):
    rows = re.findall(r"\| ([PIAC]\d{2}) \| `([^`]+)`", (ROOT / "BUILD_GUIDE.md").read_text(encoding="utf-8"))
    assert len(rows) == len(set(code for code, _ in rows)) == 32
    ids = {"customerId": "customer_id", "subscriptionId": "subscription_id", "invoiceId": "invoice_id",
        "productId": "product_id", "planId": "plan_id", "templateId": "template_id"}
    pages = []
    for code, path in rows:
        for parameter, field in ids.items():
            path = path.replace(f"[{parameter}]", manifest[field])
        assert "[" not in path, f"Unresolved route: {code}"
        if code == "P04":
            path += "?token=synthetic-benchmark-form-mode"
        pages.append({"id": code, "path": path, "role": "customer" if code.startswith("C") else "public" if code.startswith("P") else "admin"})
        if code.startswith("I"):
            pages.append({"id": f"staff:{code}", "path": path, "role": "staff"})
    return pages


async def states(playwright):
    saved = {"public": {"cookies": [], "origins": []}}
    counts, summary = {}, {}
    for role in ("admin", "staff", "customer"):
        client = await playwright.request.new_context()
        csrf = await client.get(f"{API}/auth/csrf")
        token = (await csrf.json())["csrf_token"]
        response = await client.post(f"{API}/auth/login", data={"email": f"benchmark_{role}@brightloop.test", "password": "Benchmark@Secure123"},
            headers={"X-CSRF-Token": token, "Origin": WEB})
        assert response.ok, f"Benchmark {role} sign-in failed ({response.status})"
        saved[role] = await client.storage_state()
        if role == "admin":
            report = await client.get(f"{API}/reports/summary?date_from=2000-01-01&date_to=2099-01-01")
            assert report.ok
            summary = await report.json()
            assert summary["received"] == "34500000.00" and summary["outstanding"] == "24500000.00", "Seeded ledger does not reconcile to finance summary."
            for resource in ("subscriptions", "invoices", "payments", "customers"):
                listing = await client.get(f"{API}/{resource}?page_size=1")
                assert listing.ok
                counts[resource] = (await listing.json())["total"]
            assert counts["subscriptions"] >= 5000 and counts["invoices"] >= 50000 and counts["payments"] >= 100000
        await client.dispose()
    return saved, counts, summary


async def observe(browser, state, item, semaphore, cache_mode="cold"):
    async with semaphore:
        context = await browser.new_context(storage_state=state, viewport={"width": 1440, "height": 1000})
        page = await context.new_page()
        pending, failures, errors = set(), [], []
        page.on("request", lambda request: pending.add(request) if request.url.startswith(API) else None)
        page.on("requestfinished", lambda request: pending.discard(request))
        page.on("requestfailed", lambda request: (pending.discard(request), failures.append("API request failed")) if request.url.startswith(API) else None)
        page.on("pageerror", lambda error: errors.append(str(error)))
        def check_response(response):
            if response.url.startswith(API) and response.status >= 400:
                if not (item["role"] == "public" and response.status == 401 and response.url.endswith("/auth/me")):
                    failures.append(f"API {response.status}")
        page.on("response", check_response)
        started = time.perf_counter()
        try:
            if cache_mode == "warm":
                warmup = await page.goto(WEB + item["path"], wait_until="domcontentloaded", timeout=15000)
                assert warmup and warmup.ok, "Warm-cache preparation failed"
                await page.wait_for_load_state("networkidle", timeout=15000)
                assert not pending and not failures and not errors, "Warm-cache preparation had page/API errors"
                started = time.perf_counter()
            response = await page.goto(WEB + item["path"], wait_until="domcontentloaded", timeout=15000)
            assert response and response.ok
            await page.wait_for_function("""() => {
                const body = document.body.innerText;
                return !!document.querySelector('h1,h2') &&
                  !/Loading[^\\n]*|Authenticating session|Opening your workspace/i.test(body) &&
                  !/Access restricted|Permission denied|not authorized/i.test(body);
            }""", timeout=15000)
            # Request completion plus rendered loading-state exit prevents timing
            # an authenticated shell or a delayed selector request as a full page.
            deadline = time.perf_counter() + 15
            while pending and time.perf_counter() < deadline:
                await page.wait_for_timeout(10)
            assert not pending and not failures and not errors, f"Page errors: {failures + errors}"
            code = item["id"].split(":")[-1]
            if code == "I05":
                assert await page.get_by_role("combobox", name="Customer", exact=True).locator("option").count() > 1
                assert await page.get_by_role("combobox", name="Plan", exact=True).locator("option").count() > 1
                assert await page.get_by_role("button", name="Save draft", exact=True).is_enabled(), "Quotation editor is not usable yet"
            if code in {"I02", "I04", "I07", "I09", "A01", "A02", "A04", "A06", "A07", "A08", "C02", "C04", "C06"}:
                assert await page.locator("tbody tr").count() > 0, "Data list has not rendered persisted rows."
            elapsed = (time.perf_counter() - started) * 1000
            # A render opportunity after DOM updates is included in the boundary.
            await page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            elapsed = (time.perf_counter() - started) * 1000
            return {"id": item["id"], "role": item["role"], "milliseconds": round(elapsed, 2), "pass": elapsed < 2000}
        except Exception as exc:
            return {"id": item["id"], "role": item["role"], "pass": False, "error": redact(str(exc).split("Call log:")[0][:500])}
        finally:
            await context.close()


async def run(args):
    manifest = json.loads((ROOT / "test-results/benchmark-manifest.json").read_text(encoding="utf-8"))
    pages = inventory(manifest)
    if args.pages:
        available = {item["id"].split(":")[-1] for item in pages}
        if not set(args.pages) <= available:
            raise ValueError("Unknown diagnostic template ID")
        pages = [item for item in pages if item["id"].split(":")[-1] in args.pages]
    async with async_playwright() as playwright:
        saved, counts, finance = await states(playwright)
        manifest = {**manifest, "seed_counts": manifest["counts"], "counts": counts, "current_finance_snapshot": finance}
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        fingerprint = source_fingerprint()
        samples = []
        for concurrency in args.concurrency:
            semaphore = asyncio.Semaphore(concurrency)
            jobs = [observe(browser, saved[item["role"]], item, semaphore, args.client_cache) for _ in range(args.repeats) for item in pages]
            results = await asyncio.gather(*jobs)
            samples.extend({**result, "concurrency": concurrency} for result in results)
            print(f"Concurrency {concurrency}: {len(results)} observations, {sum(not result['pass'] for result in results)} failing", flush=True)
        summaries = []
        for concurrency in args.concurrency:
            for item in pages:
                selected = [sample for sample in samples if sample["id"] == item["id"] and sample["concurrency"] == concurrency]
                timings = sorted(sample["milliseconds"] for sample in selected if "milliseconds" in sample)
                summaries.append({"id": item["id"], "role": item["role"], "concurrency": concurrency,
                    "samples": len(selected), "p50_ms": round(statistics.median(timings), 2) if timings else None,
                    "p95_ms": timings[max(0, math.ceil(len(timings) * .95) - 1)] if timings else None,
                    "max_ms": max(timings) if timings else None, "pass": all(sample["pass"] for sample in selected)})
        assert source_fingerprint() == fingerprint, "Application source changed during measurement"
        report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "dataset": manifest,
            "scope": "diagnostic subset" if args.pages else "all 32 templates and ten staff variants",
            "selected_ids": [item["id"] for item in pages],
            "client_cache": args.client_cache,
            "warm_cache_preparation": "one completed navigation and network idle before timed navigation" if args.client_cache == "warm" else None,
            "frontend_build_id": (ROOT / "frontend/.next-benchmark/BUILD_ID").read_text(encoding="utf-8").strip(),
            "source_sha256_at_measurement": fingerprint,
            "boundary": "fresh browser context navigation through rendered initial data and two animation frames; warm production servers",
            "platform": platform.platform(), "browser": browser.version, "viewport": "1440x1000", "throttling": "none; local loopback",
            "summaries": summaries, "observations": samples}
        output = ROOT / f"test-results/{args.output}"
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        failed = [summary for summary in summaries if not summary["pass"]]
        for summary in failed:
            print(f"FAIL: {summary}")
        print(f"Report: {output}; {len(summaries) - len(failed)}/{len(summaries)} page/concurrency gates passed.")
        await browser.close()
        return int(bool(failed))


from browser_test_errors import install_redaction, redact
install_redaction()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 5])
    parser.add_argument("--output", default="browser-benchmark.json")
    parser.add_argument("--pages", nargs="+", help="Diagnostic subset by template ID, including applicable staff variants")
    parser.add_argument("--client-cache", choices=["cold", "warm"], default="cold")
    args = parser.parse_args()
    if args.repeats < 1 or any(value < 1 or value > 20 for value in args.concurrency) or Path(args.output).name != args.output:
        parser.error("Use positive repetitions, 1–20 concurrent navigations and a filename without directories.")
    raise SystemExit(asyncio.run(run(args)))
