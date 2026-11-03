# Brightloop - API contract outline

Status: Implemented domains through Phase 8. Phase 9 transport consistency is implemented and regression-tested: allowlisted sorting, strict query validation and create Location headers. Final local acceptance is recorded in FINAL_ACCEPTANCE.md. Depends on [business-rules.md](business-rules.md) and [database-design.md](database-design.md). Prefix every route below with `/api/v1`. OpenAPI/Pydantic schemas formalize implemented fields; this document records behavior and access.

## Shared contract

All authenticated POST/PATCH/PUT/DELETE domain operations, including the read-only pricing preview POST, use session-bound X-CSRF-Token and the configured Origin/Referer policy. The common CSRF dependency includes Origin validation; clients without browser Origin/Referer can still use the documented token policy. Cookie authentication derives identity from the server session. The route declaration audit covers 68 protected domain routes and 37 POST/PATCH operations; ownership and role enforcement are additionally exercised at runtime.

JSON requests/responses; currency amounts as strings, ISO dates, UTC timestamp strings, UUIDs and server-derived role/actor. Deny by default. A = admin, S = staff, C = owning customer, P = public. Any `C` operation derives customer from the session and applies ownership in the SQL query; an arbitrary customer_id never expands access. A/S endpoints still validate nested associations.

Collections: `page` default 1, `page_size` default 20/max 100, allowlisted `sort`, structured filters, stable id tie-break. Response `{items, page, page_size, total}`. Reject invalid filter/date/sort fields with 422. Search number/email prefix or documented name prefix; no raw SQL/column expressions. Detail `{...fields}`; create 201 with Location; reads/commands 200; logout 204.

Collection `descending` controls direction; ties use ascending ID and nullable values sort last. Defaults preserve existing views: names ascending for products/plans/discounts/templates; creation descending for customers/staff/taxes/subscriptions; payment date descending for payments; start descending for billing runs. OpenAPI lists each endpoint's allowed fields. Unknown query names and repeated scalar parameters return 422. Plan availability accepts available/future/expired, independent of archive state. Discounts support scope, fixed/percentage type and eligible/not-yet-valid/expired/exhausted/disabled filters computed from persisted revisions and redemption counts.

Created-resource Location identifies the readable resource; embedded revisions and customer requests identify their parent aggregate. Registration identifies `/auth/me`, readable after authentication. Variant locations have a nested read endpoint with association validation; staff locations have an admin-only detail endpoint. CORS exposes Location and Retry-After. Validation uses 422; an immutable historical cutoff rewrite uses 409.

Owned subscription change-options supports product-name search (up to 100 results) and an optional validated product_id to hydrate a selected active product independently of search. Ownership is checked before catalog lookup, and customer results contain sales/variant fields only. Reviewed request responses include reviewer display name and review time, without reviewer account IDs or email.

Errors: `{error: {code, message, fields: [{path, message}], request_id}}`. 401 missing/expired session, 403 forbidden role, 404 absent/unavailable owned resource, 409 stale version/duplicate email/key mismatch/state conflict, 422 field/business input validation, 503 unavailable infrastructure. No raw ORM/SQL/token details. SMTP failure returns a persisted FAILED attempt with retry guidance, not a fictitious rollback of the confirmed invoice.

Required names/types/classifications are trimmed and must contain a non-whitespace character; explicit null updates to required fields fail 422. Passwords retain their exact whitespace. Monetary request fields accept decimal strings (or Decimal values in internal Python calls), never JSON numbers, and enforce NUMERIC(18,2), finite values and domain sign rules. Percentage inputs support four decimal places and 0–100 bounds. Quantities/caps must fit PostgreSQL INTEGER; template validity and plan payment terms align with the existing commercial draft's 365-day input limit. Calculated line/aggregate overflow fails validation before a financial write. Product base-price and variant writers lock the parent product in a consistent order and validate effective prices against the same monetary range.

Versioned aggregate commands include `expected_version` and fail 409 on stale state. Draft creation accepts `Idempotency-Key` (the browser always supplies it); quote issue/confirm, request review, lifecycle scheduling and invoice commands carry `request_key` in their validated JSON body. Payment creation requires JSON `request_key` and serializes on the invoice rather than trusting an optimistic browser balance. Persist normalized request hash and result reference; commercial/invoice keys are scoped to actor/operation, while payment keys are globally unique. Same-key/same-payload replay returns the original resource without a second write; changed intent conflicts. A billing trigger can create a new run, but its period processing is idempotent independently of request keys.

## Identity, users and customers

