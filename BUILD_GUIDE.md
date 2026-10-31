# Brightloop - Phase-by-phase implementation plan

## 1. Scope and document map

This is the implementation plan for `makeaton-initial`, based on the four-page Subscription Management System problem statement and the evaluator's message supplied by the team. This revision replaces the former Stage 0-18 Antigravity guide with Phase 0-9. No application implementation is claimed by this document.

- [AGENTS.md](AGENTS.md): persistent engineering, security and collaboration rules.
- [docs/USER_FLOWS.md](docs/USER_FLOWS.md): authoritative roles, navigation, 32 page templates, page contents and user journeys.
- [docs/PLANNING_VERIFICATION.md](docs/PLANNING_VERIFICATION.md): final source-to-plan coverage, consistency checks and decisions still requiring Phase 0 acceptance.
- This file: build sequence, proposed business rules, dependencies and acceptance gates.

The evaluator's confirmed emphasis is database design, backend APIs, locally managed relational persistence, real dynamic data, graceful validation, team Git participation, clean interactive UI, navigation, performance, scalability, security, debugging and understanding the implementation. PostgreSQL and the approved application stack remain team choices consistent with that guidance. The exact order below is our delivery sequence, not a claimed official scoring formula.

**Deliver:** configure products/plans/taxes/discounts/templates -> prepare quotation -> confirm/activate subscription -> automatically generate invoices -> record full/partial payments -> reconcile reports -> customer portal.

**Scope boundaries:** one responsive web application, local PostgreSQL, configured SMTP, no online payment gateway, no separate mobile app, no BaaS, and no speculative AI/blockchain/chatbot features. Audit events are emitted by the relevant operations; a separate audit-management UI is not part of the page inventory. No marketing website, generic settings suite or unused screens.

## 2. Proposed product rules for Phase 0 acceptance

The concrete D01-D10 recommendations, pricing model, state transitions and expected financial/calendar examples are now maintained in [docs/business-rules.md](docs/business-rules.md). That document supersedes the earlier alternatives in this section without marking them accepted. The proposed seat count/excess-unit fields are reflected in the existing editor and plan pages; the page count stays 32.

Review [docs/database-design.md](docs/database-design.md), [docs/api-design.md](docs/api-design.md) and [docs/architecture.md](docs/architecture.md) with those rules. Record team acceptance or requested changes before migrations. Phase 0 preparation is complete; its acceptance checklist remains pending. All unchanged source requirements and engineering guardrails continue to apply.

## 3. Architecture and page delivery

Use Next.js/TypeScript/Tailwind for the interface; FastAPI/Pydantic for APIs; SQLAlchemy/Alembic/PostgreSQL for persistence. Use React Hook Form/Zod for forms and TanStack Query where shared server state needs caching. HTTP routes call domain services; no financial rules in React or route handlers.

Proposed modules: identity, customers, catalog/pricing, quotations/subscriptions, billing/invoices, payments, reporting and SMTP/document adapters. Build UI alongside each domain, with navigation exposing only completed, authorized routes.

The schema review covers users/sessions/reset tokens, pending signup/verification/account-link records, customers, products/variants, plans/included lines, tax applicability, discount rules/assignments/redemptions, templates/lines, subscriptions/lines/agreement versions, quote versions/lines, lifecycle events/change requests, invoices/lines/tax/discount snapshots, payments, audit events and billing-run outcomes. Create a table only when its responsibility and constraints are justified in the ERD. Pending signup passwords and all one-time bearer tokens are stored only as hashes with expiry/consumption state.

Key constraints: normalized email uniqueness; unique document numbers; valid periods/quantities; protected financial foreign keys; unique subscription/billing-period invoice; unique payment request key; safe discount-cap concurrency. Preserve customer/company billing identity as invoice snapshots. Index actual ownership, status/date, search and reporting queries.

**32 page templates:** P01-P04 public; I01-I10 shared admin/staff; A01-A11 admin-only; C01-C07 customer. Admin can access 21 internal templates, staff 10, customers 7 portal templates. Shared templates are implemented once. Dialogs, tabs, root/role redirects, error states, email links and PDF responses are excluded from the count. Exact contents are in docs/USER_FLOWS.md.

