# Autonomous development status

Final local release checkpoint (3 November 2026): **Phases 0–9 PASS**. All planned software, source/action/API, financial, setup and linked-demo gates have current evidence. Final verification and handoff are recorded at the end; older sections are historical checkpoints. The release is integrated on codex/finish-brightloop.

The user authorized fixing the remaining issues and completing all remaining phases here, without further phase-acceptance prompts. This supersedes manual approval pauses, not requirements, security constraints or test gates. Full project completion remains the objective. Accepted D01-D10 in business-rules.md remain authoritative.

## Verified progress - 1 November 2026

Phase 3 corrections completed:
- Added services/template_validation.py to validate retained plan/product/variant references before template activation, including metadata-only PATCH operations. Failed activation rolls back.
- Added three permanent PostgreSQL regression cases in tests/test_template_activation.py; all assert rejection and unchanged inactive state.
- Removed the browser runner's email-skip branch. Mailpit is mandatory before any journey; successful completion reports five passed and zero skipped.
- Started Docker Desktop, existing Compose Mailpit, backend and production frontend for actual acceptance tests.

Commands actually run:
```powershell
$env:PYTHONPATH='.;backend'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=no
docker compose up -d mailpit
backend/.venv/Scripts/python.exe -u scripts/test_browser_journeys.py
backend/.venv/Scripts/python.exe -u scripts/test_catalog_journeys.py
```

Results: 60 backend tests passed, 13 pre-existing deprecation warnings. Core Playwright runner completed all five journeys, including Mailpit account-link verification and reset delivery; zero skipped. Catalog Playwright journey passed all seven steps. This was the Phase 3 checkpoint; Phase 4 evidence is recorded below. Earlier production build passed before these backend-only/template-test changes; frontend source was unchanged in this correction.

Local server sessions started for testing: backend exec session 42067 (uvicorn process 30620), frontend exec session 38230. These are observations at verification time, not proof of future liveness; recheck the same handles/ports before restarting. Backend access logs are disabled to avoid logging reset/verification URL secrets. Mailpit remains the existing Compose service on loopback.

## Remaining work

- Phase 9: repeatable seed, reproducible setup, all pages/actions, integration/browser checks, measured two-second performance evidence, final source/requirement audit.

Next step: Phase 9 dataset, performance, complete source/page/action/API audit and evaluation readiness. Continue without asking for phase approvals. Preserve current uncommitted Antigravity work. Do not mark the goal complete until all remaining phases and the requirement-by-requirement completion audit actually pass.

## Phase 4 evidence — 1 November 2026

Implemented:
- Five planned pages I04–I06/C02–C03, shared responsive editor/list/detail, operational customer entry links and preselection, role navigation.
- SQL filtering and stable pagination, recurring estimate/expiry/Ended flag and pending-request counts.
- Draft aggregate, template/default bundle population, immutable numbered quotation revisions, inclusive expiry, confirmation under the same subscription, start-guarded activation and reasoned abandonment.
- Frozen line/tax/policy/commercial estimate snapshots; pin the exact selected discount revisions. Multiple product rules are allowed only on disjoint paid charge lines; whole-subscription rules stand alone. Previews do not consume discount redemptions.
- Expected-version writes, subscription row locking and command receipts. Real independent-connection concurrency regression proves duplicate confirmation yields one term and one receipt.
- Dated pause/resume/renewal/early-close/add-on events and a tested event applier. Pause extends term by paused days; resume resets the segment anchor. Changes do not apply before their effective date.
- Owned customer requests, cancellation, staff/admin review, changed-price/policy/version rejection and customer-safe product options. Approval records the event atomically with the review.
- Two additive Alembic migrations: d731a82cf901 and a4921b77fd02; applied to dev and isolated test databases.
- Reconciled API documentation to implemented routes, removed stale architecture claims, removed invented MRR/ARR/export and grace/notice scope from the roadmap.

Files changed: backend schemas/subscriptions.py; services/subscriptions.py, lifecycle.py, calendar.py, change_requests.py and pricing.py; endpoints/subscriptions.py and router; models/subscriptions.py; the two migrations; four subscription/multiple-discount test modules; frontend components/subscriptions, subscription pages, lib/subscriptions.ts and role/customer navigation; scripts/test_subscription_journeys.py; synchronized README/design/roadmap documents. Pre-existing teammate changes remain preserved and uncommitted.

Commands actually run:
```powershell
$env:PYTHONPATH='.;backend'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short
# Latest complete result: 82 passed, 14 deprecation warnings in 35.35 seconds.

# Run from backend:
.venv/Scripts/python.exe -m alembic upgrade head

# Run from frontend (explicit launcher avoids this machine's broken roaming npm shim):
& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' run build

# Live local browser acceptance:
backend/.venv/Scripts/python.exe -u scripts/test_subscription_journeys.py
# 3 passed, 0 skipped; includes multi-rule selection, staff quote acceptance,
# own customer request, staff review, customer feedback and mobile overflow assertion.
backend/.venv/Scripts/python.exe -u scripts/test_catalog_journeys.py
# All seven catalog journey steps passed after adding subscription navigation.
git diff --check
```

Manual verification: inspected the generated customer mobile screenshot; header wraps, page fits the 390-pixel viewport, tables scroll within cards, state and review feedback remain visible. Screenshots are local ignored artifacts in test-results/. No benchmark timings or complete-project acceptance are claimed.

Design decisions: store quotation estimates separately from authoritative future invoices; retain all accepted/issued versions; compose bounded disjoint discount results with the shared Decimal calculator rather than a second allocation algorithm; schedule intent separately from applying service state. New quote save/issue commits as one transaction.

Manual actions remaining for Phase 4: none. No additional user approval is needed under the active objective.

Known limits/deferred checks: 14 existing dependency deprecation warnings remain. Financial redemption/cursor/concurrency integration belongs to Phase 5; actual periodic invocation belongs to Phase 8. Dataset/browser performance evidence and final complete-source audit remain Phase 9. Do not claim invoice/payment/report functionality is implemented yet. UI polish and the final all-actions audit remain required before overall completion.

Gate status: Phase 4 PASS for the documented phase acceptance checks; overall project IN PROGRESS. Continue with Phase 5 without requesting approval.

Current local server handles (revalidate before restart): backend exec 27742, uvicorn PID 2736; frontend exec 68822. Prior server handles in earlier notes have been stopped. Frontend build includes the final multi-discount UI. Backend access logs remain disabled.

## Phase 5 evidence — 2 November 2026

