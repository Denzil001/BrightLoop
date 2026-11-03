"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { useCallback, useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useQueryState, useUrlFilters } from "@/lib/useUrlFilters";
import { apiClient } from "@/lib/api";
import type { InvoiceSummary } from "@/lib/invoices";
import { errorMessage, inputStyle, secondaryStyle } from "@/lib/subscriptions";
import { formatCurrency } from "@/lib/utils";

export default function InvoiceList({portal = false}: {portal?: boolean}) {
  const requestSequence = useRef(0);
  const [items, setItems] = useState<InvoiceSummary[]>([]); const [total, setTotal] = useState(0);
  const [filters, setFilters] = useUrlFilters({search: "", state: "", overdue: false, outstanding: false, issue_from: "", issue_to: "", due_from: "", due_to: "", sort: "invoice_date", descending: true});
  const [customerId, setCustomerId] = useQueryState("customer_id", ""); const [subscriptionId, setSubscriptionId] = useQueryState("subscription_id", ""); const [page, setPage] = useQueryState("page", 1);
  const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const base = portal ? "/portal" : "/app";
  useEffect(() => {const params = new URLSearchParams(window.location.search); if (!portal) setCustomerId(params.get("customer_id") || ""); setSubscriptionId(params.get("subscription_id") || ""); setFilters(prev => ({...prev, state: params.get("state") || "", overdue: params.get("overdue") === "true", outstanding: params.get("outstanding") === "true", issue_from: params.get("issue_from") || "", issue_to: params.get("issue_to") || "", due_from: params.get("due_from") || "", due_to: params.get("due_to") || ""}));}, [portal, setCustomerId, setSubscriptionId, setFilters]);
  const load = useCallback(async () => {const request = ++requestSequence.current; setLoading(true); setError(""); try {
    const params = new URLSearchParams({page: String(page)});
    Object.entries(filters).forEach(([key, value]) => {if (value !== "") params.set(key, String(value));});
    if (customerId) params.set("customer_id", customerId); if (subscriptionId) params.set("subscription_id", subscriptionId);
    const result = await apiClient<{items: InvoiceSummary[]; total: number}>(`/invoices?${params}`); if (request !== requestSequence.current) return;
    setItems(result.items); setTotal(result.total);
  } catch (e) {if (request !== requestSequence.current) return; setError(errorMessage(e));} finally {if (request === requestSequence.current) setLoading(false);}}, [filters, page, customerId, subscriptionId]);
  useEffect(() => {const timer = setTimeout(load, 250); return () => clearTimeout(timer);}, [load]);
  const update = (patch: Partial<typeof filters>) => {setFilters(previous => ({...previous, ...patch})); setPage(1);};
  return <section className="space-y-6"><div><h1 className="text-2xl font-bold">{portal ? "My invoices" : "Invoices"}</h1><p className="text-sm text-slate-500">{portal ? "Issued invoices and current balances. Contact the team for payment arrangements." : "Invoices generated from agreed service periods, with persisted payment balances."}</p></div>
    <div className="grid gap-3 rounded-lg border bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
      <label className="text-sm">Search<input className={inputStyle} value={filters.search} placeholder="Invoice, subscription or customer" onChange={e => update({search: e.target.value})} /></label>
      <label className="text-sm">Status<select aria-label="Invoice status" className={inputStyle} value={filters.state} onChange={e => update({state: e.target.value})}><option value="">All statuses</option>{(portal ? ["CONFIRMED", "PARTIALLY_PAID", "PAID", "CANCELLED"] : ["DRAFT", "CONFIRMED", "PARTIALLY_PAID", "PAID", "CANCELLED"]).map(state => <option key={state}>{state}</option>)}</select></label>
      <label className="text-sm">Sort<select aria-label="Invoice sort" className={inputStyle} value={filters.sort} onChange={e => update({sort: e.target.value})}><option value="invoice_date">Invoice date</option><option value="due_date">Due date</option><option value="number">Number</option><option value="total">Amount</option></select></label>
      <label className="self-end py-2 text-sm"><input type="checkbox" checked={filters.descending} onChange={e => update({descending: e.target.checked})} /> Descending</label>
      {(["issue_from", "issue_to", "due_from", "due_to"] as const).map((key, i) => <label className="text-sm" key={key}>{["Issued from", "Issued through", "Due from", "Due through"][i]}<input className={inputStyle} type="date" value={filters[key]} onChange={e => update({[key]: e.target.value})} /></label>)}
      <label className="text-sm"><input type="checkbox" checked={filters.overdue} onChange={e => update({overdue: e.target.checked})} /> Overdue only</label>
      <label className="text-sm"><input type="checkbox" checked={filters.outstanding} onChange={e => update({outstanding: e.target.checked})} /> Outstanding only</label>
    </div>
    {error && <p role="alert" className="rounded bg-red-50 p-4 text-red-700">{error} <button type="button" className="underline" onClick={load}>Retry</button></p>}
    {loading ? <p role="status">Loading invoices…</p> : <ScrollableRegion className="overflow-x-auto rounded-lg border bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr>{["Invoice", ...(!portal ? ["Customer"] : []), "Period", "Issued / due", "Total", "Paid", "Outstanding", "Status"].map(h => <th className="p-3" key={h}>{h}</th>)}</tr></thead><tbody>{items.map(item => <tr key={item.id} className="border-t"><td className="p-3"><Link href={`${base}/invoices/${item.id}`} className="text-blue-700 underline">{item.number}</Link></td>{!portal && <td className="p-3">{item.customer_name}</td>}<td className="p-3 whitespace-nowrap">{item.period_start}<br />to {item.period_end}</td><td className="p-3 whitespace-nowrap">{item.invoice_date}<br />Due {item.due_date}</td>{(["total", "paid", "remaining"] as const).map(key => <td key={key} className="p-3 whitespace-nowrap">{formatCurrency(item[key])}</td>)}<td className="p-3">{item.state}{item.overdue && <span className="block font-medium text-red-700">Overdue</span>}</td></tr>)}</tbody></table>{!items.length && <p className="p-8 text-center text-slate-500">No invoices match these filters.</p>}</ScrollableRegion>}
    <div className="flex items-center justify-between text-sm"><span>{total} invoices · Page {page}</span><div className="flex gap-2"><button type="button" disabled={page === 1 || loading} className={secondaryStyle} onClick={() => setPage(page - 1)}>Previous</button><button type="button" disabled={page * 20 >= total || loading} className={secondaryStyle} onClick={() => setPage(page + 1)}>Next</button></div></div>
  </section>;
}