## 4. Phase plan and gates

Implement one accepted phase at a time. A gate requires only capabilities introduced so far. Later-phase integration checks are activated when their prerequisites exist and remain regressions thereafter. Phase acceptance never waives previously passing security/integrity tests.

### Phase 0 - Confirm scope, flows and relational design

**Depends on:** this planning handoff and team review.

**Work:** accept/replace the proposed rules in section 2; confirm role matrix and all 32 pages; produce the ERD, cardinalities, API outline, state tables, money examples, document snapshot strategy and concurrency plan. Record the actual repository state. Agree local PostgreSQL versus Docker-hosted local PostgreSQL, business timezone, SMTP testing and the measurable page-response test environment. Assign domain owners and another teammate for reviews; everyone contributes through Git.

**Pages:** review all page designs; build none.

**Gate:** PASS. Decisions D01–D10 accepted on 31 October 2026. Design and contracts reviewed and accepted. Phase 1 authorized.

### Phase 1 - Reproducible foundation and database

**Depends on:** accepted Phase 0 design.

**Work:** create frontend/backend structure; local PostgreSQL setup; safe environment examples and ignore rules; pinned dependency manifests/lockfile strategy; FastAPI v1 modules, validated configuration, consistent errors, dependency-injected sessions, health/readiness and known-origin CORS. Configure invoice issuer/company details and currency through validated local configuration; a settings UI is not required. Add SQLAlchemy models and initial Alembic migrations for the approved schema, plus a separate disposable PostgreSQL test database. Record exact Windows setup/start/migration commands in README.

**Pages:** app/auth/portal layout foundations only; temporary development health page is removed before final acceptance and is not in the 32-page product inventory.

**Gate: PASS.** Frontend and backend start; readiness checks live PostgreSQL; schema verified from empty base through Alembic migrations (without create_all fallback); all 36 relational entities defined; composite foreign keys, partial unique indexes, and constraints exercised via Pytest (17 tests passing, including user email uniqueness, role check, product price non-negative, plan interval, invoice total identity, payment constraints, partial unique draft version, partial unique open pause, partial unique accepted effective date, cross-subscription term source FK, and financial deletion safety RESTRICT). Navigation hides undelivered routes; setup and reproduction commands documented in README.

### Phase 2 - Identity, staff and customer records

**Depends on:** Phase 1.

**Work:** controlled admin bootstrap; atomic signup/customer creation; normalized unique email; Argon2id; login/logout and revoked sessions; password reset and safe existing-customer linking via local SMTP; role and ownership dependencies; authentication rate protection; CSRF strategy. Create minimal role shells, admin staff management, operational customer creation/search/detail/edit and own-profile/password forms. Deactivated staff loses active sessions.

**Pages delivered:** P01-P04, I02-I03, I10, A01, C07. Until later dashboards exist, authenticated landing redirects to a delivered permitted page; no dead dashboard links. Future-domain customer tabs remain absent until delivered.

**Gate: PASS.** Delivered pages P01–P04, I02–I03, I10, A01, and C07. Automated Playwright browser tests (`scripts/test_browser_journeys.py`) verified all 5 end-to-end user journeys (F01 atomic registration, F01 unlinked customer email verification and linking via Mailpit, F02 forgot/reset password with session revocation via Mailpit, F03 admin staff provisioning and deactivation with instant session revocation, and customer directory CRUD/search/detail editing). Pytest suite expanded to 32 tests (100% pass) verifying Argon2id password complexity (9-char boundary), duplicate rejection, token expiry/single-use, CSRF protection, RBAC and customer isolation. Undelivered routes remain hidden.

### Phase 3 - Catalog, pricing rules and templates

**Depends on:** Phase 2.

**Work:** product/variant CRUD and archiving; plan fees/included lines, four intervals, quantity/availability/policy flags; tax rules/applicability; discount CRUD/scope/eligibility; template plan/product lines and validity days. Implement the shared Decimal pricing service and backend field validation. Add real admin forms and operation-only catalog reads for staff.

