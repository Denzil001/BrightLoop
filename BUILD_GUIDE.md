# BUILD_GUIDE.md - Brightloop Implementation Roadmap

This guide specifies the implementation sequence, business defaults, phase gates, and performance targets for Brightloop.

## 1. Sequence and scope

Ten implementation phases (0 through 9) partition the project. Phase gates are hard stops: do not begin phase N+1 until phase N meets its gate.

### Phase 0 - Planning, architecture, and database design

**Work:** document all schema models, constraints, data types, indexes, and cascades. Document the API route structure, status codes, and error response shapes. Propose initial business defaults for D01-D10 in `docs/business-rules.md`. Document the 32 page templates, their routes, permitted roles, and primary actions in `docs/USER_FLOWS.md`.

**Gate: PASS.** Phase 0 documentation completed and explicitly accepted by the team (decisions D01-D10 confirmed).

### Phase 1 - Foundation, schema, and layout shell

**Work:** initialize the repository with the agreed stack. Configure PostgreSQL connection pools for development and disposable test databases. Create initial Alembic migrations for all models. Add check constraints, unique constraints, and foreign key cascades. Add health and readiness endpoints. Create the shared responsive layout shell with navigation, role indicator, and unauthenticated state.

**Pages delivered:** Shared responsive layout shell, health/readiness endpoints, unauthenticated landing/login redirect. Hide navigation links to unbuilt features.

**Gate: PASS.** Alembic migrations run cleanly against empty databases. Database constraints verified with PostgreSQL test cases (non-negative prices, valid tax rates, invoice identity, payment restrictions, financial deletion protection, partial unique indexes for single draft agreement version, accepted version effective date uniqueness, and single open pause per term). Health endpoints return 200 with structured JSON and database latency. Frontend layout compiles, renders responsively, and hides unbuilt navigation.

### Phase 2 - Identity, staff and customer records

**Depends on:** Phase 1.

**Work:** controlled admin bootstrap; atomic signup/customer creation; normalized unique email; Argon2id; login/logout and revoked sessions; password reset and safe existing-customer linking via local SMTP; role and ownership dependencies; authentication rate protection; CSRF strategy. Create minimal role shells, admin staff management, operational customer creation/search/detail/edit and own-profile/password forms. Deactivated staff loses active sessions.

**Pages delivered:** P01–P04, I02–I03, I10, A01, C07. Until later dashboards exist, authenticated landing redirects to a delivered permitted page; no dead dashboard links. Future-domain customer tabs remain absent until delivered.

**Gate: PASS (Review corrections applied).** Delivered pages P01–P04, I02–I03, I10, A01, and C07. Automated Playwright browser tests (`scripts/test_browser_journeys.py`) verified all 5 end-to-end user journeys (F01 atomic registration, F01 unlinked customer email verification and linking via Mailpit, F02 forgot/reset password with session revocation via Mailpit, F03 admin staff provisioning and deactivation with instant session revocation, and customer directory CRUD/search/detail editing). Pytest suite expanded to 37 tests (100% pass) verifying fresh-browser CSRF token context, pre-auth CSRF challenge binding & rotation on login, Origin validation across public auth mutations and logout, CSRF required on logout, Starlette HTTP exception header preservation (`Retry-After` on 429), and truthful email delivery failure recording (`AuthChallenge.delivery_status` and `delivery_attempts` with check constraint, 503 on registration delivery failure without false success claims, generic 202 on forgot-password without account leakage, and automated recovery on retry). Undelivered routes remain hidden.

### Phase 3 - Catalog, pricing rules and templates

**Depends on:** Phase 2.

**Work:** product/variant CRUD and archiving; plan fees/included lines, four intervals, quantity/availability/policy flags; tax rules/applicability; discount CRUD/scope/eligibility; template plan/product lines and validity days. Implement the shared Decimal pricing service and backend field validation. Add real admin forms and operation-only catalog reads for staff.

