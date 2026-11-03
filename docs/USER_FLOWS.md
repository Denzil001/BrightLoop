# Brightloop - User flows and page specifications

## 1. Scope, count and navigation

Complete proposed first-release interface for the supplied PDF and evaluator expectations. Read [BUILD_GUIDE.md](../BUILD_GUIDE.md) for proposed business defaults and phase gates. Team acceptance of those defaults is required in Phase 0. This document describes planned behavior, not implemented functionality.

**Exactly 32 page templates:**

| Group | IDs | Count | Access |
|---|---|---:|---|
| Public authentication | P01-P04 | 4 | Visitors; token modes validate their token |
| Shared operations | I01-I10 | 10 | Admin and staff |
| Admin configuration/control | A01-A11 | 11 | Admin |
| Customer portal | C01-C07 | 7 | Customer, own records only |
| Total | | 32 | |

Admin accesses 21 internal templates, staff 10, customers 7. Dynamic records share one template. Role variants of the same dashboard count once. Tabs, dialogs/drawers, confirmation screens, pagination, redirects, error states, email-link modes and PDF responses do not add pages.

There is no separate marketing home, quotations list, variant list, payment form page, settings suite, audit page or request inbox. Those functions are embedded where specified below. `/` redirects to `/login` or the authenticated role landing page. Admin/staff land at `/app`; customers at `/portal`. During construction, redirect to a delivered permitted page until dashboards exist.

Navigation:

- Admin: Dashboard; Customers; Subscriptions; Invoices; Payments; Catalog (Products, Plans, Taxes, Discounts, Quotation templates); Staff; Reports; Billing runs. Profile/logout in account menu.
- Staff: Dashboard; Customers; Subscriptions; Invoices; Payments. Profile/logout in account menu. Catalog selectors inside forms use authorized read APIs, without access to admin configuration pages.
- Customer: Overview; Subscriptions; Invoices; Payments; Profile. Logout in account menu.
- Subscriptions includes Quotations and Pending requests filters; these do not create separate modules.
- Mobile: collapsible navigation, visible primary action, scrollable tables or equivalent cards, full-screen form drawers and accessible dialogs.

### Permission matrix

| Action | Admin | Staff | Customer |
|---|---|---|---|
| Provision/deactivate staff | Yes | No | No |
| Configure catalog/taxes/discounts/templates | Yes | No | No |
| Select operational catalog/assign existing valid discount | Yes | Yes | Own agreed pricing only |
| Manage customer records | Yes | Yes | Own allowed profile fields |
| Prepare/confirm quotes and operate subscriptions | Yes | Yes, within plan policy | View own; submit permitted requests |
| Approve/reject subscription requests | Yes | Yes, within plan policy | Cancel own pending request only |
| Confirm/cancel/send invoice | Yes | Yes, within invoice rules | No |
| Print/download issued invoice | Yes | Yes | Own only |
| Record payment | Yes | Yes | No |
| Manually run/retry billing | Yes | No | No |
| Full finance report/run diagnostics | Yes | No | No |
| Dashboard | Business summary | Operational queues | Own summary |

Backend policies enforce this matrix, including document/report routes. Customers never receive product cost, internal notes, audit context or another customer's data.

## 2. Shared page behavior

- Consistent layout, color/spacing, page title, breadcrumbs where useful and account menu. One clear primary action when creation is supported.
- Data pages: loading, useful empty state, error/retry, refresh after success. Empty-state actions must be permitted and implemented.
- Lists: server search/filter/sort/pagination, URL-preserved filters and correctly scoped counts. No full-table browser filtering.
- Forms: labels, required markers, field-level validation, inline backend errors, duplicate-submit prevention, preserved input on failure and unsaved-change warning.
- Consequential actions: record identity, effective date, impact, confirmation and cancellation. Require a reason for rejection/cancellation/early closure. Backend rechecks eligibility.
- Expired session: login with safe internal return path. Forbidden/missing resource: shared 403/404 state with valid navigation, without revealing other customers. These are not inventory pages.
- Money/status/totals come from the backend. Dates show business timezone. Overdue/Ended are derived badges, not arbitrary editable statuses.
- Stale conflict: explain and refresh. Mail failure: show retry without undoing invoice/payment. Financial history has no hard-delete controls.
- Hide not-yet-delivered navigation/tabs during phased development. Every final visible control must work.