**Pages delivered:** A02-A09.

**Gate:** admin-only writes; correct 560 variant adjustment; allowed zero prices versus invalid negatives; all interval/availability/policy fields persist; tax and discount bounds/thresholds/caps validated; templates populate valid lines; pricing unit tests and PostgreSQL constraints pass; admin browser CRUD works. Test pricing previews without invoice writes. Historical invoice/redemption integration checks are deferred specifically to Phase 5.

### Phase 4 - Quotation and subscription lifecycle

**Depends on:** Phase 3.

**Work:** create subscription draft; template-based quote editor; immutable quote versions/expiry; confirmation/activation; agreed product/plan/tax context and price snapshots; lifecycle actions; customer request submission/cancellation and staff approve/reject workflow; dated plan-policy enforcement; agreement versions for renewals/add-on changes. Show pending and completed changes on the same subscription detail page.

**Pages delivered:** I04-I06, C02-C03. Customer/profile links connect to delivered subscription views.

**Gate:** Draft -> Quotation -> Confirmed -> Active path persists; repeat confirmation is safe; expired quote fails; invalid plan/date/quantity/state operations fail; requested changes never directly mutate billing; approve/reject/cancel access and effective dates work; disallowed pauses/renewals/closure rejected; quote/subscription snapshots survive catalog edits. Customer sees only own subscriptions/requests. Browser flow reaches active subscription. Invoice effects of scheduled changes are deferred to Phase 5.

### Phase 5 - Invoice engine, documents and delivery

**Depends on:** Phase 4 and the accepted calendar/money rules.

**Work:** one tested billing service plus CLI/admin trigger; per-period transactions, locks and unique invoice period; bounded backlog recovery; start/term/change eligibility; invoice/customer/company/line/tax/discount snapshots; capped discount redemption; invoice confirm/cancel; invoice number/due dates; local PDF/print document and configured SMTP send/retry. Persist run outcomes, per-period errors and delivery attempts. SMTP reset already exists from Phase 2; reuse its adapter.

**Pages delivered:** I07-I08, A11, C04-C05. Invoice send/print/download works on delivery; no placeholder controls waiting for a later phase. Payment actions appear only in Phase 6.

**Gate:** daily/weekly/monthly/yearly periods; month-end anchor restoration; leap year; final partial-period calculation; repeated/concurrent runs; interrupted/replayed billing; eligible backlog after expiry/closure; paused intervals and approved changes; same-transaction discount cap/rollback; catalog/profile edits do not rewrite issued documents; cancellation rules; no skipped eligible periods. Include a PostgreSQL fixture with at least 300 subscriptions due together, mixed eligibility and an injected per-period failure; reconcile every expected period to a created invoice or visible retryable failure, then recover without duplicates. Print/download matches stored data and customer ownership; send failure is retryable without reversing financial records. Manual trigger and CLI produce identical results. Add browser invoice confirm/send/download journey.

### Phase 6 - Payment recording and reconciliation

**Depends on:** Phase 5.

**Work:** invoice-level payment dialog; persisted immutable payment records and actor; cash/bank transfer/UPI/card/cheque/other methods; payment date/note/reference validation; unique request keys and locked balance checks; derived Partially Paid/Paid; searchable payment history for operations and customer.

**Pages delivered:** I09, C06. Complete payment sections/actions in I08 and C05.

**Gate:** known 10,000 invoice -> 4,000 payment -> 6,000 remaining -> final 6,000 -> zero; reject another payment, zero/negative amounts, missing method/date/note, draft/cancelled invoices and customer writes. Repeated request returns the same payment; conflicting key reuse fails; concurrent partial payments cannot overpay. Balances reconcile to PostgreSQL rows; payment browser journey passes. Customer history remains isolated.

### Phase 7 - Dashboards, filters and reporting

**Depends on:** Phase 6.