**Pages delivered:** A02–A09 (`/app/products`, `/app/products/[productId]`, `/app/plans`, `/app/plans/[planId]`, `/app/taxes`, `/app/discounts`, `/app/quotation-templates`, `/app/quotation-templates/[templateId]`).

**Gate: PASS.** Catalog Playwright journeys were rerun successfully on 1 November 2026; see DEVELOPMENT_STATUS.md for actual commands. Verified requirements: admin-only writes; correct 560 variant adjustment; allowed zero prices versus invalid negatives; all interval/availability/policy fields persist; tax and discount bounds/thresholds/caps validated; templates populate valid lines; pricing unit tests and PostgreSQL constraints pass; admin browser CRUD works. Test pricing previews without invoice writes. Historical invoice/redemption integration checks are deferred specifically to Phase 5.

### Phase 4 - Quotation and subscription lifecycle

**Depends on:** Phase 3.

**Work:** create subscription draft; template-based quote editor; immutable quote versions/expiry; confirmation/activation; agreed product/plan/tax context and price snapshots; lifecycle actions; customer request submission/cancellation and staff approve/reject workflow; dated plan-policy enforcement; agreement versions for renewals/add-on changes. Show pending and completed changes on the same subscription detail page. One subscription exists from Draft; confirmation accepts that agreement version rather than creating a duplicate subscription.

**Pages delivered:** I04–I06, C02–C03 (`/app/subscriptions`, `/app/subscriptions/new`, `/app/subscriptions/[subscriptionId]`, `/portal/subscriptions`, `/portal/subscriptions/[subscriptionId]`).

**Gate: PASS (1 November 2026).** Full backend suite: 82 passed; production build passed; staff/customer Playwright subscription journeys: 3 passed, zero skipped, including two disjoint discount rules and mobile overflow assertion. See DEVELOPMENT_STATUS.md for commands and deferred phase dependencies. Verified requirements: subscription created in draft state; quotation confirmation accepts agreement version; price snapshots preserved; customer ownership verified; staff-only approvals; customer cancellation of own requests; dated pause/resume; renewal/add-on agreement versions; accepted plan flags, quantities and service/boundary dates enforced; transitions tested with PostgreSQL persistence; customer/staff browser tests pass. The shared event applier is tested in this phase; billing invokes it chronologically in Phase 5 and scheduling invokes billing in Phase 8. Grace periods, notice policies and minimum service durations are not invented beyond accepted rules.

### Phase 5 - Billing engine, invoices, and documents

**Depends on:** Phase 4.

**Work:** one tested billing service plus CLI/admin trigger; per-period transactions, locks and unique invoice period; bounded backlog recovery; start/term/change eligibility; invoice/customer/company/line/tax/discount snapshots; capped discount redemption; invoice confirm/cancel; invoice number/due dates; local PDF/print document and configured SMTP send/retry. Persist run outcomes, per-period errors and delivery attempts. SMTP reset already exists from Phase 2; reuse its adapter.

**Pages delivered:** I07–I08, A11, C04–C05 (`/app/invoices`, `/app/invoices/[invoiceId]`, `/app/billing-runs`, `/portal/invoices`, `/portal/invoices/[invoiceId]`).

**Gate: PASS (2 November 2026).** Full PostgreSQL suite: 100 passed; production build passed; live billing browser journeys: four passed, zero skipped, including real Mailpit PDF attachment and mobile/print checks. Independent-connection tests prove same-period uniqueness and a global one-use discount race. PDF samples were rendered and visually checked, including long descriptions across three pages. Verified requirements: single period unique constraint enforced; billing recovery catches missed periods; discount redemption limits respected; no double-advance; concurrent runs cannot duplicate invoices; document generation matches database state; retry handles transient failure; financial integration tests pass.

### Phase 6 - Payments, ledger, and reconciliation

**Depends on:** Phase 5.

**Work:** manual payment recording; payment methods/references; customer balance tracking; partial and final payments; unique payment request key; immutable ledger view; payment receipt documents. (No refunds, payment edits, or replacements under D09 initial scope).