## 3. Public pages - 4

### P01 - Login

**Route:** `/login`. **Phase:** 2.

Email, password, show/hide password, Sign in, Create account and Forgot password links. Validate format/required fields; safe invalid-credentials message and rate-limit retry guidance. On success, use backend role for authorized landing/return destination. No role selector or staff/admin public registration.

### P02 - Customer registration

**Route:** `/register`. **Phase:** 2.

Full name, email, password, confirmation and optional company name. Visible password checklist: at least 9 characters, uppercase, lowercase, special character. Sign up creates only CUSTOMER; validation, submission and completion states; Sign in link.

If a matching operational customer exists without a login, send an expiring verification link before associating its records. It returns to this same route in verification mode; consume it and finalize the pending signup atomically. Do not expose existing details before verification. An existing registered login cannot be claimed/overwritten. Hash pending passwords; scrub emailed bearer tokens from logs.

### P03 - Forgot password

**Route:** `/forgot-password`. **Phase:** 2.

Email, Send reset link, Back to sign in and generic completion message independent of account existence. Invalid email gets a field message. Use configured SMTP/local inbox; requests are rate-limited. Do not display/log a reset URL as a development shortcut.

### P04 - Reset password

**Route:** `/reset-password`. **Phase:** 2.

Emailed token opens new password, confirmation, password checklist and Reset password. Missing/invalid/expired/used token links to P03. Valid token consumption changes hash and revokes sessions atomically; success links to P01. Secret tokens never appear in errors/logs.

## 4. Shared admin/staff operations - 10

### I01 - Operational dashboard

**Route:** `/app`. **Phase:** 7.

Admin: active subscriptions, payments received in selected range, current outstanding/overdue, upcoming renewals and recent payments. Staff: quotes awaiting confirmation, pending customer requests, due/ending subscriptions, invoices requiring action, overdue and recent payments. Staff does not receive full finance reports.

Date filters where applicable, attention tables, Create subscription and list shortcuts. Cards/rows open matching authorized filtered lists/details. Clearly label current balances versus range receipts. No invented activity/metrics or decorative charts.

### I02 - Customers list

**Route:** `/app/customers`. **Phase:** 2.

Name/email search, portal-linked/unlinked filter, pagination/sort. Columns: name/company, email, phone, portal status, created date. Create drawer: name, company, email, phone, billing address. Row opens I03. No hard delete. Creating an operational customer does not create a password or grant portal access; duplicate email gives actionable feedback.

### I03 - Customer detail

**Route:** `/app/customers/[customerId]`. **Phase:** 2; domain tabs in 4-6.

Identity, company/contact/billing details, portal-link state, Edit details dialog. Tabs for this customer's subscriptions/quotes, invoices and payments appear when delivered, with dates/status/totals and record links. Create subscription opens I05 preselected. Editing profile cannot change role/login or financial history. Address changes affect future snapshots only.

### I04 - Subscriptions and quotations list

**Route:** `/app/subscriptions`. **Phase:** 4.

Search subscription/quote number/customer; All/Quotations views; lifecycle/plan/upcoming billing/expiry/pending-request filters; pagination. Columns: number, customer, plan, lifecycle/Ended badge, recurring amount, next billing, expiry, request count. Create opens I05; row opens I06. Quotations use this route with a filter, not another page.

### I05 - New subscription / quotation editor

**Route:** `/app/subscriptions/new`. **Phase:** 4.

Customer, available plan, optional template; explicit seat quantity, start/expiry, payment-term days, quote-validity days; plan fee, included-seat threshold and excess-seat charge; included items and product/variant/add-on lines with quantity, agreed unit price, taxes, assigned existing discount and calculated line amount. Clearly distinguish included lines from additional charges. Backend preview shows each line's amount plus subtotal, estimated discount/tax and total. Seat pricing follows the accepted Phase 0 rules in [business-rules.md](business-rules.md).

Save draft -> I06 DRAFT. Save and issue quotation -> immutable quote version and I06 QUOTATION. Validate minimum quantities/date windows/discount conflicts. Permitted agreed-price overrides require backend validation/reason. Staff cannot create configuration here. Preview consumes no discount redemption. Warn before losing unsaved changes.

### I06 - Subscription detail and lifecycle

**Route:** `/app/subscriptions/[subscriptionId]`. **Phase:** 4; invoice links in 5.

