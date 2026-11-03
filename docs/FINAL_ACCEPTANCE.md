# Final acceptance audit — PASS

This is the completion audit, separate from the earlier planning-coverage report. Source requirements are R01–R24 and E01–E11 from PLANNING_VERIFICATION.md, the accepted D01–D10 decisions, all 32 USER_FLOWS templates/F01–F15 journeys, and the BUILD_GUIDE gates. All software delivery gates are verified for the recorded local environment. Performance, workflow, database, security and reproducibility evidence are separate checks; actual future presenter participation is human-owned.

## Current evidence

- Phases 0–8 have their recorded local gates. The latest full PostgreSQL suite passed **194 tests** in 58.74 seconds on 3 November, with one external Starlette/httpx deprecation warning. Main production build `DO6xl0qQyiLmkLAZK5l3t` passed; pinned Biome lint checks 68 files with zero warnings, and all four native decimal tests pass.
- All 32 templates and ten staff variants rendered persisted data in a production browser build over 5,000 subscriptions / 50,000 invoices / 100,000 payments. Five samples each at concurrency 1 and 5: 420 cold-client observations under two seconds, maximum 1,078.33 ms; another 420 warm-client observations pass, maximum 567.54 ms. See PERFORMANCE_VERIFICATION.md for boundary, hardware, per-template p50/p95/max and the retained initial failure.
- Read-only completion browser checks passed three: root role redirects/mobile menu, selectors beyond the first 100 with selected-value preservation, and cancellable internal navigation from a dirty quotation editor. Main reporting browser regression passed all three after SQL optimization.
- Current backend exposes frozen term policies and per-line quote estimates. Add-on changes preserve the current term policy, and pending accepted changes do not masquerade as the current agreement. A permanent regression covers the policy/estimate distinction.
- Four operational lifecycle browser journeys now pass: historical pause/resume with exact two-day extension and resumed billing anchor, future pause, add-on changes with retained policy and expiry validation, closed-term renewal with revised catalog price/policy and unchanged historical invoices, and future-only early closure/customer permissions. Quote issue/revision/confirmation/activation, immutable superseded lines and request rejection/prefill/cancellation/approval pass in the four subscription journeys.
- Clean `npm ci`, installation of all pinned runtime/browser Python packages in a new virtual environment, `pip check`, and empty-schema migration/initial API verification passed. All 38 application tables start empty at the current head, Alembic reports no model drift, and the verifier removes only its own isolated test schema. This establishes dependency/empty-schema reproducibility on the recorded Windows environment, not an untested OS installation.
- Git history across repository branches contains two existing contributors (Denzil001: 11 commits; Paul Francis: 10). This records actual history, not fabricated teammate contributions or presentation participation.

## Source-to-evidence map

The table maps every source requirement to inspected code and executed verification. Raw development artifacts are ignored; the committed reports retain results, failures, scope and reproduction commands.

