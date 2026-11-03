# Phase 8 security verification

Scope: the local Brightloop application, source, pinned dependencies and isolated PostgreSQL integration tests on 2 November 2026. This is application verification for the hackathon; it is not an independent penetration-test certification or proof about an undeployed production network.

### 3 November tooling dependency update

Frontend lint uses pinned Biome 2.6.4 with recommended rules and React/Next.js domains, following the [Biome installation guide](https://biomejs.dev/installation/quick-start/) and [domain configuration](https://biomejs.dev/linter/domains/). `npm run lint` checks all source, native tests and the two JavaScript configuration files with zero permitted warnings. Type checking remains a separate production-build check. The repository recognizes Tailwind's custom at-rule; missing effect dependencies remain errors, while intentional retry/navigation triggers may remain in dependency arrays. One narrowly documented exception permits the shared named overflow region's keyboard focus, covered by actual scroll/keyboard verification.

The initial Next.js 15 ESLint setup produced 14 moderate findings, all propagated from [minimatch glob-pattern amplification GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249), and required end-of-support ESLint 9. Installing newer ESLint alone would still require an affected minimatch major. The legacy dependencies were removed rather than force-downgraded or overridden incompatibly; they are absent from the final package manifest. Clean `npm ci`, the full npm audit and the final lockfile synchronization report **zero vulnerabilities**. The backend runtime and runtime-plus-browser-test audits report no known vulnerabilities. Bandit reports zero issues and zero skipped tests. The full PostgreSQL suite passed 194 tests; final hardening browser journeys passed four, including scoped scheduler replay and failed-logout recovery. Earlier audit counts below describe their own checkpoint.

The browser login helper now identifies actual 429 responses and respects the backend Retry-After before one retry, checking that email/password inputs remain intact. Application limits remain 15 IP logins and 10 account logins per five minutes. Running many browser suites concurrently had exhausted this real limit; the failed runs are not counted as application passes. The sequential reruns passed. Removed a core runner's manual traceback catch, which had bypassed the installed redactor; uncaught errors now use the common safe reporter.

The final declaration audit inspects the pinned FastAPI version's effective routes (not only the lazy router wrappers): 68 protected domain routes and 37 POST/PATCH operations. The common session-bound CSRF dependency now includes Origin validation, and the pricing-preview POST uses it too. Six new regressions first demonstrated foreign-origin staff/customer creation and profile changes plus unguarded preview transport, then passed after the fix. They also verify unchanged records and successful side-effect-free pricing with legitimate headers. Existing pricing tests retain all calculation assertions and now supply the legitimate CSRF/Origin headers. Full regression: **194 passed, one external deprecation warning**. This declaration audit does not replace runtime role/ownership testing.

References: [OWASP Top 10:2025](https://top10.owasp.org/2025/), [OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), and [PostgreSQL advisory locks](https://www.postgresql.org/docs/18/explicit-locking.html#ADVISORY-LOCKS). The checklist below maps application evidence to those risk categories; a passing tool cannot certify every category.

| Area | Implemented controls and exercised evidence | Scope/limits |
|---|---|---|
| A01 access control | Backend role/ownership dependencies; foreign subscription/invoice/payment/document denial; no customer financial mutations. Live browser probes deny anonymous access on 13 protected collection/dashboard endpoints. | Full endpoint/action inventory is additionally audited in Phase 9. |
| A02 configuration | Exact-origin CORS; CSRF and Origin validation; no debug response traces; no-store API responses; preserved private PDF cache header; nosniff/frame/referrer/permissions headers; frame/object/base CSP restrictions on frontend. | HTTPS termination and host/service configuration require the real deployment environment. CSP is deliberately limited; it is not a complete script nonce policy. |
| A03 supply chain | Pinned Python requirements and npm lockfile; Bandit and dependency audits actually run. Vulnerable nested PostCSS replaced through an npm override using the existing patched direct dependency. | Advisory results are a dated snapshot; repeat scans when dependencies change. No untrusted CSS processing feature exists. |
| A04 cryptography | Argon2id passwords; random expiring bearer tokens, stored as hashes; HttpOnly/SameSite session cookie; production Secure flag. Browser confirms session token is inaccessible to document.cookie. | Local loopback is HTTP. Production transport is an operations prerequisite. |
| A05 injection | Parameterized SQLAlchemy queries; backend Pydantic validation; escaped React text; local PDF escaped descriptions. Browser stores an HTML-shaped customer name and confirms inert literal text/no injected image/dialog; SQL-injection-shaped search returns no records. | Browser probes cover the exercised components; final all-page review remains Phase 9. |
| A06 design | Backend financial authority; frozen snapshots; transactions/locks/uniqueness/idempotency; customer requests require review; bounded catch-up; uncertain email stays UNKNOWN. | Financial and ownership integration regressions remain mandatory after changes. |
| A07 authentication | Shared PostgreSQL sliding-window limits, one count per attempt, bounded passwords; CSRF binding/rotation, expiry/revocation; reset/session-creation user lock and atomic credential/session updates. Forty independent-connection attempts admit exactly ten; concurrent reset rejects or revokes all old-credential sessions. | Configure trusted proxy client addressing for deployment; no untrusted forwarded IP bypass. |
| A08 integrity | Alembic schema, check/composite FK/unique constraints; immutable payment trigger; snapshot history; command/payment keys; safe scheduler run recovery from committed state. | Database-owner operational access can change data by design; protect those credentials. |
| A09 logging | Safe persisted authentication/financial/auto-close audit events, billing outcomes, delivery attempts and actual scheduler status. Passwords and raw bearer/reset/CSRF tokens are absent from audit payloads; API access logging disabled in local instructions. | External alerting/log retention and incident response are deployment/team responsibilities. No invented audit page. |
| A10 exceptional conditions | Safe structured errors, no raw SQL/parameters in responses; tested rollbacks/races, lost response retry, partial billing failure, interrupted process recovery and UNKNOWN delivery. Failed sign-out preserves authenticated UI and offers retry; successful retry revokes the original server session. | SMTP exactly-once delivery is not promised; no blind uncertain resend. |

Actual scan results: Bandit found zero issues with no suppressed/skipped tests; pinned backend pip-audit found no known vulnerabilities; npm runtime audit/install reported zero vulnerabilities after the PostCSS override. Artifacts are ignored under test-results/. A first pip-audit attempt failed because Requests did not recognize this machine's certificate issuer; the successful rerun used Windows' trusted store with TLS verification enabled, without disabling certificate checks.

Reproduce from the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-security.txt
New-Item -ItemType Directory -Force test-results | Out-Null
backend/.venv/Scripts/python.exe -m bandit -r backend/app -f json -o test-results/bandit.json
backend/.venv/Scripts/python.exe scripts/audit_backend_dependencies.py
$env:PYTHONPATH='.;backend'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short
backend/.venv/Scripts/python.exe -u scripts/test_browser_journeys.py
backend/.venv/Scripts/python.exe -u scripts/test_hardening_journeys.py
# From frontend:
npm audit --omit=dev
npm run build
```

The hardening browser runner creates only uniquely named synthetic local records and scopes scheduler commands to its new subscription. The real timer test runs two ticks against the guarded isolated test database. Existing billing/payment races continue to verify manual/scheduled engine invariants without replacing the live database.