Header: number, customer link, plan, lifecycle/Ended badge, service dates, next billing, recurring total. Sections/tabs: agreement/lines; quote versions and expiry; invoices; customer requests; dated lifecycle history. Show current/agreed versions, future changes, payment terms and each line's product, quantity, unit price, tax/discount and calculated amount. Historic versions are read-only.

Contextual actions: edit draft in-place using the shared editor; issue/revise quote; confirm; activate when eligible; pause/resume; renew; early close; schedule add-on change. No arbitrary status dropdown. Every action respects role/state/plan flags and previews dates/impact/reason.

Requests show action/items/date/note, Pending/Approved/Rejected/Cancelled, reviewer/reason and resulting dates. Approve/reject here; no separate inbox. If requested dates/pricing are no longer valid, reject with a reason and explain the valid terms so the customer can submit a new request. Never silently rewrite an agreement. Invoice history links I08.

### I07 - Invoices list

**Route:** `/app/invoices`. **Phase:** 5.

Search invoice/customer/subscription; state/Overdue and issue/due-date filters; pagination/sort. Columns: number, customer, subscription, period, issue/due date, total, paid, outstanding, status. Row opens I08. Billing generates invoices; no unrelated manual creation form. Draft/Cancelled are visibly distinct from receivables. Settlement fields become operational in Phase 6.

### I08 - Invoice detail

**Route:** `/app/invoices/[invoiceId]`. **Phase:** 5; payments in 6.

Number/state/Overdue; snapshot company/customer/address; subscription; period; invoice/due dates/currency; lines, quantities/unit prices, allocated discount, tax rates/amounts, subtotal/tax/total/remaining. Sections: payments, delivery attempts/status, safe action history.

Actions: correct permitted draft metadata; Confirm; Cancel eligible unpaid invoice with reason; Send/retry after issue; Print; Download PDF. Draft previews are marked and not sent as issued documents. Calculations are backend-owned. Issued cancelled copies remain marked historical documents; cancelled drafts are not customer-visible.

Phase 6 adds Record payment only for eligible issued invoices with balance. Dialog: required amount, method, date and non-empty customer-visible note, plus optional reference; remaining/resulting-balance preview and one persisted submission key. Keep internal information out of the customer-visible note. Success refreshes status/history. Stale balance/overpayment preserves the form with an explanation. No payment edit/delete or Pay online.

### I09 - Payments ledger

**Route:** `/app/payments`. **Phase:** 6.

Search customer/invoice/reference; date/method filters; paginated columns payment ID, customer, invoice, amount, method, date, reference, recorded by. Row opens read-only detail drawer with note/timestamps and source links. Record from the target invoice only; no unallocated payment or edit/delete workflow.

### I10 - Own operational profile

**Route:** `/app/profile`. **Phase:** 2.

Own name/contact fields; read-only login email/role. Change password dialog: current/new/confirmation, password validation and session-revocation feedback. Save changes only permitted own fields. Profile cannot administer staff or change role. Logout remains in the global account menu.

## 5. Admin-only pages - 11

### A01 - Staff management

**Route:** `/app/staff`. **Phase:** 2.

Name/email search, active/inactive filter; table name/email/status/created date. Create drawer: name, email, initial password/confirmation; role fixed STAFF. Edit permitted staff contact fields; confirm deactivate/reactivate. Deactivation revokes sessions. Never list/log passwords; later password recovery uses the standard reset flow. No admin/customer role conversion here.

### A02 - Products list

**Route:** `/app/products`. **Phase:** 3.

Name/type search, active/archive filter, pagination. Columns name/type/sales price/internal cost/variant count/state. Create drawer: name, type, sales price, cost price, internal notes. Row opens A03. Archive confirmation preserves referenced history and removes the product from new selections.

### A03 - Product detail and variants

**Route:** `/app/products/[productId]`. **Phase:** 3.

Editable product fields/state; variants table with name, adjustment, effective sales price and state; applicable tax assignments. Add/edit variant dialog validates final non-negative price and shows base-plus-adjustment preview. Archive referenced variants. The 560 example is a test case, not hard-coded live data. Staff/customer cannot access this admin route.

### A04 - Plans list

**Route:** `/app/plans`. **Phase:** 3.

Search; interval/availability/active filters; pagination. Columns name/base fee/interval/minimum quantity/availability/policy flags. Create drawer captures required metadata and opens A05 after save. Row opens A05. Availability and archive state are displayed separately.