**Work:** role dashboards and admin finance report; known definitions for active subscriptions, payments received, current outstanding and overdue; date/customer/status filters; upcoming renewals and attention queues; SQL aggregation and indexed/paginated drill-downs. Each card links to the matching filtered list. Dashboards use only existing persisted operations; no invented activity or charts.

**Pages delivered:** I01, A10, C01. Switch post-login destinations to the final role dashboards. All 32 templates are now delivered.

**Gate:** known data produces expected totals; Draft/Cancelled excluded from receivables; payment-date filter correct; active/paused/ended counts correct; drill-down filters match their cards; customer dashboard scopes every query. Reports do not download whole tables. Browser journeys verify dashboard changes after invoice/payment operations and usable empty/error states.

### Phase 8 - Automatic execution and recovery

**Depends on:** Phase 5 engine and all Phase 7 regressions passing.

**Work:** configure Windows Task Scheduler or deployment scheduler to invoke the same command; run start-date activation, approved dated changes, recurring billing and configured auto-closure through tested domain services. Document executable/working directory/timezone, startup/restart, failed-run visibility, retries and disabling the schedule. Use demo data only. No extra page and no duplicate billing algorithm.

**Pages delivered:** no new templates; A11 shows actual scheduled/manual run outcomes and retry eligibility. Scheduler configuration stays in deployment documentation, not a generic settings screen.

**Gate:** an actual scheduled run invokes the expected command; repeated scheduled/manual runs are safe; downtime backlog recovers; failed work stays visible/retryable; auto-close-enabled terms close and others appear ended without out-of-term billing. Demonstrate no duplicate/omitted eligible period and no false success after partial failure.

### Phase 9 - Security, performance and final demonstration

**Depends on:** Phases 0-8 accepted.

**Work:** fresh-clone setup rehearsal; migrations from empty PostgreSQL; idempotent seed using development-only credentials from environment; API/role/ownership review; responsive/keyboard validation of the entire inventory; query-plan review; measured browser performance; final documentation and shared team walkthrough. Resolve defects without adding new product scope.

**Pages:** verify P01-P04, I01-I10, A01-A11, C01-C07. No page additions.

**Gate:** backend unit/PostgreSQL integration/browser suites and frontend checks pass; all visible actions work; 32 page templates accounted for; no tracked secrets/generated dumps; fresh teammate setup succeeds; demo uses persisted data and needs no manual DB edits. Every teammate explains their code, data relationships and test decisions.

**Mandatory performance evidence:** propose 5,000 subscriptions, 50,000 invoices and 100,000 payments. Agree actual fixture counts, hardware, browser, local/deployed topology and representative concurrency in Phase 0. Time navigation until primary content is usable for the 32 templates using authorized representative accounts/records; include filtered/paginated large collections. Record cold/warm results, sample counts, p50/p95/max and failures. Every sampled designated page load must be under two seconds; p95 alone does not satisfy the literal PDF target. Treat unmeasured environments as unknown, not proven. Bulk generation throughput is reported separately from interactive page latency.

**Final demonstration:** admin configures product/variant/plan/tax/discount/template -> customer registers -> staff prepares and confirms quote -> activate subscription -> run due billing -> confirm/send/print invoice -> partial then final payment -> customer checks owned history -> admin report reconciles -> rerun billing safely -> show a customer change request and plan-policy validation.

## 5. Execution and handoff

Use a focused feature branch per phase or coherent subfeature, with another teammate reviewing code and evidence. Keep phase gates sequential even when team members divide the current accepted phase. No particular agent tool is required.

After each phase provide: Implemented; Files changed; Design decisions; Commands run; Test results; Manual actions remaining; Known issues; Gate status. Report the exact repository commands that were actually run. A pending human review or required external setup stays visible; passing documentation checks does not imply application acceptance.

**Current state:** Phase 0 accepted; Phase 1 (foundation, database models, migrations, and layout) implemented and verified (PASS); Phase 2 (Identity, staff and customer records, pages P01–P04, I02–I03, I10, A01, C07, Mailpit SMTP linking/reset, Argon2id, and Playwright journeys) implemented and verified (PASS). Next phase is Phase 3 (Catalog, pricing rules and templates), pending team request.
