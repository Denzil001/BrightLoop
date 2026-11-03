"use client";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api";
import type { Dashboard as Data } from "@/lib/reporting";
import { businessDate } from "@/lib/payments";
import { errorMessage, inputStyle, secondaryStyle } from "@/lib/subscriptions";
import { formatCurrency } from "@/lib/utils";

export default function Dashboard({portal = false}: {portal?: boolean}) {
  const today = businessDate();
  const [first, setFirst] = useState(`${today.slice(0, 8)}01`); const [last, setLast] = useState(today);
  const [data, setData] = useState<Data | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const requestSequence = useRef(0);
  const initialLoad = useRef(true);
  const base = portal ? "/portal" : "/app";
  const load = useCallback(async () => {const request = ++requestSequence.current; setLoading(true); setError(""); try {const result = await apiClient<Data>(`/dashboard?${new URLSearchParams({date_from: first, date_to: last})}`); if (request === requestSequence.current) setData(result);} catch (e) {if (request === requestSequence.current) setError(errorMessage(e));} finally {if (request === requestSequence.current) setLoading(false);}}, [first, last]);
  useEffect(() => {requestSequence.current += 1; setLoading(true); const timer = setTimeout(load, initialLoad.current ? 0 : 200); initialLoad.current = false; return () => clearTimeout(timer);}, [load]);
  const range = new URLSearchParams({date_from: first, date_to: last}).toString();
  return <section className="space-y-6"><div className="flex flex-wrap justify-between gap-4"><div><h1 className="text-2xl font-bold">{portal ? "My overview" : "Operational overview"}</h1><p className="text-sm text-slate-500">Current service and balances; payments use the selected date range.</p></div><button type="button" className={secondaryStyle} disabled={loading} onClick={load}>Refresh overview</button></div>
    <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-white p-4"><label className="text-sm">Payments from<input className={inputStyle} type="date" value={first} onChange={e => setFirst(e.target.value)} /></label><label className="text-sm">Payments through<input className={inputStyle} type="date" value={last} onChange={e => setLast(e.target.value)} /></label>{!portal && <Link className={secondaryStyle} href="/app/subscriptions/new">Create subscription</Link>}</div>
    {error && <p role="alert" className="rounded bg-red-50 p-4 text-red-700">{error} <button type="button" className="underline" onClick={load}>Retry</button></p>}
    {loading ? <p role="status">Loading overview…</p> : data && <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {data.role === "STAFF" ? <><Card title="Quotes awaiting confirmation" value={String(data.quote_count)} href="/app/subscriptions?state=QUOTATION" /><Card title="Pending customer requests" value={String(data.pending_request_count)} href="/app/subscriptions?pending_requests=true" /><Card title="Subscriptions due for billing" value={String(data.due_subscription_count)} href={`/app/subscriptions?billing_before=${data.as_of_date}`} /><Card title="Draft invoices needing action" value={String(data.invoice_action_count)} href="/app/invoices?state=DRAFT" /></> : <>
          <Card title="Active service today" value={String(data.metrics?.active_subscriptions || 0)} href={`${base}/subscriptions?service_active=true`} />
          {data.role === "ADMIN" && <Card title="Payments received in range" value={formatCurrency(data.metrics?.received)} href={`/app/reports?view=receipts&${range}`} />}
          <Card title="Current outstanding" value={formatCurrency(data.metrics?.outstanding)} href={`${base}/invoices?outstanding=true`} /><Card title="Current overdue" value={formatCurrency(data.metrics?.overdue)} href={`${base}/invoices?overdue=true`} />
          {portal && <Card title="Next billing date" value={data.next_billing_date || "Not scheduled"} href="/portal/subscriptions" />}
        </>}
      </div>
      {portal && !data.metrics?.active_subscriptions && <p className="rounded bg-blue-50 p-4 text-sm text-blue-900">The team prepares your subscriptions. Review your agreements and pending requests below.</p>}
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title={`Pending requests (${data.pending_request_count})`}>{data.pending_requests.length ? data.pending_requests.map(r => <p className="text-sm" key={r.id}><Link className="break-all text-blue-700 underline" href={`${base}/subscriptions/${r.subscription_id}`}>{r.number}</Link> · {r.type.replaceAll("_", " ")} · {r.requested_date}</p>) : <Empty />}</Panel>
        <Panel title="Expiry / renewal reminders — next 30 days">{data.ending_subscriptions.length ? data.ending_subscriptions.map(s => <p className="text-sm" key={s.id}><Link className="break-all text-blue-700 underline" href={`${base}/subscriptions/${s.id}`}>{s.plan_name} · {s.number}</Link><br />Expires {s.expiry_date}</p>) : <Empty />}</Panel>
        {data.role === "STAFF" && <><Panel title="Quotations awaiting attention">{data.quotes?.length ? data.quotes.map(s => <p className="text-sm" key={s.id}><Link href={`/app/subscriptions/${s.id}`} className="break-all text-blue-700 underline">{s.number}</Link> · {s.customer_name}</p>) : <Empty />}</Panel><Panel title="Due billing / overdue attention">{data.due_subscriptions?.length ? data.due_subscriptions.map(s => <p className="text-sm" key={s.id}><Link href={`/app/subscriptions/${s.id}`} className="break-all text-blue-700 underline">{s.number}</Link> · Due {s.next_billing_date}</p>) : <Empty />}<Link className="text-sm text-blue-700 underline" href="/app/invoices?overdue=true">View {data.overdue_count} overdue invoices</Link></Panel></>}
        <Panel title="Recent issued invoices">{data.recent_invoices.length ? data.recent_invoices.map(i => <p className="text-sm" key={i.id}><Link className="break-all text-blue-700 underline" href={`${base}/invoices/${i.id}`}>{i.number}</Link> · {i.state} · Outstanding {formatCurrency(i.remaining)}</p>) : <Empty />}<Link href={`${base}/invoices`} className="text-sm text-blue-700 underline">All invoices</Link></Panel>
        <Panel title="Recent payments in range">{data.recent_payments.length ? data.recent_payments.map(p => <p className="text-sm" key={p.id}><Link className="text-blue-700 underline" href={`${base}/payments?invoice_id=${p.invoice_id}&payment_id=${p.id}`}>{p.payment_date} · {formatCurrency(p.amount)}</Link> · {p.method?.replaceAll("_", " ")}</p>) : <Empty />}<Link href={`${base}/payments?${range}`} className="text-sm text-blue-700 underline">All payments in range</Link></Panel>
      </div><p className="text-xs text-slate-500">Current snapshot: {data.as_of_date} · Query time: {data.query_time_ms} ms. Current balances are independent of the payment-date range.</p>
    </>}
  </section>;
}
function Card({title, value, href}: {title: string; value: string; href: string}) {return <Link href={href} className="rounded-xl border bg-white p-5 hover:border-blue-400"><p className="text-sm text-slate-500">{title}</p><p className="mt-2 break-words text-2xl font-semibold">{value}</p></Link>;}
function Panel({title, children}: {title: string; children: ReactNode}) {return <section className="space-y-3 rounded-lg border bg-white p-5"><h2 className="font-semibold">{title}</h2>{children}</section>;}
function Empty() {return <p className="text-sm text-slate-500">No matching records.</p>;}