**Pages delivered:** I09, C06 (`/app/payments`, `/portal/payments`).

**Gate: PASS (2 November 2026).** Full backend suite: 120 passed; production build passed; payment browser journeys: three passed, zero skipped, including a committed payment whose response is lost followed by reload/retry. Five independent-connection race cases verify settlement, overpayment, same-key replay, cross-invoice key collision and cancellation serialization. Verified requirements: payments serialized per invoice; same-key/same-payload retries return the original payment; changed payload conflicts; overpayment rejected; balances reconcile with payment sum; immutable payment records; payment receipts generated; Playwright payment tests pass.

### Phase 7 - Analytics, reports, and operational overview

**Depends on:** Phase 6.

**Work:** operational and customer overview dashboards; finance reporting; active subscriptions; cash received in range; current outstanding and overdue totals/counts; audit events; SQL aggregates with matching filters and source drill-down. Follow A10/I01/C01 in USER_FLOWS.md; no MRR/ARR claims or speculative export/chart scope.

**Pages delivered:** I01, A10, C01 (`/app`, `/app/reports`, `/portal`).

**Gate: PASS (2 November 2026).** Full PostgreSQL suite: 126 passed; production build passed; three reporting browser journeys passed, zero skipped. SQL summary for the filtered browser sample: 9.2 ms (not the Phase 9 page-load benchmark). Verified: operational and customer dashboards load dynamic aggregates; financial report reconciles to persisted records; filters and source lists match metric definitions; query time within performance budget; audit log events intact.

### Phase 8 - Scheduled billing, hardening, and operational readiness

**Depends on:** Phase 7.

**Work:** scheduled billing invocation (adding automated scheduler to the tested billing engine/CLI as planned in architecture and verified in PLANNING_VERIFICATION); comprehensive penetration testing; OWASP Top 10 verification; rate limiting verification under load; timezone edge cases (month-end, leap year, DST); transaction isolation level verification; session revocation under concurrency; CSRF edge cases.

**Pages delivered:** none (hardening existing pages and operational scheduler infrastructure).

**Gate: PASS (2 November 2026, local application verification).** Full PostgreSQL suite: 138 passed; production build passed; core browser journeys five passed, hardening journeys four passed and billing regression four passed, zero skipped. Bandit and pinned dependency audits have no findings. Scope/limits are documented in SECURITY_VERIFICATION.md; no external penetration-test or production-network certification is claimed. Verified: scheduler triggers due billing runs without duplication; OWASP checklist passed; no information leaks in error responses; rate limits hold under parallel requests; timezone calculations verified across 28/29/30/31-day transitions; concurrent sessions properly revoked; security scan clean.

### Phase 9 - Performance benchmarking and evaluation readiness

**Depends on:** Phase 8.

**Work:** generate benchmark dataset (propose 5,000 subscriptions, 50,000 invoices, 100,000 payments); run page load benchmarks against all 32 templates; measure p50/p95/max latencies under concurrency; tune SQL queries and indexes; optimize frontend bundle; verify all 15 user journeys end-to-end; prepare evaluation demonstration script.

**Pages delivered:** all 32 verified against performance budget.

**Gate: PASS (3 November 2026, local delivery).** Final backend: 194 PostgreSQL tests pass; production build, 68-file lint and four decimal tests pass. All 84 desktop/mobile accessibility observations have zero violations/overflow; incomplete cases and keyboard behavior are reviewed. The linked evaluator UI rehearsal passes through actual Mailpit delivery, partial/final settlement, requests, reports and safe replay. All 840 cold/warm-client guarded-source browser observations over all 32 templates and staff variants are under two seconds, maximum 1,078.33 ms. Clean dependency/empty-schema setup, route-policy, private-file and source/action audits pass. See FINAL_ACCEPTANCE.md, PERFORMANCE_VERIFICATION.md and DEVELOPMENT_STATUS.md for commands, failures, limits and reproduction. Actual future human presentation participation is not fabricated.

