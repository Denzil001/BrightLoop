"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient } from "@/lib/api";
import { buttonStyle, type DraftPayload, errorMessage, inputStyle, secondaryStyle, type SubscriptionDetail as Detail } from "@/lib/subscriptions";
import { formatCurrency } from "@/lib/utils";
import SubscriptionEditor from "./SubscriptionEditor";
import ServicePolicySummary from "./ServicePolicySummary";

export default function SubscriptionDetail({id, portal = false}: {id: string; portal?: boolean}) {
  const [sub, setSub] = useState<Detail | null>(null); const [error, setError] = useState("");
  const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false); const [action, setAction] = useState("");
  const [effective, setEffective] = useState(""); const [reason, setReason] = useState("");
  const [requestRevision, setRequestRevision] = useState(0);
  const [requestProposal, setRequestProposal] = useState<DraftPayload | null>(null);
  const [reviewId, setReviewId] = useState(""); const [reviewReason, setReviewReason] = useState("");
  useUnsavedChanges(Boolean(reason || reviewReason));
  const load = useCallback(async () => {setError(""); try {setSub(await apiClient<Detail>(`/subscriptions/${id}`));} catch (e) {setError(errorMessage(e));}}, [id]);
  useEffect(() => {load();}, [load]);
  const mutate = async (endpoint: string, body?: unknown) => {
    setBusy(true); setError(""); setNotice("");
    try {setSub(await apiClient<Detail>(`/subscriptions/${id}${endpoint}`, {method: "POST", ...(body ? {body: JSON.stringify(body)} : {})})); setNotice("Change saved."); return true;}
    catch (e) {setError(errorMessage(e)); return false;} finally {setBusy(false);}
  };
  if (!sub) return <section>{error ? <p role="alert">{error} <button type="button" className="underline" onClick={load}>Retry</button></p> : <p role="status">Loading subscription…</p>}</section>;
  const agreement = sub.agreements[0];
  const businessToday = new Intl.DateTimeFormat("en-CA", {timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date());
  const accepted = sub.agreements.find(a => a.state === "ACCEPTED" && !a.pending_change && a.effective_from && a.effective_from <= businessToday);
  const activeAgreement = accepted || agreement;
  const term = sub.terms[sub.terms.length - 1];
  const policies = term?.policies || activeAgreement.policies;
  const base = portal ? "/portal" : "/app";
  const initial: DraftPayload = {customer_id: sub.customer_id, plan_id: sub.plan_id, template_id: null,
    seat_quantity: agreement.seat_quantity, start_date: agreement.start_date, expiry_date: term?.expiry_date || agreement.expiry_date,
    payment_term_days: agreement.payment_term_days, validity_days: 30,
    discount_id: null, discount_ids: agreement.discount_rule_ids,
    lines: agreement.lines.filter((l): l is typeof l & {product_id: string} => l.product_id !== null).map(l => ({product_id: l.product_id, variant_id: l.variant_id,
      quantity: l.quantity, line_kind: l.kind, agreed_unit_price: l.kind === "ADDON" ? l.unit_price : undefined,
      override_reason: l.override_reason || undefined}))};
  const command = async (value: string) => {
    if (!window.confirm(`${value.toLowerCase()} this subscription?`)) return;
    if (await mutate("/commands", {action: value, expected_version: sub.version, request_key: crypto.randomUUID(),
      agreement_id: agreement.id, ...(value === "ABANDON" ? {reason} : {})})) setReason("");
  };
  const submitLifecycle = async (proposal?: DraftPayload) => {
    if (!reason.trim()) {setError("Give a reason for the requested change."); return false;}
    const date = proposal?.start_date || effective;
    const impact: Record<string, string> = {
      PAUSE: "Service and billing pause at this boundary. Resuming extends the term by the paused days.",
      RESUME: "Service resumes and billing restarts from this date; the term extends by the paused days.",
      EARLY_CLOSE: "Service ends on this date. Eligible unbilled periods remain payable.",
      RENEW: "The displayed commercial terms will apply to the new service term.",
      ADDON_CHANGE: "The displayed commercial terms will replace the current agreement from this boundary.",
    };
    if (!window.confirm(`${portal ? "Submit" : "Schedule"} ${action.replaceAll("_", " ").toLowerCase()} for ${date}? ${portal ? "The team must approve it before service changes. " : ""}${impact[action] || ""}`)) return false;
    const body = {action, effective_date: proposal?.start_date || effective, reason, proposal,
      expected_version: sub.version, ...(!portal ? {request_key: crypto.randomUUID()} : {})};
    if (await mutate(portal ? "/requests" : "/lifecycle", body)) {setAction(""); setReason(""); return true;}
    return false;
  };
  const eligible: string[] = [];
  if (sub.state === "ACTIVE" && term) {
    if (policies.allow_pause) eligible.push("PAUSE");
    if (!portal && policies.allow_early_closure) eligible.push("EARLY_CLOSE");
    eligible.push("ADDON_CHANGE");
  }
  if (sub.state === "PAUSED" && policies.allow_resume) eligible.push("RESUME");
  if (["ACTIVE", "CLOSED"].includes(sub.state) && term && policies.allow_renewal) eligible.push("RENEW");
  const pending = sub.events.some(e => !e.applied_at);
  return <section className="space-y-6">
    <Link className="text-sm text-blue-700 underline" href={`${base}/subscriptions`}>Back to subscriptions</Link>
    <header className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="break-all text-2xl font-bold">{sub.number}</h1><p className="text-slate-600">{sub.plan_name} · {sub.state} · {sub.seat_quantity} seats</p>{!portal && <Link href={`/app/customers/${sub.customer_id}`} className="text-blue-700 underline">{sub.customer_name}</Link>}</div><p className="text-sm text-slate-500">Next billing: {sub.next_billing_date || "Not scheduled"}</p></header>
    {error && <p role="alert" className="rounded bg-red-50 p-4 text-red-700">{error} <button type="button" className="underline" onClick={load}>Refresh</button></p>}
    {notice && <p role="status" className="rounded bg-emerald-50 p-4 text-emerald-800">{notice}</p>}
    {!portal && ["DRAFT", "QUOTATION", "CONFIRMED"].includes(sub.state) && <section className="space-y-3 rounded-lg border bg-white p-5"><h2 className="font-semibold">Quotation actions</h2><div className="flex flex-wrap gap-3">
      {["DRAFT", "QUOTATION"].includes(sub.state) && <button type="button" disabled={busy} className={secondaryStyle} data-discard-form onClick={() => setEditing(!editing)}>{editing ? "Close editor" : agreement.state === "DRAFT" ? "Edit draft" : "Revise quotation"}</button>}
      {agreement.state === "DRAFT" && <button type="button" disabled={busy} className={buttonStyle} onClick={() => command("ISSUE")}>Issue quotation</button>}
      {sub.state === "QUOTATION" && agreement.state === "ISSUED" && <button type="button" disabled={busy} className={buttonStyle} onClick={() => command("CONFIRM")}>Confirm agreement</button>}
      {sub.state === "CONFIRMED" && <button type="button" disabled={busy} className={buttonStyle} onClick={() => command("ACTIVATE")}>Activate service</button>}
    </div>{["DRAFT", "QUOTATION"].includes(sub.state) && <div className="flex flex-wrap gap-2"><label className="flex-1 text-sm">Reason for abandonment<input className={inputStyle} value={reason} onChange={e => setReason(e.target.value)} /></label><button type="button" disabled={busy || !reason.trim()} className={`${secondaryStyle} self-end text-red-700`} onClick={() => command("ABANDON")}>Abandon subscription</button></div>}</section>}
    {editing && <SubscriptionEditor key={agreement.id} initial={initial} onSave={async (payload, issue) => {
      const updated = await apiClient<Detail>(`/subscriptions/${id}`, {method: "PATCH", body: JSON.stringify({...payload, expected_version: sub.version})});
      setSub(updated); setEditing(false); setNotice("Draft saved.");
      if (issue) await mutate("/commands", {action: "ISSUE", expected_version: updated.version, request_key: crypto.randomUUID()});
    }} />}
    <section className="space-y-4 rounded-lg border bg-white p-5"><h2 className="font-semibold">Service terms</h2>{sub.terms.length ? sub.terms.map(t => <p key={t.id} className="text-sm">Term {t.sequence}: {t.start_date} → {t.expiry_date} (exclusive) · {t.interval}</p>) : <p className="text-sm text-slate-500">Proposed service: {agreement.start_date} → {agreement.expiry_date}. Awaiting acceptance.</p>}<p className="text-lg font-semibold">Recurring estimate {formatCurrency(activeAgreement.pricing_estimate.total)}</p><p className="text-sm text-slate-500">Subtotal {formatCurrency(activeAgreement.pricing_estimate.subtotal)} · Estimated discount {formatCurrency(activeAgreement.pricing_estimate.total_discount)} · Tax {formatCurrency(activeAgreement.pricing_estimate.total_tax)}</p></section>
    <section className="space-y-4"><h2 className="text-lg font-semibold">Agreement & quotation history</h2>{sub.agreements.map(a => <details key={a.id} open={a.id === agreement.id} className="rounded-lg border bg-white p-5"><summary className="cursor-pointer font-medium">Version {a.sequence} · {a.state} {a.quote_number && `· ${a.quote_number}`}</summary><p className="my-3 text-sm text-slate-600">{a.start_date} → {a.expiry_date} · {a.interval} · Payment within {a.payment_term_days} days{a.valid_until && ` · Quote valid through ${a.valid_until} inclusive`}</p>
      <ServicePolicySummary label="Agreed term policies" policies={a.policies} /><ScrollableRegion className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{["Charge", "Kind", "Qty", "Unit price", "Base amount", "Taxes", "Discount", "Estimated tax", "Estimated total"].map(h => <th key={h} className="p-2">{h}</th>)}</tr></thead><tbody>{a.lines.map(l => <tr key={l.id} className="border-t"><td className="p-2">{l.name} {l.variant_name && `(${l.variant_name})`}</td><td className="p-2">{l.kind}</td><td className="p-2">{l.quantity}</td><td className="p-2">{formatCurrency(l.unit_price)}</td><td className="p-2">{formatCurrency(l.subtotal)}</td><td className="p-2">{l.taxes.map(t => `${t.name} ${Number(t.rate)}%`).join(", ") || "—"}</td>{(["discount_amount", "tax_amount", "total"] as const).map(key => <td className="p-2" key={key}>{l[key] == null ? "Unavailable" : formatCurrency(l[key])}</td>)}</tr>)}</tbody></table></ScrollableRegion><p className="mt-3 text-sm text-slate-500">{a.discount_revision_ids.length ? "Assigned discount terms are pinned. Eligibility and available usage are checked per billing period." : "No discount assigned."} Quotation amounts are estimates until invoiced.</p></details>)}</section>
    {(eligible.length > 0 || pending) && <section className="space-y-4 rounded-lg border bg-white p-5"><h2 className="font-semibold">{portal ? "Request a change" : "Schedule a service change"}</h2>
      {pending ? <p className="text-sm text-slate-600">A scheduled change is awaiting its effective date.</p> : <><p className="text-sm text-slate-500">{portal ? "The team must review your request before it takes effect." : "Changes apply on approved service dates. Pause, closure and add-ons require a future unbilled boundary."}</p>
        <label className="block text-sm">Action<select className={inputStyle} value={action} onChange={e => {if (action && !window.confirm("Discard the change you are preparing?")) return; setAction(e.target.value); setEffective(""); setRequestProposal(null);}}><option value="">Select action</option>{eligible.map(a => <option key={a} value={a}>{a.replaceAll("_", " ")}</option>)}</select></label>
        {action && <><label className="block text-sm">Reason / note<textarea required className={inputStyle} value={reason} onChange={e => setReason(e.target.value)} /></label>
          {["RENEW", "ADDON_CHANGE"].includes(action) ? <SubscriptionEditor key={`${action}-${requestRevision}`} fixedIdentity portalId={portal ? id : undefined} changeAction={action} acceptedPolicies={policies} initial={requestProposal || {...initial, start_date: action === "RENEW" ? term.expiry_date : "", expiry_date: action === "RENEW" ? "" : term.expiry_date}} submitLabel={portal ? "Submit request" : "Accept & schedule change"} onSave={async proposal => {if (!(await submitLifecycle(proposal))) throw new Error("The change was not saved. Review the feedback above.");}} /> : <form className="flex flex-wrap items-end gap-3" onSubmit={async (e: FormEvent) => {e.preventDefault(); await submitLifecycle();}}><label className="text-sm">Effective date<input required type="date" className={inputStyle} value={effective} onChange={e => setEffective(e.target.value)} /></label><button type="submit" disabled={busy || !reason.trim()} className={buttonStyle}>{portal ? "Submit request" : "Schedule change"}</button></form>}</>}
      </>}
    </section>}
    <section className="space-y-3 rounded-lg border bg-white p-5"><h2 className="font-semibold">Recent invoices</h2>{sub.invoices.length ? sub.invoices.map(invoice => <p className="text-sm" key={invoice.id}><Link href={`${base}/invoices/${invoice.id}`} className="text-blue-700 underline">{invoice.number}</Link> · {invoice.period_start} · {invoice.state} · {formatCurrency(invoice.total)}</p>) : <p className="text-sm text-slate-500">No {portal ? "issued " : ""}invoices yet.</p>}<Link className="text-sm text-blue-700 underline" href={`${base}/invoices?subscription_id=${sub.id}`}>View all subscription invoices</Link></section>
    <section className="space-y-4 rounded-lg border bg-white p-5"><h2 className="font-semibold">Change requests</h2>{!sub.requests.length && <p className="text-sm text-slate-500">No change requests.</p>}{sub.requests.map(r => <article key={r.id} className="space-y-2 rounded border p-4"><p className="font-medium">{r.action.replaceAll("_", " ")} · {r.status} · {r.effective_date}</p><p className="text-sm">{r.note}</p>{r.proposal != null && <details><summary className="cursor-pointer text-sm text-blue-700">Requested commercial terms</summary><RequestEstimate value={r.price_summary} /></details>}{r.review_reason && <p className="text-sm text-slate-600">Team response: {r.review_reason}</p>}{r.reviewed_at && <p className="text-xs text-slate-500">Reviewed by {r.reviewer_name || "the team"} on {new Date(r.reviewed_at).toLocaleString("en-IN", {timeZone: "Asia/Kolkata"})} (Asia/Kolkata)</p>}
      {portal && r.status === "REJECTED" && eligible.includes(r.action) && !pending && <button type="button" className={secondaryStyle} onClick={() => {setAction(r.action); setEffective(r.effective_date); setReason(r.note); setRequestProposal(r.proposal ? r.proposal as DraftPayload : null); setRequestRevision(value => value + 1); setNotice("Previous request copied. Review the date, terms and team response before submitting a new request."); window.scrollTo({top: 0, behavior: "smooth"});}}>Prepare new request</button>}
      {r.status === "PENDING" && (portal ? <button type="button" disabled={busy} className={secondaryStyle} onClick={() => {if (window.confirm("Cancel this pending request? Service terms will stay unchanged.")) void mutate(`/requests/${r.id}/cancel`);}}>Cancel request</button> : <><button type="button" className={secondaryStyle} onClick={() => {setReviewId(r.id); setReviewReason("");}}>Review request</button>{reviewId === r.id && <form className="space-y-3" onSubmit={async e => {e.preventDefault(); const decision = ((e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement).value; if (!window.confirm(`${decision === "APPROVE" ? "Approve and schedule" : "Reject"} this ${r.action.replaceAll("_", " ").toLowerCase()} request for ${r.effective_date}? ${decision === "APPROVE" ? "The requested terms will take effect on the approved date." : "Service terms will stay unchanged; the customer will see your reason."}`)) return; if (await mutate(`/requests/${r.id}/review`, {decision, reason: reviewReason, expected_version: sub.version, request_key: crypto.randomUUID()})) {setReviewId(""); setReviewReason("");}}}><label className="block text-sm">Review reason<textarea required className={inputStyle} value={reviewReason} onChange={e => setReviewReason(e.target.value)} /></label><button type="submit" disabled={busy} value="APPROVE" className={buttonStyle}>Approve</button> <button type="submit" disabled={busy} value="REJECT" className={secondaryStyle}>Reject</button></form>}</>)}
    </article>)}</section>
    <section className="space-y-3 rounded-lg border bg-white p-5"><h2 className="font-semibold">Lifecycle history</h2>{sub.events.map((event) => <p key={event.id} className="text-sm">{event.effective_date} · {event.action.replaceAll("_", " ")} · {event.applied_at ? "Applied" : "Scheduled"}</p>)}{!sub.events.length && <p className="text-sm text-slate-500">No lifecycle changes yet.</p>}</section>
  </section>;
}

function RequestEstimate({value}: {value: unknown}) {
  if (!value || typeof value !== "object") return <p>No pricing changes.</p>;
  const estimate = value as {subtotal?: string; total_discount?: string; total_tax?: string; total?: string; lines?: {ordinal: number; description: string; quantity: number; total: string}[]};
  return <div className="space-y-2 py-3 text-sm">{estimate.lines?.map(line => <p key={line.ordinal}>{line.description} × {line.quantity} · {formatCurrency(line.total)}</p>)}<p>Subtotal {formatCurrency(estimate.subtotal)} · Discount {formatCurrency(estimate.total_discount)} · Tax {formatCurrency(estimate.total_tax)}</p><p className="font-semibold">Estimated total {formatCurrency(estimate.total)}</p></div>;
}