Implemented:
- Five planned templates I07/I08/A11/C04/C05: operational and owner-scoped invoice lists/details, billing-run history/outcomes/recovery, responsive navigation and customer/subscription source links.
- Shared pure Decimal calculator now serves previews and frozen agreement billing. No billing path reads live catalog prices or live tax rates. Exact fixed-discount allocation, thresholds, disjoint scopes and per-line tax rounding have one implementation.
- Historical term/pause reconstruction, all four anchored intervals, expiry-exclusive final-period proration, automatic eligible confirmation activation through reconciliation, and chronological application of approved boundary events. Current CLOSED/PAUSED state and a cleared cursor cannot erase earlier owed periods.
- Per-period subscription locks and invoice uniqueness; sorted discount-rule locks; cap evaluation after locks; atomic snapshots, redemptions, allocations, cursor and outcome. Retries preserve invoice dates and identities; failures retain earlier commits and block later periods only on that subscription.
- Bounded admin/CLI batches with stable subscription continuation, optional single-subscription scope, persistent safe failures and a database-backed preceding-run link. Terminal probes do not miscount invoices created in that same run as pre-existing periods.
- Invoice snapshot list/detail filters, owner/issued-state enforcement, audited draft-only billing corrections, idempotent confirmation/cancellation, zero-total settlement without fake payments and cancellation that preserves period/redemption consumption.
- Local ReportLab PDF, browser print, customer-safe PDF authorization, persisted email attempts and real SMTP PDF attachments through the existing Mailpit adapter. Invoice header/lines/taxes/customer/company are persisted snapshots. Draft/cancelled documents remain explicitly marked.
- Additive migrations e7312d48bc50 (proration context), f3d74198a062 (composed descriptions), b502c8e34a17 (recovery-run link); applied to development and isolated test databases. Application engine explicitly uses READ COMMITTED for cap rechecks after row-lock waits.

Files changed: billing/invoice models and migrations; services/financial_calculator.py, discount_context.py, billing_periods.py, billing.py, billing_runs.py, invoices.py, invoice_documents.py, invoice_delivery.py; pricing service refactored to the shared calculator; invoice/run schemas and endpoints; SMTP attachment support; requirements; six new billing/invoice test modules; five invoice/run pages and shared components; API blob support; navigation/source links; scripts/run_billing.py and scripts/test_billing_journeys.py; synchronized guides.

Commands actually run:
```powershell
$env:PYTHONPATH='.;backend'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short
# Final restored-environment run: 100 passed, 16 existing deprecation warnings, 33.62 seconds.

# From backend:
.venv/Scripts/python.exe -m alembic upgrade head
# Phase 5 checkpoint head b502c8e34a17; native PostgreSQL remains the only database.

# From frontend:
& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' run build
# Production compilation/type checks/static generation passed.

backend/.venv/Scripts/python.exe -u scripts/test_billing_journeys.py
# Four passed, zero skipped; real Mailpit delivery/attachment, authorized customer
# download, print styling, mobile overflow, cancellation and no replacement on replay.
backend/.venv/Scripts/python.exe -u scripts/test_subscription_journeys.py
# Three passed after shared-calculator/invoice-link integration (1 November).

# CLI replay of the browser-created synthetic subscription:
$billingBrowserIds = Get-Content test-results/billing-browser-ids.json | ConvertFrom-Json
backend/.venv/Scripts/python.exe scripts/run_billing.py --subscription-id $billingBrowserIds.subscription_id
# COMPLETED; created=0, existing=1, failed=0, has_more=False.

git diff --check
```

Verification evidence: independent PostgreSQL connections race the same period (one invoice/advance) and two subscriptions against one global discount use (one discounted invoice, one full price). Other regressions cover rollback, late/closed backlog, Jan 31 restoration, leap anniversaries, daily/weekly/yearly periods, partial periods, safe failure outcomes, bounded continuation, linked runs, isolation, draft ownership, cancellation history, zero totals, PDF text and failed email retry.

Manual verification: rendered and inspected the regular PDF plus every page of a three-page stress case with long catalog descriptions. Kept invoice summary/status together to prevent orphaned final notes. Inspected the mobile customer invoice screenshot. Artifacts are ignored under test-results/. Poppler printed local fallback-font warnings; inspected Latin/INR output is legible, with no missing glyphs or clipped table content. No international typography certification or browser performance benchmark is claimed.

Design decisions: invoice unit prices retain agreed full-period values; persisted actual/full days explain prorated base amounts. Billing recovers history independently of the cursor. CLI and admin use the same engine. SMTP runs outside the invoice-creation transaction; explicit retries do not promise exactly-once email delivery.

Manual actions remaining for Phase 5: none. Known limits: 16 dependency deprecation warnings; automated scheduler/auto-close and interruption hardening remain Phase 8; payment entry/receipts/ledger are Phase 6; dashboard/report aggregates are Phase 7; representative dataset and full source/performance audit remain Phase 9. Overall completion is not claimed.

Gate status: Phase 5 PASS. Continue with Phase 6 without asking for approval.

Latest server handles after restoration (revalidate before restarting): backend exec 68829 / uvicorn PID 32536; frontend exec 56115. Earlier handles have stopped. Docker Mailpit was restored and the live browser test verified actual delivery. No access logs containing document/reset tokens are enabled.

## Phase 6 evidence — 2 November 2026

Implemented:
- I09/C06 operational/customer ledgers with persisted filters, stable SQL pagination, read-only accessible drawers, source invoice links and local receipt downloads.
- I08 operational payment dialog and I08/C05 recent payment history/current balances. Only staff/admin can record positive payments against eligible issued invoices. Customers have read-only owned records; actor/time/request-key/hash metadata is excluded.
- Invoice row lock, authoritative persisted payment sum, overpayment/state checks, normalized global request key/hash and transactional payment/status/audit writes. Same-key/same-payload replay returns the original payment even after settlement. Changed intent returns 409; different-invoice key races roll back the losing write/status change.
- Permanent PostgreSQL UPDATE/DELETE rejection trigger for payments (migration c6493de14f80). No payment editing, deletion, refunds or external gateway was added.
- Browser keeps an unconfirmed per-user/per-invoice payment intent in session storage. Lost-response reload retry reuses the same key and details; an explicitly detected changed-key intent conflict offers review/new-entry recovery rather than silently creating a payment.
- Receipt rendering uses immutable payment and invoice snapshot fields; regular PDF and mobile drawer visually inspected. Invoice/customer ledger links and source navigation are connected.
- Also closed the documented draft-creation retry gap: browser sends Idempotency-Key, actor-scoped creation retries serialize and return the same aggregate, changed creation details conflict. Legacy API callers without that header remain compatible; browser saves always include it.

Files changed: schemas/payments.py, services/payments.py and payment_documents.py, endpoints/payments.py and nested invoice payment endpoint, invoice history response, API router, immutable-ledger migration; payment API/concurrency tests and reusable isolated race-test teardown; frontend payment dialog/drawer/ledger, two ledger pages, invoice history/recording integration, downloads/field-error helpers, navigation; scripts/test_payment_journeys.py. Draft-creation header/receipt and its regression were added to the subscription API/new page. README/API/schema/roadmap/architecture documents are synchronized.

Commands actually run:
```powershell
$env:PYTHONPATH='.;backend'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short
# Final result: 120 passed, 25 dependency deprecation warnings in 22.03 seconds.

# From backend:
.venv/Scripts/python.exe -m alembic upgrade head
# Development and test schema head: c6493de14f80.

# From frontend:
& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' run build
# Production compilation/types/static generation passed for both ledger pages and dialog.

backend/.venv/Scripts/python.exe -u scripts/test_payment_journeys.py
# Three passed, zero skipped. The browser forwards one payment to a successful
# server commit, aborts its response, reloads, restores the entry and retries.
# Exactly one first payment remains; final installment settles the invoice.
backend/.venv/Scripts/python.exe -u scripts/test_subscription_journeys.py
# Three passed against final browser draft-creation header and new invoice links.
backend/.venv/Scripts/python.exe -u scripts/test_billing_journeys.py
# Four passed after payment integration: invoices, actual SMTP/PDF, ownership,
# cancellation and replay remain correct.

pdftoppm -scale-to 1200 -png -singlefile test-results/payment-receipt.pdf test-results/payment-receipt
git diff --check
```