## 2. Business defaults accepted in Phase 0

The following decisions D01–D10 were formally accepted by the team on 31 October 2026 without modification:

| Decision | Accepted Default | Implementation Rule |
|----------|-----------------|---------------------|
| D01: Customer Login & Linking | One CUSTOMER login per customer; verified linking to pre-existing operational records. | Atomic customer/user registration for new users; pending signup with hashed expiring verification token and email delivery via Mailpit before linking existing customer records. |
| D02: Change Requests & Review | Customers request pause/resume/renew/add-on changes; staff/admin reviews. | Self-service lifecycle changes create pending requests (`PENDING`); staff/admin reviews and approves or rejects at approved future boundaries. No direct customer modification of financial terms. |
| D03: Plan Fee & Seat Entitlement | A plan fee includes its minimum seat quantity; explicit excess-seat unit price; separate add-ons. | Plan defines `base_fee`, `minimum_seats`, and `extra_seat_unit_price`. Subscription explicitly stores `seat_quantity >= minimum_seats`. Excess-seat line (`seat_quantity - minimum_seats`) * excess price. Included items are descriptive entitlements at ₹0.00. |
| D04: Currency & Amounts | INR (`₹`), two-decimal amounts, positive integer quantities, exclusive percentage tax. | All monetary columns in PostgreSQL use `NUMERIC(18, 2)`. Quantities are positive integers (`INTEGER`). Transmitted as decimal strings. Tax calculated on discounted line bases. |
| D05: Price & Term Freezing | Freeze sales prices and tax rates in the accepted agreement; changes require a new agreed version. | Commercial terms (agreed unit price, tax rate snapshots) are frozen upon quotation confirmation / agreement version acceptance. Catalog updates apply only to future drafts. |
| D06: Discount Terms & Stacking | Pin assigned discount terms; no overlapping discounts on the same charge; eligibility at period start. | Discount assignment pins immutable `DiscountRevision`. Whole-subscription discount conflicts with product-scoped discounts; product rules can only coexist on disjoint charge lines. No discount stacking on the same line. Eligibility evaluated at period start. |
| D07: Timezone & Payment Terms | Asia/Kolkata billing dates; calendar anchors; advance billing; default 15-day payment terms. | All business-date calculations use `Asia/Kolkata` timezone. Month-end calendar anchoring clamps to month end. Advance billing at period start. Default due date = invoice date + 15 days. |
| D08: Boundary Changes & Pausing | Boundary-only voluntary changes; pause extends term; resume resets anchor; expiry partial period prorated. | Changes take effect at period boundaries. Pause opens an interval and stops service clock; resume shifts expiry by exact paused calendar days and establishes new anchor. Final partial period prorated actual/actual days. |
| D09: Cancellation & Settlement | Cancel only unpaid invoices; preserve period/discount consumption; no replacement/refund/payment edits initially. | Invoices can only be cancelled if completely unpaid. Cancelled periods remain consumed (no re-billing same period, no discount refund). Overpayment rejected. No payment editing/deletion/refunds initially. |
| D10: Infrastructure & Isolation | Single company, local PostgreSQL plus Docker Mailpit, no online gateway. | Native/local PostgreSQL persistence with strict test-database isolation; Docker Mailpit for local SMTP testing; manual payment recording; no external BaaS or third-party payment gateways. |

## 3. Page inventory cross-reference

The 32 page templates from `docs/USER_FLOWS.md` map to implementation phases as follows:

