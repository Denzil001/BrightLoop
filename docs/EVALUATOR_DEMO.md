# Brightloop evaluator demonstration and team handoff

Status: presentation guide prepared; the combined rehearsal and final release acceptance remain pending in FINAL_ACCEPTANCE.md. Existing catalog, subscription, billing and payment browser runners verify the individual workflows described here.

## Preflight

Use synthetic `.test` identities and clearly named demo records. Open separate browser profiles for ADMIN, STAFF and CUSTOMER so their cookies remain separate. Every team member should own a section and understand the complete flow; assign presenters before rehearsing.

1. Follow README setup, migrate PostgreSQL and bootstrap the local admin using ignored environment configuration.
2. Start the backend, production frontend and Mailpit. Verify `/api/v1/health`, `/api/v1/ready` and the local inbox at `http://127.0.0.1:8025`.
3. Provision one demo staff account as admin. Register a fresh customer and retain the email/password privately for the customer browser profile.
4. Prepare the catalog below through the admin UI. Give the records a shared demo prefix so searches isolate them from development fixtures. Use business dates displayed by the application; discount validity must include the service start.
5. Keep the final acceptance/performance reports and database diagram available. Show the measured environment and dataset when discussing performance.

| Configuration | Value |
|---|---|
| Tax | GST, 18% |
| Product | Server, sales price INR 200.00, cost INR 80.00, GST assigned |
| Variant | High memory, price adjustment INR 560.00; effective sales price INR 760.00 |
| Monthly plan | Base fee INR 1,000.00 includes 5 seats; each excess seat INR 100.00; GST assigned |
| Discount | Whole subscription, 10%, valid on the service start; no overlapping product rule |
| Quotation template | The plan above, two units of the variant as ADDON, validity 30 days; activate after configuring lines |

Do not display private environment files, passwords, session/reset tokens or production customer information. The test scripts' synthetic demo passwords are local fixtures, not production credentials.

## Twelve-minute walkthrough

| Time | Presenter responsibility | Demonstration and explanation |
|---|---|---|
| 0:00–1:30 | Data/backend owner | Show the schema relationships: user/customer, plan/product/variant, subscription/agreement/term, invoice/lines, payment. Explain Decimal money, database constraints, immutable snapshots and protected financial history. |
| 1:30–3:00 | Catalog/UI owner | Show the configured +560 variant, plan seats, tax and discount dates. Search for a record beyond the first page. Demonstrate an invalid value, field feedback and preserved input. |
| 3:00–5:00 | Subscription owner | As staff, create the customer's draft using the template, choose 7 seats, current business-date start and an appropriate expiry. Preview, issue, confirm and activate. Show the accepted version and service term on the same subscription. |
| 5:00–7:30 | Billing owner | As admin, run billing scoped to this subscription using `/app/billing-runs?subscription_id=<subscription UUID>`. Open the draft invoice, check amounts, confirm and send it. Open the actual Mailpit message/PDF. Repeat the scoped run and show that it creates no second invoice for that period. |
| 7:30–9:00 | Payment owner | As staff, record INR 1,000.00 with method, date, customer-visible note and optional reference. Show INR 1,888.64 remaining. Record the final INR 1,888.64; the invoice becomes PAID with two permanent payments. |
| 9:00–10:30 | Customer/UX owner | In the customer profile, show own invoice/receipt/history and absence of staff financial actions. Submit an eligible future-boundary change request. Staff rejects with a reason; show customer feedback and prefill for a new request. Cancel the new pending request and show that service has not changed. |
| 10:30–12:00 | Whole team | Show filtered persisted reporting, source drill-down, mobile navigation and the final performance report. Explain the concurrency/recovery tests, each member's actual Git contribution and one tradeoff each person understands. |

The worked invoice is exact:

| Calculation | INR |
|---|---:|
| Plan fee | 1,000.00 |
| Two excess seats | 200.00 |
| Two variant units at 760.00 | 1,520.00 |
| Subtotal | 2,720.00 |
| Whole-subscription 10% discount | −272.00 |
| GST 18% of 2,448.00 | 440.64 |
| Invoice total | **2,888.64** |

Use a full unprorated period for this example. Invoice/PDF totals come from stored backend snapshots. Later changes to prices or customer details must not alter that issued document.

## Evidence to have ready

- [Database design](database-design.md), [accepted business rules](business-rules.md) and [API contract](api-design.md).
- [Development evidence](DEVELOPMENT_STATUS.md), [security scope/results](SECURITY_VERIFICATION.md), [performance measurement](PERFORMANCE_VERIFICATION.md) and [final acceptance](FINAL_ACCEPTANCE.md).
- The actual Git history and diffs. Describe real contributions and reviews; do not invent authors, approvals or participation.
- The mixed billing regression: 300 due subscriptions, 600 expected periods, one injected failure, recovery of the single missing period and zero replay duplicates.
- Independent PostgreSQL-connection tests for invoice identity, discount caps, payment serialization and request-key collisions. A request retry and a new business action are different intents.

## Shared understanding

Every presenter should be able to trace a browser action through route validation, authorization, service transaction, PostgreSQL constraints and response rendering. Explain why historical agreements/invoices are snapshots, why payment writes serialize on the invoice, why billing reconstructs historical eligibility, and why the scheduler calls the same billing service as the CLI/admin action.

The application uses local PostgreSQL and local SMTP capture. It records offline payments; it does not connect to a payment gateway. The initial policy excludes refunds, payment edits and invoice replacement. Performance results describe the recorded local hardware/build/dataset and are not a guarantee for an unmeasured deployment.

## Rehearsal completion record

The automated linked UI rehearsal passed on **3 November 2026, 06:18 UTC**, build `DO6xl0qQyiLmkLAZK5l3t`, against the final common Origin/CSRF guard. It configured the taxed catalog and template through the admin UI, registered the customer with invalid-email feedback, prepared/issued/confirmed/activated the quote as staff, generated/confirmed/emailed the invoice, recorded two payments, downloaded owned documents, reviewed/cancelled customer requests, reconciled reporting and replayed billing safely. The invoice total/receipts are INR **2,888.64**, with two payments and zero outstanding.

Synthetic rehearsal identifiers: customer `9f4f283c-bfde-45ba-93f7-9420e66562b7`, subscription `d1003d15-6c8e-46ac-aa48-a49e7e25dee4`, invoice `afecc8e3-ba2c-461a-854d-b23fbb2c028b`. The record, PDF, receipt and mobile screenshot are under ignored test-results/. The first run reached settlement but its final mobile locator matched both equal total/paid values; the complete corrected rerun passed. Actual presenter participation is human-owned and is not simulated by browser automation.

To repeat, start the app and Mailpit, run the core browser journeys first to provision the documented synthetic `admin_bootstrap@brightloop.test` fixture, then run:

```powershell
backend/.venv/Scripts/python.exe -u scripts/test_evaluator_demo.py
```

Every run creates uniquely named synthetic records. Review the exact worked calculation and role responsibilities above before the team's live presentation. Keep credentials and tokens out of presentation material.