| Method / path | Access | Input / result |
|---|---|---|
| POST /auth/register | P | name,email,password,company?; creates customer session-ready identity or generic verification-required result for existing operational customer |
| POST /auth/verify-signup | P token | consume token; verified pending identity/customer link |
| POST /auth/login | P | email,password; opaque session cookie and current-user DTO |
| POST /auth/logout | authenticated | revoke current session, clear cookie |
| GET /auth/me | A/S/C | identity/role, no password/session hash |
| GET /auth/csrf | P/session | establish/refresh CSRF context without leaking auth token |
| POST /auth/forgot-password | P | email; generic 202, whether or not account exists |
| POST /auth/reset-password | P token | token,new_password; consume and revoke all sessions |
| POST /auth/change-password | A/S/C | current_password,new_password; revoke other sessions |
| PATCH /profile | A/S/C | allowed own contact fields only; customer includes billing fields |
| GET, POST /staff | A | paginated staff list; name,email,initial_password creates STAFF only |
| PATCH /staff/{id} | A | name/contact, expected_version; no arbitrary role changes |
| POST /staff/{id}/deactivate or /reactivate | A | state command; deactivation revokes sessions |
| GET, POST /customers | A/S | search/list; create operational customer without password |
| GET, PATCH /customers/{id} | A/S | detail/contact edits; validated normalized email and link restrictions |
| GET /profile | A/S/C | own role-appropriate profile, including customer contact fields |

Registration/verification exceptions must not leak pre-existing customer's record fields. Auth throttling, hashed challenge tokens and session behavior follow architecture.md. Login-email changes are not an exposed first-release operation. Existing linked customer email cannot drift from account email through operational editing.

## Catalog and templates

| Method / path | Access | Responsibility |
|---|---|---|
| GET /products; GET /products/{id} | A/S | A gets admin DTO; S gets only operational sales fields |
| POST /products; PATCH /products/{id} | A | name,type,sales_price,cost_price,notes; validated archive flags |
| POST /products/{id}/variants; PATCH /products/{id}/variants/{variantId} | A | name,adjustment; validate association/effective price |
| GET, POST /plans; GET, PATCH /plans/{id} | A/S reads; A writes | fee,minimum_seats,extra_seat_unit_price,interval,availability,payment terms,flags,included lines,tax assignments |
| GET, POST /taxes; PATCH /taxes/{id} | A/S reads; A writes | admin tax rules; assignment fields on product/plan write schemas |
| GET, POST /discounts; GET, PATCH /discounts/{id} | A/S reads; A writes | revisioned conditions, product scope and global cap |
| POST /discounts/{id}/deactivate | A | prospective date, reason; preserve assigned history |
| GET /discounts/{id}/redemptions | A | paginated committed uses |
| GET, POST /quotation-templates; GET, PATCH /quotation-templates/{id} | A/S reads; A writes | metadata/lines/validity; incomplete template inactive |
| POST /pricing/preview | A/S | selected plan,seats,lines,discount IDs,dates; authoritative estimate without redemption |

Archive via validated active-state patch with confirmation; no destructive deletion of referenced catalog. Customer add-on selection uses the restricted subscription eligibility route below, not these unrestricted catalog responses. Tax/discount configuration cannot be embedded as newly trusted rules in a pricing request.

## Subscriptions, quotations and customer requests

The following subscription routes are implemented under `/api/v1`. Portal pages use the same owner-scoped API rather than duplicate routers. Other domain tables below remain planned until their phase is delivered.

| Method / path | Access | Responsibility |
|---|---|---|
| GET /subscriptions | A/S/C owner | SQL filters, stable pagination, recurring estimate, expiry and pending request count |
| POST /subscriptions?issue=true | A/S | Atomic draft creation and optional quotation issue |
| GET /subscriptions/{id} | A/S/C owner | Explicit safe agreement lines, quotation history, terms, requests and events |
| PATCH /subscriptions/{id} | A/S | Expected-version draft replacement; issued offers retained, revised versions numbered separately |
| POST /subscriptions/{id}/commands | A/S | ISSUE, CONFIRM, ACTIVATE, ABANDON; expected_version and idempotency request_key |
| POST /subscriptions/{id}/lifecycle | A/S | PAUSE, RESUME, RENEW, EARLY_CLOSE, ADDON_CHANGE; future/boundary validation, complete proposal for commercial changes |
| GET /subscriptions/{id}/change-options | A/S/C owner | Searchable active products/variants and own plan; excludes cost/internal notes |
| POST /subscriptions/{id}/change-preview | A/S/C owner | Validate requested action/date/proposal and compute estimate without writes |
| POST /subscriptions/{id}/requests | C owner | Pending change request with version and server-generated commercial estimate |
| POST /subscriptions/{id}/requests/{requestId}/cancel | C requester | Cancel own pending request |
| POST /subscriptions/{id}/requests/{requestId}/review | A/S | APPROVE/REJECT, reason, expected_version and request_key; revalidate requested terms |