| Source | Evidence location / remaining check |
|---|---|
| R01 account uniqueness/atomic signup | test_auth.py, test_db_constraints.py; core browser F01 linking/new signup |
| R02 exact password rule | test_auth.py eight/nine boundary and nine-character no-digit success; shared security validator and browser checklist |
| R03 emailed password reset | test_password_reset.py; core browser actual Mailpit/reset/session revocation |
| R04 roles and owned portal | domain ownership tests; reporting/payment/billing/core/hardening browser journeys |
| R05 admin-only staff | test_staff.py and core provisioning/deactivation journey |
| R06 product metadata | test_catalog.py; catalog browser CRUD; Staff response excludes cost/notes |
| R07 variant +560 | pricing/catalog unit assertions and catalog/billing browser worked case |
| R08 four intervals | calendar/billing tests, configured plans and large fixture across all four intervals |
| R09 minimum quantity/availability | test_pricing.py/test_subscriptions.py and backend plan/date validation |
| R10 plan-specific lifecycle | test_lifecycle.py/test_scheduler.py; frozen policy/add-on regression; four operational lifecycle browser journeys |
| R11 templates and validity | template/activation tests; catalog/subscription browser; large selector navigation check |
| R12 numbered subscription/terms/itemized pricing | subscription snapshots and estimate regression; shared editor/detail; linked UI rehearsal and exact 32-template source/action audit |
| R13 lifecycle state progression | subscription/lifecycle/scheduler tests and quote acceptance browser; pause/resume, renewal, add-on and closure UI verification |
| R14 automatic populated invoices | shared engine/scheduler tests and actual worker two-tick process; snapshot/document browser |
| R15 hundreds due, no duplicate/skip | PASS: isolated committed 325-subscription cohort, 300 due / 600 periods, one injected failure; 599 initial + 1 retry + 0 replay; all 610 final identities reconcile including ten previously billed periods; test_large_billing_batch.py |
| R16 automatic tax | shared Decimal calculator/pricing/billing tests, known invoice 2,888.64 and PDF snapshot |
| R17 invoice actions and settlement | invoice/document/payment tests; actual Mailpit attachment, confirm/cancel/print/PDF and lost-response payment browser |
| R18 discount types/scope/thresholds | discount/pricing/multiple-discount tests and catalog forms |
| R19 dates and use cap | cap race/rollback tests, date eligibility and business-date cutoff regression |
| R20 automatic next-invoice discount/expiry | billing eligibility/cap/snapshot regressions; no manual discount re-entry in billing |
| R21 required payment fields/correct invoice | payments/schema/independent-connection tests and four payment browser journeys |
| R22 paid/outstanding/overdue | persisted payment-sum reports, invoice/ledger views and known-value report tests |
| R23 finance filters/summary | test_reporting.py; report browser and large-ledger known totals; no MRR claim |
| R24 thousands/under-two-second pages | PASS: final guarded-source run, 420 observations / 84 page-concurrency gates, maximum 1,078.33 ms. Earlier I05 miss and substantive fix retained in PERFORMANCE_VERIFICATION.md |
| E01 relational design | additive migrations, composite FKs/checks/uniqueness/indexes, financial race/rollback tests, protected ledger |
| E02 local database | native PostgreSQL plus loopback Mailpit; no BaaS; test DB and benchmark schema separated |
| E03 modular APIs | shared pricing/billing/lifecycle/payments; allowlisted sorting, strict unknown/duplicate query validation, create Location and readable association-checked endpoints; test_api_contracts.py (18 tests) |
| E04 dynamic persistence | pages query versioned API/PostgreSQL; bulk synthetic rows are benchmark-only fixtures |
| E05 validation/feedback | required-text/null/precision/range negatives and exact large-money browser transport pass; 194-test full backend suite, five money browser journeys and complete linked UI rehearsal |
| E06 team Git | two actual human contributors preserved; reviewed codex/finish-brightloop integration branch, private-value/artifact and local-link audits clean; integration commit is recorded in Git history |
| E07 UI/navigation | exact 32-template source inventory; 84 desktop/mobile axe observations with zero violations/overflow, all eight incomplete cases reviewed; twelve opened-dialog scans and keyboard/Back journeys pass; selector, filter and dirty-form regressions pass; linked UI rehearsal passes |
| E08 performance/scalability/security/usability | measured browser gate, PostgreSQL concurrency, security scope/checklist; final combined acceptance passes |
| E09 debugging/detail | retained test/benchmark failures and fixes; permanent regressions; consolidated final evidence recorded |
| E10 minimal outside APIs | no payment gateway/BaaS/novelty service; local SMTP/PDF, ordinary framework libraries |
| E11 understanding/shared presentation | EVALUATOR_DEMO.md provides worked invoice, role walkthrough and shared-understanding handoff; clean dependency/empty-schema setup and combined UI rehearsal pass; actual team presentation remains human-owned |

## Completed release audit

- All R01–R24 and E01–E11 software deliverables are covered above. All F01–F15 journeys are exercised by the role-specific runners and the linked evaluator rehearsal. The PDF was reread in full and its four-page SHA-256 reconfirmed against PLANNING_VERIFICATION.md.
- Source inventory: exactly 32 feature templates plus the root redirect; 174 buttons and 27 forms have declared actions, no permanently disabled placeholders, no missing/extra feature pages. This wiring audit complements runtime checks; it does not replace them.
- Final backend: 194 PostgreSQL tests pass, including independent connections, financial rollback/replay, batch reconciliation and six new transport-policy regressions. The declaration audit covers 68 protected domain routes and 37 POST/PATCH operations; all declare identity and the common CSRF/Origin policy. Runtime ownership/role tests remain separate evidence.
- Final frontend: production build, 68-file Biome lint and four decimal tests pass. All 84 desktop/mobile accessibility observations pass; eight incomplete cases are rendered/reviewed (77 targets, minimum 4.548:1). Keyboard, dirty-form, payment and exact-money regressions pass.
- Full npm audit and backend runtime-plus-browser dependency audits find no known vulnerabilities; Bandit finds zero issues with zero skipped tests. No external security or unmeasured deployment certification is claimed.
- Clean npm installation, clean Python runtime/test installation, pip check, all empty-schema migrations, model parity and initial API use pass. Temporary schema cleanup and preservation of existing test records are verified. Fresh-machine prerequisites and private first-time database provisioning are documented in README.
- The linked UI rehearsal passes on the final guard: one taxed/template-based subscription, INR 2,888.64 invoice, actual Mailpit PDF, two payments, zero balance, owned documents, request review/cancellation, reporting and safe billing replay. EVALUATOR_DEMO.md records identifiers and team handoff.
- Final benchmark covers 5,000 subscriptions, 50,000 invoices and 100,000 payments. All 840 cold/warm-client sampled loads are below two seconds; cold-client maximum 1,078.33 ms and warm-client maximum 567.54 ms. Benchmark services are temporary verification infrastructure, separate from normal application data.
- Candidate Git files were checked against configured private environment values/passwords and credential signatures; no matches or generated/private artifacts were found. Local Markdown links and diff whitespace checks pass. The sole removed page is the unplanned frontend health-check; backend health/readiness remain.

**Gate: PASS for local project delivery.** One external Starlette/httpx test-client deprecation warning remains; application tests pass. The team's live speaking assignments, code understanding and future deployment operations remain genuine human responsibilities described in the handoff, without fabricated reviews or participation.