Verification: five independent-connection races cover two valid partial payments, competing full payments, same-key retries, global key collision on different invoices, and payment versus invoice cancellation. Other tests cover the accepted partial/final balances, normalized retries, changed payload, paid/draft/cancelled state guards, invalid/future/non-positive/over-precision amounts and notes, foreign ownership, customer-safe receipt/detail schemas and actual PostgreSQL payment update/delete rejection. Committed concurrency fixtures bypass the immutability trigger only inside isolated test-DB teardown transactions; production/application paths never do.

Manual verification: payment receipt text/layout inspected from a rendered PNG; mobile customer drawer screenshot inspected, including visible note, method, reference, receipt button and absence of internal actor metadata. Browser assertion verifies no horizontal viewport overflow. Test outputs remain ignored under test-results/.

Design decisions: serialize on invoice before reading balance; normalize the financial intent hash; rollback key collisions with a savepoint while retaining the invoice lock; derive status from actual sums; preserve uncertain browser intent across retries/reload. Receipt states only its immutable payment amount and refers users to the portal for the current balance.

Manual actions remaining for Phase 6: none. Known limits: 25 dependency deprecation warnings; dashboards/reports remain Phase 7; scheduler/security/auto-close remain Phase 8; final measured performance/source/page/action audit remains Phase 9. That audit must check all selectors beyond their initial choice page and outstanding transport consistency details (Location/filter behavior); no whole-project completion claim is made.

Gate status: Phase 6 PASS. Continue with Phase 7 without asking for approval.

Latest live handles: backend exec 99059 / uvicorn PID 29504; frontend exec 49870. Prior Phase 5 handles have been stopped. Native PostgreSQL and existing Mailpit are retained. No test credentials or private environment values were printed or committed.

## Phase 7 evidence — 2 November 2026

Implemented: I01/A10/C01 operational, finance and own-customer dashboards; SQL aggregates and stable paginated report details; payment-date/customer/plan filters, current balances and matching source links. Staff sees operational queues without administrator financial totals/reports. Customer queries enforce ownership and exclude internal payment metadata. Active service excludes paused/ended/due-stop terms. Recent invoices display state. Login now lands on the role overview and restricts return destinations to the role route prefix. Financial audit history remains intact.

Files changed: reporting service/endpoints/tests and API router; shared subscription/invoice filters; Dashboard and report page; source filter initialization in subscription/invoice/payment components; role navigation and login/AuthContext; reporting API types; reporting browser runner and landing assertions in existing runners; roadmap/API/README/status docs. No schema migration required.

Commands actually run:
```powershell
$env:PYTHONPATH='.;backend'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short
# 126 passed, 26 dependency deprecation warnings in 25.99 seconds.
# From frontend:
& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' run build
# Production build/type checks passed. Sandbox output-directory EPERM resolved by approved local execution.
backend/.venv/Scripts/python.exe -u scripts/test_reporting_journeys.py
# Three passed, zero skipped; final filtered SQL summary 9.2 ms.
git diff --check
```

Test results: filtered receipts/outstanding/overdue reconcile to real payment sums; date ranges affect receipts only; role denial, foreign ownership, stable pagination, due-stop service filtering and unchanged financial audit records pass. Browser verifies filtered report/source links, staff queue navigation and report denial, customer owned active/outstanding drill-down and mobile overflow. Core authentication/Mailpit journeys also passed five with new overview landings during this phase. Loaded mobile dashboard screenshot inspected; dynamic cards/reminders/history fit the viewport.

Design decisions: one role-aware /dashboard endpoint; authoritative SQL definitions shared with detail/source filters; exact Decimal strings; stale asynchronous responses cannot replace newer selected filters. SQL query time is explicitly distinct from browser performance.

Manual actions remaining: none for Phase 7. Known issues/deferred: 26 dependency deprecation warnings; automatic scheduling/recovery/security is Phase 8; representative dataset, all-pages/actions/source audit and measured under-two-second browser acceptance remain Phase 9. Overall project IN PROGRESS.

Gate status: Phase 7 PASS. Continue Phase 8 without approval prompts. Current live backend exec 6295 / PID 31780; frontend exec 37525. Revalidate before restarting.

## Phase 8 evidence — 2 November 2026

Implemented: separate foreground scheduler process using the existing bounded billing engine; exclusive PostgreSQL tick lock and per-run ownership locks; actual runtime state/heartbeat/interval/continuation; safe orphaned manual/CLI/scheduled run recovery from committed outcomes. A live owner's lock prevents false interruption. Due lifecycle changes and frozen auto-close flags reconcile after historical billing; open pauses do not close at their former expiry. Old PENDING invoice email attempts become UNKNOWN without blind resend. Expired shared auth windows/pre-auth challenges are cleaned.

Hardening: PostgreSQL-backed authentication admission windows replace process memory and count each attempt once. User row locking rechecks verified credentials before session issuance, serializes reset/deactivation and makes password-change/revocation atomic. Added safe authentication audit events, bounded password fields, signup-verification/CSRF-issuance rate protection, API/browser security/cache headers and truthful failed sign-out feedback. Patched nested PostCSS through an npm override; no Next.js major upgrade required.

Files changed: scheduler/rate-limit models and migrations d8a149c27e60/e90c51fa2b73; scheduler service/entry point; billing service/run ownership and admin runtime response; auth service/routes/schemas, main security headers, tests/conftest; scheduler/hardening test modules; frontend billing runtime/recovery UI, AuthContext/layout feedback, Next config, package/lock; browser security runner, audit launcher/optional security requirements; README, API/schema/architecture/roadmap and new OPERATIONS/SECURITY_VERIFICATION guides. Pre-existing teammate changes remain preserved and uncommitted.

Commands actually run:
```powershell
$env:PYTHONPATH='.;backend'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short
# Final: 138 passed, 26 dependency deprecation warnings in 45.58 seconds.
# The real worker process test runs two timer ticks against only the isolated test DB.
# From backend:
.venv/Scripts/python.exe -m alembic upgrade head
# Both development and test schema head: e90c51fa2b73.
# From frontend, explicit Node/npm launcher on this machine:
& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' install --ignore-scripts
& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' run build
# Production build passed against patched PostCSS; installation audit: zero vulnerabilities.
backend/.venv/Scripts/python.exe -m bandit -r backend/app -f json -o test-results/bandit.json
# Zero issues; no suppressed/skipped checks.
backend/.venv/Scripts/python.exe -c "import truststore,runpy,sys; truststore.inject_into_ssl(); sys.argv=['pip-audit','-r','backend/requirements.txt','--no-deps','--disable-pip','-f','json','-o','test-results/pip-audit.json']; runpy.run_module('pip_audit',run_name='__main__')"
# No known vulnerabilities. The equivalent reproducible launcher is scripts/audit_backend_dependencies.py.
backend/.venv/Scripts/python.exe -u scripts/test_browser_journeys.py
# Five passed, zero skipped, including actual Mailpit linking/reset/session revocation.
backend/.venv/Scripts/python.exe -u scripts/test_hardening_journeys.py
# Four passed, zero skipped: anonymous denial, escaped content/cookies/headers,
# actual scoped scheduler replay/runtime status, failed logout and revoking retry.
backend/.venv/Scripts/python.exe -u scripts/test_billing_journeys.py
# Final backend regression: four passed, zero skipped, including actual PDF/SMTP and replay.
git diff --check
```