### A05 - Plan detail and policy

**Route:** `/app/plans/[planId]`. **Phase:** 3.

Name/description, recurring fee/currency, daily/weekly/monthly/yearly interval, minimum included seats, excess-seat unit price, plan-fee/excess-seat tax assignments, sales-availability dates, default payment terms and active state. Included product/variant lines with explicit bundle quantities; switches for auto-close, early closure, pause and renewal. Explain included versus additional charges. These seat/tax fields are the Phase 0 recommendation, not a new source requirement.

Save validates dates/quantity and preserves existing agreed versions/invoices. Archive prevents new sales; it does not delete history. Subscription-specific dates/actions stay in I06.

### A06 - Tax rules

**Route:** `/app/taxes`. **Phase:** 3.

Search/active filter; table name/classification/rate/applicability/state. Create/edit drawer contains those fields and product applicability. Initial calculation mode is percentage/exclusive per accepted BUILD_GUIDE rules; no unsupported inclusive/fixed switches. Add effective-date fields only if the Phase 0 tax policy adopts them. Disable/archive confirmation explains future-versus-historical effect.

### A07 - Discount rules

**Route:** `/app/discounts`. **Phase:** 3; redemption history in 5.

Search, scope/type/eligibility filters; table fixed/percentage value, thresholds, validity, used/cap, active state. Create/edit drawer: name, type/value, minimum eligible purchase/quantity, product or whole-subscription scope, selected products, start/end, usage cap. Labels distinguish inactive/not-yet-valid/expired/exhausted.

Details show conditions and committed redemptions when available. Admin edits rules; staff selects existing eligible rules on subscriptions. Disable stops future eligibility without rewriting prior invoices. Validation explains conflicting non-stacking assignments and invalid values.

### A08 - Quotation templates list

**Route:** `/app/quotation-templates`. **Phase:** 3.

Name/plan search, active filter, pagination; columns name/default plan/line count/validity/state. Create metadata drawer: name, description, plan, validity days. Save opens A09 to complete lines; incomplete templates stay inactive. Row opens A09. Deactivate preserves historic quotes.

### A09 - Quotation template editor

**Route:** `/app/quotation-templates/[templateId]`. **Phase:** 3.

Name, description, default plan, validity days, state; line editor with product/variant/quantity and included/additional classification derived from the plan. Backend price/tax estimate and validation. Activation requires valid plan/complete lines. Editing affects future drafts only. Staff adjustments belong to I05/I06, not this admin template.

### A10 - Finance report

**Route:** `/app/reports`. **Phase:** 7.

Payment-date range, applicable customer/plan filters, metric definitions, active subscriptions, cash received in range, current outstanding and overdue totals/counts. Clearly separate snapshot balances from ranged receipts. Paginated detail tabs: receipts, outstanding, overdue, active subscriptions; source links to I04/I07/I09.

Show empty/error states and query time. SQL-backed values reconcile to persisted records. No MRR claim, speculative charts/export or separate analytics page in this scope.

### A11 - Billing runs and recovery

**Route:** `/app/billing-runs`. **Phase:** 5; scheduler outcomes in 8.

Run history: as-of business date, trigger type, start/end, state, created/already-processed/failed counts, remaining backlog. Run now confirmation defaults to today and rejects future dates in the live UI. Expand a run in-place for subscription/period outcomes, safe errors and invoice/subscription links.

Retry failed/remaining work calls the same idempotent service and rechecks eligibility. Partial failure stays visible. Scheduler state uses actual configured/runtime information; otherwise show truthful unconfigured state. Scheduling is configured in deployment instructions, not a fake toggle.

## 6. Customer portal - 7

### C01 - Customer overview

**Route:** `/portal`. **Phase:** 7.

Own active count, next billing, current outstanding, recent issued invoices/payments and renewal/expiry reminders. Cards link to matching C02/C04/C06 filters; pending requests link C03. No-record state explains staff prepares subscriptions; no unsupported Buy now control.

### C02 - Own subscriptions

**Route:** `/portal/subscriptions`. **Phase:** 4.

Own number/plan search, lifecycle filter, pagination; table/cards number, plan, status/Ended, recurring amount, dates, next billing. Row opens C03. Owned quote-stage records are read-only offers, with no internal margins/customer selector or Create subscription action.

