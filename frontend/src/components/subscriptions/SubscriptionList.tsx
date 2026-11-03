"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { useCallback, useEffect, useState, useRef } from "react";
import Link from "next/link";
import { formatCurrency } from "@/lib/utils";
import CollectionSort from "@/components/CollectionSort";
import { useQueryState } from "@/lib/useUrlFilters";
import { apiClient } from "@/lib/api";
import { buttonStyle, errorMessage, inputStyle, secondaryStyle, type SubscriptionSummary } from "@/lib/subscriptions";

export default function SubscriptionList({portal = false}: {portal?: boolean}) {
  const requestSequence = useRef(0);
  const [data, setData] = useState<{items: SubscriptionSummary[]; total: number}>({items: [], total: 0});
  const [search, setSearch] = useQueryState("search", ""); const [state, setState] = useQueryState("state", "");
  const [planSearch, setPlanSearch] = useQueryState("plan_search", ""); const [billingBefore, setBillingBefore] = useQueryState("billing_before", ""); const [expiryBefore, setExpiryBefore] = useQueryState("expiry_before", "");
  const [pending, setPending] = useQueryState("pending_requests", false); const [page, setPage] = useQueryState("page", 1);
  const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const [serviceActive, setServiceActive] = useQueryState("service_active", false);
  const [customerId, setCustomerId] = useState("");
  useEffect(() => {const params = new URLSearchParams(window.location.search); if (!portal) setCustomerId(params.get("customer_id") || ""); setState(params.get("state") || ""); setPending(params.get("pending_requests") === "true"); setBillingBefore(params.get("billing_before") || ""); setExpiryBefore(params.get("expiry_before") || ""); setServiceActive(params.get("service_active") === "true");}, [portal, setState, setPending, setBillingBefore, setExpiryBefore, setServiceActive]);
  const base = portal ? "/portal" : "/app";
  const load = useCallback(async () => {const request = ++requestSequence.current;
    setLoading(true); setError("");
    try { const result = await apiClient<{items: SubscriptionSummary[]; total: number}>(`/subscriptions?${new URLSearchParams({search, state, ...(customerId ? {customer_id: customerId} : {}), page: String(page), service_active: String(serviceActive), pending_requests: String(pending), plan_search: planSearch, ...(billingBefore ? {billing_before: billingBefore} : {}), ...(expiryBefore ? {expiry_before: expiryBefore} : {})})}`); if (request !== requestSequence.current) return; setData(result); }
    catch (e) {if (request !== requestSequence.current) return;  setError(errorMessage(e)); } finally { if (request === requestSequence.current) setLoading(false); }
  }, [search, state, page, pending, planSearch, billingBefore, expiryBefore, customerId, serviceActive]);
  useEffect(() => { const timer = setTimeout(load, 250); return () => clearTimeout(timer); }, [load]);
  return <section className="space-y-6">

    <div className="flex flex-wrap items-center justify-between gap-4"><div><h1 className="text-2xl font-bold text-slate-900">{portal ? "My subscriptions" : "Subscriptions & quotations"}</h1><p className="text-sm text-slate-500">Service agreements, quotations and scheduled changes.</p></div>
      {!portal && <Link className={buttonStyle} href="/app/subscriptions/new">New subscription</Link>}</div>
      <CollectionSort fields={[["created_at", "Created"], ["number", "Number"], ["next_billing_date", "Next billing"], ["expiry_date", "Expiry"]]} initial="created_at" descending={true} onChange={() => {if (page === 1) load(); else setPage(1);}} />
    <label className="block text-sm"><input type="checkbox" checked={serviceActive} onChange={e => {setServiceActive(e.target.checked); setPage(1);}} /> Active service today (excludes paused/ended)</label>
    <div className="flex flex-wrap gap-3 rounded-lg border bg-white p-4">
      <label className="flex-1 min-w-48 text-sm">Search<input className={inputStyle} value={search} placeholder="Number, quotation or customer" onChange={e => {setSearch(e.target.value); setPage(1);}} /></label>
      <label className="text-sm">Status<select className={inputStyle} value={state} onChange={e => {setState(e.target.value); setPage(1);}}><option value="">All statuses</option>{["DRAFT", "QUOTATION", "CONFIRMED", "ACTIVE", "PAUSED", "CLOSED", "ENDED"].map(s => <option key={s}>{s}</option>)}</select></label>
      <label className="text-sm">Plan name<input className={inputStyle} value={planSearch} onChange={e => {setPlanSearch(e.target.value); setPage(1);}} /></label>
      <label className="text-sm">Billing on/before<input type="date" className={inputStyle} value={billingBefore} onChange={e => {setBillingBefore(e.target.value); setPage(1);}} /></label>
      <label className="text-sm">Expiry on/before<input type="date" className={inputStyle} value={expiryBefore} onChange={e => {setExpiryBefore(e.target.value); setPage(1);}} /></label>
      {!portal && <label className="self-end py-2 text-sm"><input type="checkbox" checked={pending} onChange={e => {setPending(e.target.checked); setPage(1);}} /> Pending requests</label>}
    </div>
    {error && <div role="alert" className="rounded bg-red-50 p-4 text-red-700">{error} <button type="button" onClick={load} className="underline">Retry</button></div>}
    {loading ? <p role="status">Loading subscriptions…</p> : <ScrollableRegion className="overflow-x-auto rounded-lg border bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr>{["Number", ...(!portal ? ["Customer"] : []), "Plan", "Status", "Seats", "Recurring estimate", "Next billing", "Expiry", ...(!portal ? ["Requests"] : [])].map(h => <th className="p-4" key={h}>{h}</th>)}</tr></thead><tbody>{data.items.map(item => <tr key={item.id} className="border-t hover:bg-slate-50"><td className="p-4"><Link className="font-medium text-blue-700 underline" href={`${base}/subscriptions/${item.id}`}>{item.number}</Link></td>{!portal && <td className="p-4">{item.customer_name}</td>}<td className="p-4">{item.plan_name}</td><td className="p-4">{item.state}{item.ended && " · Ended"}</td><td className="p-4">{item.seat_quantity}</td><td className="p-4">{formatCurrency(item.recurring_amount)}</td><td className="p-4">{item.next_billing_date || "—"}</td><td className="p-4">{item.expiry_date || "—"}</td>{!portal && <td className="p-4">{item.request_count || 0}</td>}</tr>)}</tbody></table>{!data.items.length && <p className="p-8 text-center text-slate-500">No subscriptions match your filters.{portal && " The team will prepare your subscription."}</p>}</ScrollableRegion>}
    <div className="flex items-center justify-between text-sm"><span>{data.total} subscriptions · Page {page}</span><div className="flex gap-2"><button type="button" className={secondaryStyle} disabled={page === 1 || loading} onClick={() => setPage(page - 1)}>Previous</button><button type="button" className={secondaryStyle} disabled={page * 20 >= data.total || loading} onClick={() => setPage(page + 1)}>Next</button></div></div>
  </section>;
}