Test results: two actual timed worker invocations create three invoices then zero; crash after a committed period recovers remaining periods without duplication; live manual owner remains RUNNING while orphaned CLI becomes INTERRUPTED. Frozen auto-close policy/pause history respected. Forty independent-connection auth attempts allow exactly ten and return thirty 429 responses with Retry-After. Reset racing eight session creations revokes/rejects all sessions based on old credentials. Cross-session CSRF/expiry/cache privacy and audit token exclusions pass. Browser HTML-shaped stored name stays literal, injection-shaped search returns no records, session is HttpOnly, and original session is revoked after successful logout retry.

Design decisions: OS-supervised separate worker, no API import/startup scheduling; persisted bounded continuation; per-run advisory ownership instead of timeout-only interruption guesses; explicit UNKNOWN SMTP ambiguity; shared DB auth windows; safe DB audit payloads. OPERATIONS.md explains local/production transport and process supervision. SECURITY_VERIFICATION.md maps scoped application evidence to OWASP Top 10:2025 and clearly distinguishes it from external certification.

Manual actions remaining: none for local Phase 8 acceptance. Keep scripts/run_scheduler.py running to enable continuous automatic billing; no OS service was installed. Browser verification deliberately stops its scoped workers and the UI correctly reports STOPPED. Production HTTPS/SMTP/proxy/service supervision require the deployment environment, not a fabricated local check.

Known issues/deferred: 26 dependency deprecation warnings; full representative dataset, browser p50/p95/max, query plans/indexes, all 32 templates/F01–F15/actions, final source/API/selector audit, setup/Git/demo readiness remain Phase 9. No complete-project or under-two-second benchmark claim is made.

Gate status: Phase 8 PASS for documented local application scope; overall goal IN PROGRESS. Continue Phase 9 without asking for approval. Latest live backend exec 10619 / PID 3680; frontend exec 69909. Revalidate handles before restarting; scoped scheduler processes have finished, not a running global worker.

## Phase 9 checkpoint — 3 November 2026 (not final acceptance)

Implemented:
- Re-read all four PDF pages; SHA-256 remains 80a2976f4c2ad05316975d61de32980ce622870c8d70748a37e42f1f992cf42a. Reviewed USER_FLOWS and identified real remaining contract/action gaps rather than declaring completion from earlier green tests.
- Root redirects to the authenticated role workspace/login; removed stale Phase 2 marketing/implementation text. Added collapsible mobile navigation.
- Template/discount server searches and selected record hydration remove the first-100 choice barrier; selected discount survives search changes. Shared quotation editor warns on internal navigation/close/logout and browser unload. Added rejected-request prefill (still requires a dedicated resubmission regression).
- Subscription response exposes frozen current term flags, pending change identity and per-line discount/tax/total estimates. Add-on changes keep term policy; UI does not use pending future agreements as current service. New permanent policy/estimate regression passed.
- Fixed discount current-revision/active filtering and form date defaults to Asia/Kolkata. Added explicit eight/nine password boundary with a valid nine-character password containing no digit; targeted regressions passed.
- Added guarded idempotent synthetic benchmark seeding in brightloop_benchmark schema, separate API/build ports 8001/3001, private ignored config, public-count guard and ledger balance/status checks. No public financial records were seeded or deleted.
- Added actual 32-template + ten staff-variant browser timer and SQL/EXPLAIN profiler. Corrected repeated payment aggregations and recent-invoice scans, started initial overview/report fetch immediately, and disabled global navigation prefetch flooding.
- Added PERFORMANCE_VERIFICATION.md and FINAL_ACCEPTANCE.md; synchronized known status/architecture wording without weakening remaining requirements.

Files changed: reporting/subscription/lifecycle/discount backend modules; lifecycle/auth/discount regressions; root and role layouts, shared editor/detail/report components/types/date helper/unsaved hook; benchmark build configuration/ignore; scripts/seed_benchmark.py, run_benchmark_api.py, benchmark_pages.py, profile_benchmark_queries.py, test_completion_navigation.py; new performance/final acceptance docs and existing guides. Pre-existing teammate work remains preserved/uncommitted.

Commands actually run:
```powershell
backend/.venv/Scripts/python.exe -u scripts/seed_benchmark.py
# 5,000 subscriptions, 50,000 invoices, 100,000 payments, 500 customers;
# ledger/status checks pass; public subscription count stayed 23 before/after.
# Benchmark build from frontend:
$env:BRIGHTLOOP_BUILD_DIR='.next-benchmark'
$env:NEXT_PUBLIC_API_BASE_URL='http://localhost:8001/api/v1'
& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' run build
backend/.venv/Scripts/python.exe -u scripts/run_benchmark_api.py
# Separate production frontend: next start --hostname 127.0.0.1 --port 3001
backend/.venv/Scripts/python.exe -u scripts/benchmark_pages.py --repeats 1 --concurrency 1 5 --output browser-benchmark-initial.json
# Initial 83/84 passed; admin overview 2,032.23 ms exposed a real failure.
backend/.venv/Scripts/python.exe scripts/profile_benchmark_queries.py --label before
backend/.venv/Scripts/python.exe scripts/profile_benchmark_queries.py --label after
# Full-range summary 307.12 -> 136.90 ms; recent invoices 87.11 -> 9.12 ms.
backend/.venv/Scripts/python.exe -u scripts/benchmark_pages.py --repeats 5 --concurrency 1 5
# All 420 observations passed. C1 p50/p95/max 182.83/535.49/675.44 ms;
# C5 p50/p95/max 452.33/939.55/1463.24 ms. No API-only substitution.
backend/.venv/Scripts/python.exe -u scripts/test_completion_navigation.py
# Three passed, zero skipped. Test selector corrections accounted for native
# select accessible names and the actual customer My subscriptions label.
$env:PYTHONPATH='.;backend'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short
# Latest full checkpoint: 139 passed, 26 dependency deprecations, 34.04 seconds.
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_auth.py backend/tests/test_discounts.py -q --tb=short
# Two subsequent boundary/timezone regressions included: 14 targeted passed.
# Main default production build also passed after all current frontend fixes;
# it uses .next and localhost:8000, independently of the benchmark build.
backend/.venv/Scripts/python.exe -u scripts/test_reporting_journeys.py
# Main app: three passed, zero skipped; filtered sample SQL summary 4.56 ms.
git diff --check
```

Test results/evidence: performance runs use Chrome 156.0.8078.76, i7-14650HX (16 cores/24 threads), ~16 GB RAM, Windows 11 10.0.26300, local PostgreSQL 18, fresh browser contexts and warm production servers. Timings include auth lookup, initial API/DOM data and two render frames. All list rows are persisted; setup reconciliation verifies receipts 34,500,000.00 and current outstanding 24,500,000.00. Files/parameters remain ignored under test-results; no raw auth credentials are serialized. Timings are dated evidence, not a remote-network/cold-boot guarantee.

Design decisions: isolated schema on the existing PostgreSQL instance instead of polluting team data; same production application code for measurement; one-statement financial summary, no cache/second calculator; preserve selected IDs/names while filtering choices; current term policy remains authoritative for lifecycle rights.

Manual actions remaining: none requested from the user at this checkpoint. Development continues autonomously. Human presentation/shared understanding cannot be fabricated; prepare a concrete team demo/handoff before final delivery.