### C03 - Own subscription detail and requests

**Route:** `/portal/subscriptions/[subscriptionId]`. **Phase:** 4; invoices in 5.

Number, plan/state, service dates, next billing, agreed fee, itemized product/quantity/unit price/tax/discount/line amount, payment terms, customer-visible quotes and issued-invoice links. Distinguish quote estimates from invoices. Pending/approved changes and own request history/reviewer reasons are visible.

Request pause/resume/renewal appears only for eligible states/plan flags. Request add-on change opens authorized item/quantity selection and backend projected pricing. Dialog: requested date, note, impact preview, Submit. Explain approval requirement; submission itself does not alter billing. Cancel own pending request. A rejected request shows the reason/valid terms and can prefill a new request for the customer to review and submit. No invoice confirmation, payment recording or arbitrary status editing.

### C04 - Own invoices

**Route:** `/portal/invoices`. **Phase:** 5.

Invoice-number search, issued-state/Overdue/date filters, pagination. Columns number/period/issue/due/total/paid/remaining/status. Only issued invoices and their subsequently cancelled historical copies; internal drafts/cancelled drafts excluded. Row opens C05.

### C05 - Own invoice detail

**Route:** `/portal/invoices/[invoiceId]`. **Phase:** 5; payment history in 6.

Persisted company/customer billing snapshots, number/state, subscription, period/dates, lines/discount/tax/totals/paid/remaining. Print and Download PDF; Phase 6 payment history with method/date/amount/reference/customer-visible note. Cancelled issued copies are marked and excluded from payable balance.

No Confirm, Cancel, Record payment, Edit amount or online gateway action. Documents enforce the same ownership/issued-state checks. Provide plain contact-staff guidance for payment queries, not a dead contact button.

### C06 - Own payment history

**Route:** `/portal/payments`. **Phase:** 6.

Date/method/invoice filters, pagination; payment ID, invoice link, amount, method, date, reference. Read-only drawer includes customer-visible note; excludes internal actor/audit metadata. No create/edit/delete.

### C07 - Own profile

**Route:** `/portal/profile`. **Phase:** 2.

Editable name/company/phone/billing address; read-only login email. Change password with current/new/confirm, validation and success/session feedback. Future documents use updated details; historic invoices remain unchanged. Login-email changes are outside this version. Logout in account menu.

## 7. Complete user journeys

### F01 - Signup, verified linking and login

P01 -> P02 -> validate -> check normalized email. New identity creates CUSTOMER/customer atomically. Existing unlinked operational customer requires emailed verification back to P02 before association; duplicate registered account cannot be overwritten. Finish -> P01 -> authorized role landing: C01 or I01 (C07/I02 during early delivery). Empty customer portal is truthful. Browser-supplied role never determines access.

### F02 - Forgot/reset password

P01 -> P03 -> valid email -> generic completion -> emailed token -> P04 -> validated new password -> atomic consume/hash/session revocation -> P01. Invalid/expired/reused token -> P03. Local inbox receives the message; no secret logging.

### F03 - Provision/deactivate staff

Admin -> A01 create drawer -> validated email/password -> STAFF account -> staff P01 login. Admin deactivate -> confirmation -> sessions revoked. Staff/customer direct API attempts are denied.

### F04 - Configure catalog and quote template

Admin -> A02/A03 product/variant -> A06 tax/assignment -> A04/A05 plan/included lines/policy -> A07 discount -> A08 metadata -> A09 lines/validity/activation. New selections use current valid configuration; existing agreements/issued snapshots stay unchanged. Prerequisite selectors allow navigation to their configuration, with unsaved-work warning.

### F05 - Operational customer setup

Admin/staff -> I02 Create -> validate/persist -> I03 edit billing details or I05 with customer preselected. Later signup verifies ownership through F01. Operational editing never grants login access, overwrites password or duplicates an existing identity.

### F06 - Draft and issue quotation

I03 or I04 Create -> I05 select customer/plan/template -> load lines/validity -> permitted adjustments -> backend preview -> Save draft -> I06 DRAFT. Issue -> immutable quote version -> QUOTATION with number/expiry. Preview consumes no usage; abandonment leaves no partial financial records.

### F07 - Revise, confirm and activate