| Template | Path | Role | Phase Delivered |
|----------|------|------|-----------------|
| P01 | `/login` | Public | Phase 2 |
| P02 | `/register` | Public | Phase 2 |
| P03 | `/forgot-password` | Public | Phase 2 |
| P04 | `/reset-password` | Public | Phase 2 |
| I01 | `/app` | Staff/Admin | Phase 7 |
| I02 | `/app/customers` | Staff/Admin | Phase 2 |
| I03 | `/app/customers/[customerId]` | Staff/Admin | Phase 2 |
| I04 | `/app/subscriptions` | Staff/Admin | Phase 4 |
| I05 | `/app/subscriptions/new` | Staff/Admin | Phase 4 |
| I06 | `/app/subscriptions/[subscriptionId]` | Staff/Admin | Phase 4 |
| I07 | `/app/invoices` | Staff/Admin | Phase 5 |
| I08 | `/app/invoices/[invoiceId]` | Staff/Admin | Phase 5 |
| I09 | `/app/payments` | Staff/Admin | Phase 6 |
| I10 | `/app/profile` | Staff/Admin | Phase 2 |
| A01 | `/app/staff` | Admin | Phase 2 |
| A02 | `/app/products` | Admin | Phase 3 |
| A03 | `/app/products/[productId]` | Admin | Phase 3 |
| A04 | `/app/plans` | Admin | Phase 3 |
| A05 | `/app/plans/[planId]` | Admin | Phase 3 |
| A06 | `/app/taxes` | Admin | Phase 3 |
| A07 | `/app/discounts` | Admin | Phase 3 |
| A08 | `/app/quotation-templates` | Admin | Phase 3 |
| A09 | `/app/quotation-templates/[templateId]` | Admin | Phase 3 |
| A10 | `/app/reports` | Admin | Phase 7 |
| A11 | `/app/billing-runs` | Admin | Phase 5 |
| C01 | `/portal` | Customer | Phase 7 |
| C02 | `/portal/subscriptions` | Customer | Phase 4 |
| C03 | `/portal/subscriptions/[subscriptionId]` | Customer | Phase 4 |
| C04 | `/portal/invoices` | Customer | Phase 5 |
| C05 | `/portal/invoices/[invoiceId]` | Customer | Phase 5 |
| C06 | `/portal/payments` | Customer | Phase 6 |
| C07 | `/portal/profile` | Customer | Phase 2 |

## 4. Evaluation and acceptance gates

Every phase gate requires documented evidence before advancing:

1. **Commands executed:** the exact shell commands run.
2. **Test output:** the complete test runner output including count of passed/failed tests.
3. **Database state:** verification that migrations ran and constraints hold in PostgreSQL.
4. **Browser verification:** Playwright test results for delivered user journeys.
5. **No regressions:** all previous phase tests continue to pass.

**Mandatory performance evidence:** propose 5,000 subscriptions, 50,000 invoices and 100,000 payments. Agree actual fixture counts, hardware, browser, local/deployed topology and representative concurrency in Phase 0. Time navigation until primary content is usable for the 32 templates using authorized representative accounts/records; include filtered/paginated large collections. Record cold/warm results, sample counts, p50/p95/max and failures. Every sampled designated page load must be under two seconds; p95 alone does not satisfy the literal PDF target. Treat unmeasured environments as unknown, not proven. Bulk generation throughput is reported separately from interactive page latency.

**Final demonstration:** admin configures product/variant/plan/tax/discount/template -> customer registers -> staff prepares and confirms quote -> activate subscription -> run due billing -> confirm/send/print invoice -> partial then final payment -> customer checks owned history -> admin report reconciles -> rerun billing safely -> show a customer change request and plan-policy validation.

## 5. Execution and handoff

Use a focused feature branch per phase or coherent subfeature, with another teammate reviewing code and evidence. Keep phase gates sequential even when team members divide the current accepted phase. No particular agent tool is required.

After each phase provide: Implemented; Files changed; Design decisions; Commands run; Test results; Manual actions remaining; Known issues; Gate status. Report the exact repository commands that were actually run. A pending human review or required external setup stays visible; passing documentation checks does not imply application acceptance.

**Current state:** All phases 0–9 have verified local delivery gates. The final source-to-evidence audit is [docs/FINAL_ACCEPTANCE.md](docs/FINAL_ACCEPTANCE.md), and the reproducible team walkthrough is [docs/EVALUATOR_DEMO.md](docs/EVALUATOR_DEMO.md). Earlier per-phase test counts describe their historical checkpoints.