Known issues/remaining work: FINAL_ACCEPTANCE.md lists the still-open at-least-300-due mixed failure/retry batch; API allowlisted sorting/strict invalid filters/create Location; complete list URL/back persistence; form discard warnings beyond quote editor; final F01–F15/lifecycle/rejection-resubmission/permission/mobile/keyboard/action review; setup/demo/Git/secret checks; final full regression/security/build/performance rerun after those changes. Benchmark repeat setup now records actual API counts/current finance snapshot rather than assuming the active count remains fixed on future dates. The quoted 420-observation report remains the actual unchanged earlier dataset/build measurement.

Gate status: Phase 9 IN PROGRESS. Performance checkpoint PASS; full goal remains active. Next action: implement and verify the mixed 300-due billing recovery scenario, then finish the concrete API/UI contract gaps. Do not mark complete or reduce scope to the existing passing tests.

Current live handles: main backend exec 36942 / PID 30212; main frontend exec 36596. Benchmark backend exec 34352 / PID 30052; benchmark frontend exec 72412. Earlier server handles were stopped. Revalidate before restarting. Benchmark workers are temporary testing processes and should be stopped when no longer needed; no global automatic-billing worker is running against team data.


## Phase 9 recovery and API/UI contract checkpoint — 3 November 2026

Implemented: isolated committed mixed billing recovery; strict query validation and allowlisted stable sorting; create Location headers with readable resource endpoints; plan availability and discount eligibility filters; URL-preserved collection filters and stale-response guards; shared actionable field validation messages and accessible customer name/email/error markup. Customer drawer now warns before discarding entered values. Lifecycle/request confirmations and customer-safe reviewer display are being verified in the expanded subscription browser runner.

Files changed: backend API contracts/query ordering, collection endpoints and lifecycle serialization; API/large-batch/lifecycle tests; frontend API/URL/sort utilities, collection pages/components and customer form; collection/subscription journey runners; API and acceptance documentation. Existing team changes remain preserved.

Design decisions: unknown and repeated scalar query parameters fail 422; collection ordering uses fixed column maps with ID ties and nulls last; embedded creation Location points to its aggregate; registration Location points to authenticated identity. Discounts filter persisted revision/redemption eligibility rather than frontend guesses. Request review exposes reviewer display name and time, excluding identity IDs and account details.