I06 QUOTATION -> check validity/customer agreement -> Confirm -> locked recheck/snapshot -> CONFIRMED -> eligible activation -> ACTIVE and next billing. Future starts activate through the lifecycle service. Repeat confirmation is safe. Expired quotes require a new version; invalid plan/date/quantity/state fails clearly. Historic agreed versions cannot be overwritten.

### F08 - Bill automatically/manually and recover

Scheduler or admin A11 -> same service -> find eligible historical periods -> apply due accepted versions -> Decimal pricing/tax/discount -> atomic invoice/lines/redemption/cursor -> outcome -> I07/I08. Repeated/concurrent invocation does not duplicate. Failed period remains unprocessed and visible; Retry rechecks/reprocesses safely. Downtime/current expiry does not erase earlier owed periods.

### F09 - Confirm/cancel/send/print invoice

I07 -> I08 draft -> check/correct permitted metadata -> Confirm -> issued/customer-visible. Send -> SMTP -> delivered/failed status; retry without recreating invoice. Print/download uses snapshots. Cancel eligible unpaid invoice -> impact/reason/confirm -> Cancelled, excluded from receivables; previously issued copy remains marked. Payments block cancellation. No deletion/automatic credit/same-period replacement path.

### F10 - Record/reconcile payment

I08 -> Record payment -> amount/method/date/note -> locked invoice/request-key check -> persist -> refreshed Partially Paid/Paid and I09/customer history. Example: 10,000 -> 4,000 -> 6,000 remaining -> final 6,000 -> zero. Retry returns existing payment. Overpayment, invalid amount/state, conflicting key reuse, unauthorized actor or losing concurrent balance check leaves no partial update.

### F11 - Customer financial review

P01 -> C01 -> C02/C03 -> C05; or C04 -> C05 -> Print/Download; or C06 -> C05. Every list/detail/document is own-record scoped. Another customer's ID yields no data. Payment mutation is absent in UI and forbidden through API.

### F12 - Customer subscription-change request

C03 -> eligible action -> date/items/note/preview -> submit Pending -> staff badge in I01/I04 -> I06 review -> Approve/Reject with reason -> C03 result. Customer may cancel while Pending. Ineligible/conflicting/stale requests fail clearly. Changed terms require rejection with explanation and a new customer-submitted request, using the same detail/dialog surfaces; no negotiation state or extra approval page.

Approval records an immutable scheduled agreement/lifecycle event. Shared services apply it at the accepted boundary before that period's billing; earlier owed periods and invoices remain intact. Reapplying an event is safe. No extra request page.

### F13 - Operate pause/resume/renewal/closure

I06 contextual action -> role/state/plan/date check -> effective date/term/price preview -> confirm -> dated event/agreement version. Pause stops future periods; resume follows the accepted term/anchor rule; renewal extends explicitly; early closure ends future service at the accepted boundary. Auto-close runs only if configured and preserves eligible backlog. Unsupported direct API actions fail.

### F14 - Finance and operational review

Admin I01 -> A10 -> filters -> SQL summary -> matching I04/I07/I09 detail. Current balances are labeled separately from payment-range receipts. Staff I01 opens operational queues; customer C01 applies mandatory ownership. Empty data produces zero/empty states, not demo records.

### F15 - Profile, logout and recovery

Account menu -> I10/C07 -> edit allowed fields/change password -> validate/persist -> success; historic documents unchanged. Logout revokes session -> P01. Expiry preserves safe return route. Forbidden/missing records show shared error/navigation state; failed loads offer retry with filters/input preserved. API boundaries match UI permissions.

## 8. Page-to-phase accounting

| Phase | New page IDs | Count |
|---|---|---:|
| 0 | Design only | 0 |
| 1 | Foundations only | 0 |
| 2 | P01-P04, I02-I03, I10, A01, C07 | 9 |
| 3 | A02-A09 | 8 |
| 4 | I04-I06, C02-C03 | 5 |
| 5 | I07-I08, A11, C04-C05 | 5 |
| 6 | I09, C06 | 2 |
| 7 | I01, A10, C01 | 3 |
| 8 | Existing pages; scheduling/recovery | 0 |
| 9 | Existing pages; acceptance | 0 |
| Total | Every new template counted once | 32 |

Final acceptance covers all 32 templates, applicable F01-F15 actions, backend authorization, persisted dynamic data, responsive/keyboard use and measured performance from BUILD_GUIDE.md. Planning completeness is separate from application acceptance.
