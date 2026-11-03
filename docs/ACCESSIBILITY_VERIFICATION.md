# Accessibility and page-inventory verification

Release checkpoint: 3 November 2026, 05:54 UTC. Phase 9 remains in progress.

## Verified build and scope

- Production build: `DO6xl0qQyiLmkLAZK5l3t`; Chrome `156.0.8078.80`, axe-core `4.14.0` as a pinned development dependency. Earlier build `MUvzCrTuHQwYrFpv67eLc` remains the preceding checkpoint.
- Exact source inventory: 32 feature page templates match BUILD_GUIDE.md and USER_FLOWS.md, with no missing or extra template. `/` remains a redirect. Removed the temporary `/health-check` frontend page; backend liveness/readiness endpoints remain available.
- Automated WCAG 2 A/AA and WCAG 2.1 A/AA tags: all 32 templates plus ten staff variants at widths 1440 and 390, totaling **84 observations, zero rule violations and zero page overflows**.
- Eight axe checks returned incomplete. Targeted review identified password-status glyphs and text clipped inside horizontally scrollable tables. All 77 affected targets had measured contrast at least **4.548:1**; keyboard horizontal scrolling passed for the four table observations. Rendered password/table screenshots were inspected. This is scoped application verification, not a complete accessibility-conformance assessment; final combined release review remains in FINAL_ACCEPTANCE.md.
- Twelve opened create dialogs, covering six admin forms at both widths: no automated findings; Tab/Shift+Tab containment, dirty Escape stay/discard and trigger-focus restoration passed.
- Same-document history test: dirty product edits survive cancelled Back; accepted Back restores the filtered list; Forward reloads persisted product fields.
- Payment regression: entry and staff/customer details drawers retain keyboard focus. Dirty Close/Escape, lost-response reload/retry, receipt/mobile behavior and final settlement all passed.

The audit injects axe with CSP bypass enabled only in the test browser context. It does not verify CSP; security verification uses its separate tests. Pages load persisted PostgreSQL data and synthetic payment/catalog fixtures.

## Changes driven by observed failures

Initial audit: 59 rule findings over 84 observations, zero overflows. Connected 86 labels to controls; named collection filters, pagination and remove-line buttons; increased low-contrast muted/action text; made horizontally scrollable tables focusable. A second audit retained four button-name findings; the final scan after naming those buttons passed.

Eighteen legacy overlay dialogs now use a shared native dialog component, with heading-derived names, inert background, guarded Escape, busy state and focus restoration. A keyboard test found native Tab behavior could leave document focus on the body. Added shared explicit first/last focus cycling, also used by payment entry/detail dialogs; the complete keyboard rerun passed.

The release uses one native named `ScrollableRegion` section for all 17 table overflow areas. Its intentional keyboard focus has one documented local lint exception; no axe rule is suppressed. All four clipped-table cases were scrolled with the keyboard and reviewed again. The eight incomplete observations cover 77 targets; minimum measured contrast remains 4.548:1. Current password/table screenshots were also visually inspected. Static display/group captions use paragraphs rather than unattached form labels. Buttons declare their actual submit/button behavior, and editable rows use stable identities rather than array positions. The final keyboard, dirty-form and payment runners passed after these changes.

Dirty-form history protection uses the Navigation API only for cancellable same-document traversals. Other-document unloads and in-app links retain their existing guards. Browsers decide whether a traversal can be cancelled; repeated browser Back actions may bypass cancellation to prevent trapping users. This follows the [Navigation API traversal restrictions](https://github.com/WICG/navigation-api/blob/main/README.md#restrictions-on-firing-canceling-and-responding). The recorded runtime verification is for the Chrome version above.

Main and benchmark builds now use separate TypeScript configurations, preventing stale generated route types from the other build from breaking compilation after route changes. Both still compile the same application source.

## Commands and artifacts

With the local production frontend/backend running, install frontend dependencies using README setup. The audit reuses synthetic fixtures from the payment and admin-choice runners:

```powershell
backend/.venv/Scripts/python.exe -u scripts/test_admin_choices.py
backend/.venv/Scripts/python.exe -u scripts/test_payment_journeys.py
backend/.venv/Scripts/python.exe -u scripts/test_keyboard_journeys.py
backend/.venv/Scripts/python.exe -u scripts/audit_accessibility.py
backend/.venv/Scripts/python.exe -u scripts/review_accessibility_incomplete.py
$env:PYTHONPATH='.;backend'
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_browser_log_safety.py -q --tb=short
```

Actual latest results: keyboard journeys **three passed**, payment journeys **four passed**, redaction regression **one passed** with the existing external Starlette/httpx test-client warning. Production build passed. The earlier expanded form-protection runner also passed four journeys against the native-dialog conversion.

Ignored artifacts under `test-results/`: `accessibility-audit.json`, `dialog-accessibility.json`, `accessibility-incomplete-review.json`, rendered review PNGs, retained `accessibility-audit-initial.json` and `accessibility-audit-before-final-buttons.json`. The final page audit records timestamp, build ID and browser version. The runner also records incomplete-rule details on subsequent runs to support targeted review. The focused review fails on unrecognized cases or insufficient contrast and does not suppress axe rules.

## Test-log safety correction

A payment verification GET encountered a transient connection reset after settlement. Playwright's default traceback included a synthetic test session cookie. Revoked and verified exactly that test admin session using the synthetic customer's creation/invoice interval; financial records were unchanged. The API health check passed and the complete payment rerun passed. Only the read-only verification GET retries connection resets; payment writes retain explicit request-key recovery.

Browser runner error output now redacts credential headers, session/CSRF values, reset-link tokens, password payload fields and URL passwords, and omits source lines that can contain fixture credentials. A permanent regression verifies redaction while retaining useful failure context.