Commands run / test results:
- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short` with `PYTHONPATH=.;backend`: **160 passed, one external Starlette/httpx test-client deprecation warning, 54.89 seconds**. This full checkpoint precedes the additional lifecycle reviewer assertion; subsequent targeted lifecycle suite: **12 passed**, same external warning.
- Large billing batch included in that full run: 325 subscriptions, 300 due, 600 expected due periods and ten previously billed paused/closed periods. Initial run committed 599 and recorded one deliberately injected failure; retry committed one; replay committed zero. All 610 final distinct identities and amounts reconciled, with no skipped/duplicate periods or unwanted draft/future charges. Measured processing 17.16 seconds; isolated test database only. Artifact: ignored `test-results/large-billing-batch.json`.
- Explicit installed Node/npm launcher `run build`: production build passed after API error/accessibility changes. Initial sandbox attempt failed EPERM; stopped the running frontend and rebuilt with filesystem access. Lifecycle confirmation/customer discard follow-up build is recorded in the next checkpoint when complete.
- `backend/.venv/Scripts/python.exe -u scripts/test_collection_journeys.py`: **five passed, zero skipped**. Includes actual backend invalid-email response, preserved input, SQL sort/detail-back navigation, deliberately delayed old response, payment source/back and invoice date/status/sort reload. First new test used the wrong Save Customer label; corrected after inspecting UI. Scoped the error assertion to the form alert because Next also has a route-announcer alert. Follow-up discard regression is pending rerun.
- `test_api_contracts.py`: **18 targeted passed** before the full 160-test run, covering Location/association, query/sort/filter validation, date availability and discount eligibility.

Manual actions remaining: none requested; continue authorized completion. Known remaining work: full form-discard/selector/action review, expanded rejection/resubmission browser verification, all final journey/mobile/keyboard/empty/error checks, fresh setup/demo/team handoff, Git/secret/artifact audit and final release regression/security/browser/performance reruns. Earlier dated 420-observation performance results remain a checkpoint, not a claim about the final release build.

Gate status: **Phase 9 IN PROGRESS**. Mixed billing, transport and collection navigation checkpoints pass; full acceptance is not yet complete. Main backend restarted as exec 27437 / PID 16044. Main frontend build exec 72606; revalidate handles after restart. Historical live-process references above are superseded.


### Follow-up UI verification — 3 November 2026

Implemented: lifecycle submissions show date/action/impact confirmation; request approval/rejection and customer cancellation require confirmation. Reviewed requests display reviewer name and business-timezone timestamp; no reviewer ID/email is exposed. Customer creation warns before discarding input, and links name/email labels and the error alert.

Commands/results: follow-up production `run build` **PASS**; `scripts/test_collection_journeys.py` **five passed, zero skipped**, now including dismiss/accept discard behavior; `scripts/test_subscription_journeys.py` **four passed, zero skipped**, covering reject/reason/reviewer/date, prefill and editable resubmission, cancel without service mutation, and later approval without premature state change. Backend lifecycle suite **12 passed** after reviewer assertion. The first prefill browser attempt used exact label text on a prefilled textarea; accessible textbox-role selection resolved it and the complete rerun passed. `git diff --check` initially found trailing spaces in recent customer/staff changes; corrected and rerun **PASS** (only Git line-ending notices).

Known remaining work and Phase 9 IN PROGRESS gate continue as listed in FINAL_ACCEPTANCE.md. Current main server handles: backend exec 27437 / PID 16044, frontend exec 72570; benchmark servers still run the older benchmark build and must be restarted/rebuilt for final measurement. No production/remote deployment or shared-history push occurred.


### Customer selected-product lookup checkpoint — 3 November 2026

Implemented: owned subscription change-options accepts a validated optional product_id, returning only active sales-safe product/variant fields. The customer editor hydrates selected products through this owned route when its current search excludes them. It does not call privileged catalog endpoints or expose cost/notes. Backend checks establish an actual 105-extra-product fixture where the selected product is beyond the first 100, resolves it by ID, rejects malformed UUIDs and refuses an unavailable subscription.

Commands/results: lifecycle suite **12 passed**, one external test-client warning; latest production build **PASS**; expanded subscription browser runner **four passed, zero skipped**, including selected product names surviving an excluding search before the rejection/resubmission/cancel/approval journey. Main backend now exec 53095 / PID 38924; frontend exec 81306. These supersede the previous handles.

Remaining selector work: admin configuration product/tax/plan choices still use initial-page fetches in product details, plan bundles, quotation template metadata/editor and discount product scope. Add usable search/pagination and retain selected records. Continue remaining discard/accessibility/action/final acceptance items in FINAL_ACCEPTANCE.md. Phase 9 remains **IN PROGRESS**; no broad completion claim is supported yet.


## Phase 9 admin selector and form-protection checkpoint — 3 November 2026

Implemented: shared bounded catalog choices with server search, 50-record pages, Load more, visible loading/error/retry and selected-record hydration through existing authorized detail APIs. Applied to product/plan tax assignment (create and edit), plan bundles, quotation template create/filter/editor plan and product choices, and discount create/revision product scopes. Closed dialog-only selectors do not issue background lookup requests. Search does not change stored selected IDs. Added accessible names to the affected selects.

Implemented form protection: create dialogs for products/plans/taxes/discounts/templates/staff, discount revision/deactivation, product/plan/template configuration and their child dialogs, customer edits, both role profiles/password dialogs, and subscription reason/review fields. Shared registration produces one native warning when multiple forms are dirty. Successful subscription commands/reviews clear consumed reasons. Product variant refresh now preserves unsaved parent product fields; its additional regression is pending the current build rerun. Payment close/Escape and invoice metadata/reason guards are added and awaiting their targeted final rerun.

Files changed: useCatalogChoices.ts, CatalogChoiceSearch.tsx, useUnsavedChanges.ts; affected admin and profile pages; subscription/invoice/payment components; test_admin_choices.py and test_form_protection.py; catalog/payment runner updates. No database schema or financial calculation change.

Commands/results verified so far:
- Explicit installed Node/npm production build after admin selectors and initial form protection: **PASS**. Follow-up variant/payment/invoice build is still being verified below.
- `scripts/test_admin_choices.py`: **six passed, zero skipped**, using 105 persisted synthetic products, 105 taxes and 105 plans. Confirms selected targets are outside the first 100; search and save retain correct IDs; third-page loading reaches unselected records; forced 503 and Retry retain checked tax assignments. Fixtures are explicitly named Selector QA, reused on repeat; no subscriptions/invoices/payments are seeded by this runner.
- `scripts/test_form_protection.py`: **four passed, zero skipped**, spanning nine form surfaces: six create dialogs, product configuration, nested plan/bundle forms and operational profile. Stay preserves values, discard leaves persisted data unchanged, nested guards prompt once and a successful save permits clean navigation. An additional variant-save preservation assertion was added after this run and is pending rerun.
- `scripts/test_subscription_journeys.py`: **four passed, zero skipped** against the initial expanded guards, including customer safe selected-product hydration and rejection/resubmission/cancellation/approval.
- `scripts/test_catalog_journeys.py`: complete A02–A09 workflow **PASS**, including variant +560, plan bundle, discount revision, template preview/activation and staff restriction. Initially it searched the background list while a creation POST/dialog was still settling, allowing a stale closure refresh to replace the test search. Waiting for dialog closure before searching resolves the runner race. Search now locates generated records instead of assuming they appear on the first page; choice lookups use their search controls. Earlier exact template-plan assertion was corrected to include the existing displayed fee.

Design decisions: one reusable lookup hook rather than fetching entire catalogs; independent selected-record hydration preserves archived/selected IDs for truthful form validation; active search results remain filtered. Existing backend authorization and input validation remain authoritative. Unsaved form snapshots compare semantic saved configuration, excluding lookup search text and record display metadata.

Known issues/remaining: pending latest variant/payment/invoice targeted checks; final mobile/keyboard/dialog labeling and empty/error-state review; fresh setup/demo/handoff; full final regression/security/performance reruns; Git/secret/artifact audit and integration commit. Code audit also found 25 trailing-whitespace lines in modified/new source files; cleanup and verification are pending. Gate remains **Phase 9 IN PROGRESS**, with no user action requested.


### Final checks for this UI checkpoint — 3 November 2026

Latest production build **PASS** after variant preservation and financial form guards. Latest `test_form_protection.py` **four passed**, now explicitly saving a variant while parent product fields are dirty and proving those fields survive; nested form prompt remains single and saved plan navigation is clean. Latest `test_payment_journeys.py` **four passed**, adding Close/Escape stay/discard checks, no payment on close, preserved reopened entry, and the existing committed-response-loss/reload/retry/settlement/receipt/mobile checks. Latest `test_billing_journeys.py` **four passed**, including correction editor save, confirm, actual Mailpit PDF attachment, customer PDF/print/mobile and cancelled invoice replay. No checks were skipped.

Payment form warns on dirty close/Escape and navigation/unload. Invoice corrections/reasons are guarded; confirm/cancel are disabled while correcting metadata, and the correction control explicitly closes the editor with discard confirmation. Successful financial actions clear consumed reasons. Updated architecture wording to describe actual controlled forms/page refresh implementation rather than claiming unused form/query libraries are in use.

Whitespace audit included modified and untracked Python/TypeScript source, finding 25 trailing-space lines in 12 files. Removed only trailing whitespace; `git diff --check` **PASS**, with Git's existing LF/CRLF notices. No new database migration or backend behavior was needed in this checkpoint. Full backend 160-test result remains the earlier dated checkpoint; latest application changes are frontend behavior.

Current main backend exec 53095 / PID 38924, frontend exec 47493. Benchmark ports still serve the previous benchmark build; final measurement requires rebuild/restart. Next concrete work: final accessible labels/dialog keyboard/focus and dirty browser-Back review; source-required validation/action gaps; check the temporary frontend health-check route against the exact 32-page inventory; fresh setup/demo/handoff; Git/secret audit; final combined regressions/security/performance. Phase 9 remains **IN PROGRESS**, active goal unchanged, no approval/user action required.


## Phase 9 accessibility, keyboard and inventory checkpoint — 3 November 2026

Implemented: exact 32-template source inventory restored by removing the temporary frontend health-check page; backend health/readiness remain documented. Connected 86 labels, named collection/pagination/remove controls, corrected low-contrast text and made 17 horizontal table regions focusable. Eighteen overlay dialogs now share native dialog semantics, heading names, inert workspace, busy handling, guarded Escape and focus restoration. Shared focus cycling covers these dialogs and payment entry/details. Dirty forms handle cancellable same-document Navigation API traversals without adding fake history entries.

Files changed: shared Modal/dialogFocus/unsaved utilities, affected page/form/table components, pinned development axe-core dependency and lockfile, independent main/benchmark TypeScript configs, accessibility/keyboard/focused-review runners, browser error-redaction helper and regression, README and accessibility/demo/acceptance documents. Removed only the unplanned frontend diagnostic route. Existing teammate work remains preserved.

Commands/results:
- Production build via installed Node/npm **PASS**, build `MUvzCrTuHQwYrFpv67eLc`. An initial build failed because the old benchmark-generated health-check type referenced the removed route. Independent tsconfig.json/tsconfig.benchmark.json configurations resolve cross-build stale types; neither build skips type checking.
- `scripts/audit_accessibility.py`: **84 observations, zero WCAG A/AA rule violations, zero page overflows**; all 32 templates plus ten staff variants at 1440/390 widths, Chrome 156.0.8078.76, axe 4.14.0. Timestamp 2026-11-03T00:36:02Z. Initial 59-rule failure and intermediate four-button failure artifacts are retained.
- `scripts/test_keyboard_journeys.py`: **three passed, zero skipped**. Twelve opened dialogs at both widths pass automated checks, Tab/Shift+Tab containment, dirty Escape stay/discard and trigger focus restoration. Browser history cancellation preserves product edits; accepted Back and Forward restore filters/persisted values. The first native-only focus test failed on document-body focus; shared explicit cycling fixes it and the complete rerun passed.
- `scripts/review_accessibility_incomplete.py`: **eight observations passed**, classifying 77 glyph/scroll-clipped contrast targets. Minimum measured contrast **4.548:1**, all above 4.5; keyboard horizontal scrolling verified for all four table observations. Rendered mobile password/table screenshots visually inspected. No axe rules suppressed. Report records the known eight incomplete checks separately from violations.
- `scripts/test_payment_journeys.py`: **four passed**, including entry/drawer focus checks, dirty Close/Escape, no payment on close, actual committed response loss and same-key reload recovery, receipt/mobile behavior and final two-payment settlement. One preceding verification GET failed ECONNRESET after settlement; API process remained live/healthy. Added bounded retry for that read only and reran the entire payment suite successfully.
- `backend/tests/test_browser_log_safety.py`: **one passed**, existing external Starlette/httpx warning. Default failed browser trace had printed a synthetic session cookie; revoked and verified exactly that synthetic admin session using its customer/invoice time interval. No financial records changed. Shared runner errors now redact request credentials/reset tokens/passwords and omit source lines. No credential is copied into these documents. Full backend checkpoint remains the prior 160-test run; the new test is targeted evidence, not a claimed full 161-test run.
- Frontend dependency install: one development package added; npm reported zero vulnerabilities. `git diff --check` **PASS**, only existing LF/CRLF notices.

Design decisions: native modal behavior plus shared keyboard cycling; standard browser cancellation capability rather than history sentinels; actual rendered contrast/keyboard review for incomplete axe cases; separated generated build types; test-only axe injection uses CSP bypass and does not replace security verification. Details and browser limitations are in ACCESSIBILITY_VERIFICATION.md.

Prepared EVALUATOR_DEMO.md with a 12-minute role walkthrough, preflight, exact INR 2,888.64 worked invoice, database/recovery evidence and real team ownership guidance. Combined rehearsal remains pending; human participation is not fabricated.

Manual actions remaining: none requested from the user. Known remaining work: final operational lifecycle and error/empty-state journeys; required-text/numeric-boundary and frontend monetary precision review; fresh setup/lint/tooling; combined demonstration rehearsal; Git/secret/artifact audit and integration commit; final full security/regression/performance reruns. Existing 420-observation performance results remain historical until the release build is benchmarked again.

Gate status: **Phase 9 IN PROGRESS**; overall goal active. Current main backend exec 53095 / PID 38924 and frontend exec 94299 / PID 22500. Benchmark processes still serve the older build; rebuild/restart them for final measurement and stop temporary benchmark services afterward.


## Phase 9 input validation and decimal integrity checkpoint — 3 November 2026

Implemented: request-only meaningful required-text validators trim names/types/classifications and reject whitespace/null without changing credential bytes or historical response DTOs. Shared monetary inputs enforce finite NUMERIC(18,2) decimal strings; JSON numbers are rejected under the documented string contract. Percentages support four decimal places, quantities/caps fit PostgreSQL INTEGER, and plan payment/template validity inputs align with commercial draft limits. Calculation overflow raises a safe pricing error before quantization/financial writes. Product base-price/variant writers lock the parent first and enforce effective price bounds on both edit paths. No schema migration is required: these guards enforce existing storage/domain constraints.

Frontend monetary values now remain strings through create/edit/revision hydration and API payloads. A shared decimal parser and BigInt minor-unit helpers provide exact display, dirty comparisons, variant and payment balance previews; report aggregate display allows totals larger than one stored amount. Variant preview uses the saved product base, while saving a variant preserves pending parent edits. Removed remaining legacy USD copy, enabled four-place percentage entry and replaced exponent-truncating integer parseInt calls in affected forms. Frontend package explicitly declares its existing ES module convention; decimal tests no longer emit the ambiguous-module warning.

Files changed: core/limits.py, schemas/validation.py and affected request models, financial_calculator.py, product write endpoints; test_input_validation.py/test_catalog_concurrency.py; frontend decimal.ts/utils, catalog/pricing/payment form surfaces, package test command and native decimal tests; test_money_journeys.py; API/README/acceptance evidence. Existing teammate changes remain preserved.

Commands/results:
- New negative HTTP and independent PostgreSQL tests: **27 passed** before the full rerun. Includes blank names, null edits, non-finite/over-scale/out-of-range values, exact maximum storage round-trip, preserved password whitespace and computed overflow. The race observes the second connection waiting on a PostgreSQL Lock, then proves a valid individual base/variant edit pair cannot commit a negative combined price.
- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short`, PYTHONPATH=.;backend: **188 passed, one external Starlette/httpx test-client warning, 216.45 seconds**. Includes all financial batch/concurrency regressions. Only a semantically identical explicit constant re-export changed after this run.
- Installed Node/npm `run build`: latest production build **PASS**, including the ES module declaration and exact monetary rendering.
- `npm run test:decimal`: **four passed**, no warnings/skips. Checks 90071992547409.93 (whose cent can change through floating-point conversion), one-cent differences near the storage maximum, signed adjustments, invalid inputs and larger reporting aggregates.
- Native Chrome number-input probe preserved 90071992547409.93 and 9999999999999999.99 with valid 0.01 steps. Monetary controls retain their input strings.
- `scripts/test_money_journeys.py`: **five passed, zero skipped**. Inspected actual browser POST/PATCH string payloads and PostgreSQL-backed responses for product/cost/plan/discount/threshold values; edit hydration and display remain exact. Saving a cent variant uses the saved base, retains a pending cent-only parent edit, and cancelled navigation preserves it. Mobile product body does not overflow. Whitespace-only customer creation returns field feedback, preserves email and creates no record. Synthetic large-price records are archived/disabled on success or failure via this run's unique name; failed earlier locator runs were also archived explicitly.
- Initial money runner used creation labels on edit pages; corrected to existing Base Sales Price/Base Fee labels after inspecting rendered accessibility snapshots. These were runner failures; exact stored/input values were already visible. The entire corrected runner passed.
- `scripts/test_catalog_journeys.py`: complete A02–A09 regression **PASS**, including +560, plan bundle, discount revision, template preview/activation and staff restriction.
- `scripts/test_payment_journeys.py`: **four passed, zero skipped**, retaining keyboard/Close/Escape, committed response-loss recovery, receipt/mobile and exact final settlement checks.
- `git diff --check`: **PASS**, existing LF/CRLF notices only.