Customer and staff changes both use the same validation/calculation service. Review rejects stale/different commercial terms; the customer submits a new request after preview. Action record unique request key/event identity prevents duplicate scheduled changes. Dates and history are never patched with an arbitrary status field.

## Invoices, payments, runs and reports

Invoice and billing-run routes are implemented in Phase 5; payment routes are implemented in Phase 6. Dashboard/report routes below remain planned until Phase 7 passes.

| Method / path | Access | Responsibility |
|---|---|---|
| GET /invoices; GET /invoices/{id} | A/S/C owner | operational drafts for A/S; owned issued records only for customers; SQL balance/date/overdue filters |
| PATCH /invoices/{id}/draft-metadata | A/S | only due date/contact metadata, audit reason; cannot rewrite financial lines |
| POST /invoices/{id}/commands | A/S | CONFIRM/CANCEL, expected_version and request_key; cancellation requires unpaid state/reason |
| GET /invoices/{id}/document?download=true | A/S/C owner | snapshot PDF; customer ownership and issued-state rules also protect documents |
| POST /invoices/{id}/send | A/S | issued snapshot billing contact; persisted attempt, never arbitrary unrelated recipients |
| GET /invoices/{id} delivery_attempts/history | A/S | safe delivery and action history included in operational detail; excluded from customer responses |
| POST /invoices/{id}/payments | A/S | amount/method/payment_date/note/reference?, required request_key; locked balance and server-derived actor; returns payment and refreshed invoice |
| GET /payments; GET /payments/{id} | A/S/C owner | filtered/paginated immutable ledger and read-only detail; internal actor/time excluded for customers |
| Portal invoice pages use /invoices routes above | C owner | no duplicate API router or relaxed ownership query |
| GET /payments/{id}/receipt | A/S/C owner | locally rendered immutable payment receipt PDF with the same ownership checks |
| GET /billing-runs; GET /billing-runs/{id} | A | paginated outcomes and safe failures; collection includes actual scheduler heartbeat/interval/state/last-run observations |
| POST /billing-runs | A | as_of_date <= today; max_periods <= 100; optional subscription_id/after_subscription_id/retry_of_id; persisted partial outcomes |
| POST /billing-runs with retry_of_id | A | retry/continue through the same service, retaining a database-enforced preceding-run link |
| GET /dashboard | A/S/C | backend chooses role-appropriate metrics/queues; customer ownership is mandatory on every aggregate/list |
| GET /reports/summary; GET /reports/details | A | receipts date range/customer/plan; explicit current-balance definition and paginated details |
| GET /health; GET /ready | operational | liveness; database readiness with safe status, no infrastructure secrets |

Print invokes browser print against the same document representation; it is not a second financial calculation endpoint. Customer cannot send/confirm/cancel invoices or record payments. There are no financial DELETE/PATCH payment endpoints. Send retries are explicit; delivery is not guaranteed exactly once across an SMTP acceptance/connection-loss ambiguity, so UI may report unknown delivery before a deliberate retry.

## Example schema shapes

```json
{
  "plan_id": "UUID",
  "customer_id": "UUID",
  "seat_quantity": 7,
  "start_date": "2027-01-01",
  "expiry_date": "2028-01-01",
  "payment_term_days": 15,
  "lines": [{"product_id": "UUID", "variant_id": null, "quantity": 2}],
  "discount_revision_ids": ["UUID"]
}
```

Draft input contains selectors/intent; backend looks up prices, inclusion, taxes, availability and permissions. An allowed negotiated unit-price override is a separate validated field with reason. Invoice output includes `id, number, state, overdue, period_start, period_end, subtotal, discount_total, tax_total, total, paid, remaining, lines, version`; monetary fields are decimal strings. Pagination responses never serialize ORM graphs or raw internal columns.

## Coverage and future tests

P01-P04/I10/C07 use identity/profile; I02-I03 customers; A01 staff; A02-A09 catalog/templates; I04-I06/C02-C03 commercial commands/requests; I07-I09/C04-C06 invoices/payments; A11 runs; I01/A10/C01 dashboards/reports. Full page field details stay in [USER_FLOWS.md](USER_FLOWS.md).

For every introducing phase test successful operation, malformed fields, unauthenticated/forbidden role, missing IDs, nested ID mismatch, cross-customer access, stale version and duplicate commands where applicable. PostgreSQL checks back the financial races; UI hiding is never evidence of authorization.

Phase 8 transport hardening: API responses include no-store (preserving the private PDF policy), nosniff, frame/referrer/permissions headers; production adds HSTS. Authentication rate limits are shared PostgreSQL windows and preserve 429 Retry-After. Failed logout is surfaced for retry without claiming the server session was revoked.