Design decisions: enforce decimal-string requests rather than attempting to recover already-lost floating-point input; use standard BigInt for browser previews instead of another arithmetic dependency; retain backend Decimal authority; bound inputs to existing database types; serialize catalog cross-row invariants at their parent record. Password normalization is deliberately excluded and regression-tested.

Manual actions remaining: none requested. Known remaining work: complete operational lifecycle UI and integrated F01–F15/error/empty-state review; fresh setup and frontend lint/readability/tooling verification; combined evaluator walkthrough rehearsal; Git/secret/artifact audit and integration commit; final complete security/browser/performance reruns after remaining changes. Previous accessibility/performance reports remain dated checkpoints, not claims for this new release build.

Gate status: **Phase 9 IN PROGRESS**, overall completion goal active. Current main backend exec 11699 / PID 37816, frontend exec 90474 (revalidate PID before restart). Benchmark services still run the older source/build and need refresh for final measurement.


## Final local delivery — 3 November 2026

**Implemented:** all remaining phases and 32 planned templates. The final review added complete operational lifecycle journeys, proposed/retained policy summaries, stable editable-row identities and history IDs, explicit button/form behavior, one shared keyboard-focusable table region, exact decimal handling, strict meaningful input/boundary validation and a common session-bound CSRF/Origin policy. Dependent quotation choices now load when relevant; the editor keeps server-side search and selected records beyond the first 100.

**Files changed:** domain APIs/services/models/migrations/tests; frontend pages/shared components and validation utilities; lifecycle, security, setup, browser and benchmark runners; pinned test/lint dependencies; README/BUILD_GUIDE and the source, API, operations, security, accessibility, performance and evaluator handoff reports. The sole removed feature page is the unplanned frontend health-check. Existing teammate code/history remain preserved. No extra product pages or external data platform were added.

**Design decisions:** native PostgreSQL is authoritative; financial Decimal snapshots, transactions, locks, uniqueness and immutable payments remain central. The scheduler calls the shared billing engine. Cookie/session-bound validation and Origin checks are consistent across protected POST/PATCH operations, including pricing preview. Biome replaces the temporary unsupported/advisory-bearing ESLint tree; recommended React/Next checks remain enabled. Intentional table focus has one narrow documented lint exception backed by rendered/keyboard checks. No financial records were deleted during cleanup.

**Commands run / results:**

- `PYTHONPATH=.;backend` and `backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short`: **194 passed, one external Starlette/httpx deprecation warning, 58.74 seconds**. The first security run demonstrated six failures; the fix passed all six. An initial full run caught eight old preview tests without the newly required CSRF header; their legitimate headers were updated without weakening the financial assertions, then all 194 passed.
- Explicit installed Node/npm launcher `run build`: main build **DO6xl0qQyiLmkLAZK5l3t**, benchmark build **mD2vhGRAnHjCYxDTmLLIZ**, both PASS. `npm run lint`: **68 files, zero diagnostics**; `npm run test:decimal`: **four passed**. Clean `npm ci` passes with zero vulnerabilities.
- Core browser: **five passed**; catalog A02–A09: **complete PASS**, now requiring tax assignment and exact tax-inclusive estimate; subscription quotation/revision/request: **four passed**; operational lifecycle: **four passed**; billing/PDF/Mailpit/cancellation/replay: **four passed**; payment/lost-response recovery: **four passed**; reporting: **three passed**; collection history/stale-response: **five passed**. No skipped journeys.
- Keyboard: **three passed**, including twelve opened-dialog scans and focus/dirty Back; dirty forms: **four passed** across nine surfaces; exact-money browser: **five passed**; hardening: **four passed**, including actual scoped worker replay, failed-logout recovery and 13 anonymous-denial probes. Large-selector/root/navigation checks: **three passed**.
- `scripts/audit_accessibility.py`: **84 observations, zero WCAG-rule violations, zero overflows**, main build above, Chrome 156.0.8078.80, timestamp 05:54 UTC. Rendered incomplete review: **eight passed**, 77 targets, minimum contrast 4.548:1; keyboard scrolling verified. Password/table screenshots visually inspected. This is scoped application verification, not an external accessibility certificate.
- `scripts/test_evaluator_demo.py`: **linked real-UI rehearsal PASS**, final guard, 06:18 UTC. It creates the taxed catalog/template via UI, verifies invalid-email feedback, registers one customer, prepares/confirms/activates the quote as staff, bills/confirms/sends a real Mailpit PDF, records INR 1,000.00 and 1,888.64, downloads owned documents, reviews/resubmits/cancels a request, reconciles reports and repeats billing without duplication. Recorded invoice `afecc8e3-ba2c-461a-854d-b23fbb2c028b`, subscription `d1003d15-6c8e-46ac-aa48-a49e7e25dee4`; received 2,888.64, outstanding zero, two immutable payments. No human participation is fabricated.
- Empty new Python environment installs both pinned runtime and browser-test manifests; `pip check` passes. Fresh-environment `scripts/verify_fresh_setup.py`: **38 empty tables, head e90c51fa2b73, no model drift, initial auth/staff/catalog API PASS**, own temporary schema removed and existing test rows unchanged. Circular FK metadata ordering is explicit; no storage migration was needed. Native database role/isolation checks pass. README now includes first-time private provisioning and production startup.
- `scripts/audit_route_security.py`: **68 protected domain routes, 37 POST/PATCH operations, zero missing identity/CSRF/Origin dependencies**. Runtime role/ownership tests are separate. The scanner handles the pinned framework's lazy router representation and refuses an empty enumeration.
- Bandit: **zero findings, zero skipped tests**. Backend runtime and runtime-plus-browser pip audits: **no known vulnerabilities**. Full npm audit: **zero vulnerabilities**. The temporary lint installation's 14 development advisories were removed with the legacy tree; they are retained as debugging history, not hidden.
- Final guarded cold-client benchmark: **420 observations, all under two seconds**. C1 p50/p95/max **185.25 / 462.23 / 545.13 ms**; C5 **499.90 / 827.78 / 1,078.33 ms**. Warm-client matrix: another **420 passed**, C1 **96.32 / 393.39 / 511.53 ms**, C5 **182.96 / 500.67 / 567.54 ms**. Both use source SHA-256 `6b11d573ca0511c883a032a475f3b2bc75f118ab5b4644d5a8f58e4ee5ca3952`, 5,000 subscriptions / 50,000 invoices / 100,000 payments and no competing verification workload. An earlier I05 sample failed at 2,036.15 ms; its artifact is retained, and substantive choice-loading changes reduced the focused maximum to 555.67 ms before complete reruns passed. Servers/DB caches are warm; cold/warm browser caches are disclosed separately.
- Source/action audit: **32 feature templates + root redirect, 174 buttons, 27 forms; zero missing/extra pages, unbound button/form actions or permanent disabled placeholders**. This wiring check complements runtime flows. Original four-page PDF reread; SHA-256 matches the planning record. All R01–R24/E01–E11 are mapped in FINAL_ACCEPTANCE.md.
- Candidate Git private-value/password/credential-signature/generated-artifact scan: **zero issues**, 255 text files / six configured private values; local Markdown links valid. `git diff --check` passes (existing LF/CRLF notices only). The original unchanged initial migration has two baseline trailing-space lines; no changed/new source introduces whitespace errors.

**Retained debugging evidence:** wrong creation/edit selectors, the old checklist-color assertion, early API reads before quote issuance completed, first-page assumptions after plan creation, equal total/paid mobile text, Windows stale-build/process locks, genuine shared-IP authentication throttling and the failed performance sample were diagnosed. Browser helpers now report real status, respect confirmed Retry-After before one retry and preserve inputs; they do not bypass rate limits or replay uncertain writes. One edit script's Windows encoding mistake was reversed and UTF-8/currency text reverified before the successful builds. Raw credentials were not copied into these reports.

**Manual actions remaining:** use OPERATIONS.md to start/supervise API, frontend, Mailpit and the scheduler in the team's own terminals; assign actual speakers and understand the worked flow. These are normal operation/presentation responsibilities, not missing application implementation. Temporary benchmark services are stopped after final verification. No deployment, remote push, fabricated authorship or presenter approval is claimed.

**Known issues / limits:** one external test-client deprecation warning; all application tests pass. Results describe the recorded local Windows/PostgreSQL/Chrome environment, not cold server boot, remote-network performance or independent security/accessibility certification.

**Gate status:** **Phase 9 PASS; all phases 0–9 delivered and verified locally.** See FINAL_ACCEPTANCE.md, PERFORMANCE_VERIFICATION.md and EVALUATOR_DEMO.md. Integration branch: codex/finish-brightloop; the final commit is recorded by repository history.
