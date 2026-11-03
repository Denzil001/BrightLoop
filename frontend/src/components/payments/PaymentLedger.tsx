"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { useCallback, useEffect, useState, useRef } from "react";
import Link from "next/link";
import CollectionSort from "@/components/CollectionSort";
import { useQueryState, useUrlFilters } from "@/lib/useUrlFilters";
import { apiClient } from "@/lib/api";
import { type Payment, paymentMethods } from "@/lib/payments";
import { errorMessage, inputStyle, secondaryStyle } from "@/lib/subscriptions";
import { formatCurrency } from "@/lib/utils";
import PaymentDrawer from "./PaymentDrawer";

export default function PaymentLedger({portal = false}: {portal?: boolean}) {
  const requestSequence = useRef(0);
  const [items, setItems] = useState<Payment[]>([]); const [total, setTotal] = useState(0); const [page, setPage] = useQueryState("page", 1);
  const [filters, setFilters] = useUrlFilters({search: "", method: "", date_from: "", date_to: ""});
  const [invoiceId, setInvoiceId] = useQueryState("invoice_id", ""); const [customerId, setCustomerId] = useQueryState("customer_id", "");
  const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [selected, setSelected] = useQueryState<string | null>("payment_id", null);
  const base = portal ? "/portal" : "/app";
  useEffect(() => {const params = new URLSearchParams(window.location.search); setFilters({search: params.get("search") || "", method: params.get("method") || "", date_from: params.get("date_from") || "", date_to: params.get("date_to") || ""}); setInvoiceId(params.get("invoice_id") || ""); setSelected(params.get("payment_id")); if (!portal) setCustomerId(params.get("customer_id") || "");}, [portal, setFilters, setInvoiceId, setSelected, setCustomerId]);
  const load = useCallback(async () => {const request = ++requestSequence.current; setLoading(true); setError(""); try {
    const params = new URLSearchParams({page: String(page)});
    Object.entries(filters).forEach(([key, value]) => {if (value) params.set(key, value);});
    if (invoiceId) params.set("invoice_id", invoiceId); if (customerId) params.set("customer_id", customerId);
    const result = await apiClient<{items: Payment[]; total: number}>(`/payments?${params}`); if (request !== requestSequence.current) return; setItems(result.items); setTotal(result.total);
  } catch (e) {if (request !== requestSequence.current) return; setError(errorMessage(e));} finally {if (request === requestSequence.current) setLoading(false);}}, [filters, page, invoiceId, customerId]);
  useEffect(() => {const timer = setTimeout(load, 250); return () => clearTimeout(timer);}, [load]);
  const update = (patch: Partial<typeof filters>) => {setFilters(previous => ({...previous, ...patch})); setPage(1);};
  return <section className="space-y-6">
      <div><h1 className="text-2xl font-bold">{portal ? "My payments" : "Payments ledger"}</h1><p className="text-sm text-slate-500">Permanent payment history with source invoices and downloadable receipts.</p></div>
      <CollectionSort fields={[["payment_date", "Payment date"], ["amount", "Amount"], ["created_at", "Recorded"]]} initial="payment_date" descending={true} onChange={() => {if (page === 1) load(); else setPage(1);}} />
    {invoiceId && <p className="rounded bg-blue-50 p-3 text-sm text-blue-900">Showing payments for the <Link className="underline" href={`${base}/invoices/${invoiceId}`}>selected invoice</Link>. <button type="button" className="underline" onClick={() => {setInvoiceId(""); setPage(1);}}>Show all invoices</button></p>}
    <div className="grid gap-3 rounded-lg border bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"><label className="text-sm">Invoice / reference search<input className={inputStyle} value={filters.search} placeholder={portal ? "Invoice number or reference" : "Customer, invoice or reference"} onChange={event => update({search: event.target.value})} /></label><label className="text-sm">Method<select aria-label="Payment method filter" className={inputStyle} value={filters.method} onChange={event => update({method: event.target.value})}><option value="">All methods</option>{paymentMethods.map(method => <option key={method} value={method}>{method.replaceAll("_", " ")}</option>)}</select></label><label className="text-sm">Payments from<input type="date" className={inputStyle} value={filters.date_from} onChange={event => update({date_from: event.target.value})} /></label><label className="text-sm">Payments through<input type="date" className={inputStyle} value={filters.date_to} onChange={event => update({date_to: event.target.value})} /></label></div>
    {error && <p role="alert" className="rounded bg-red-50 p-4 text-red-700">{error} <button type="button" onClick={load} className="underline">Retry</button></p>}
    {loading ? <p role="status">Loading payments…</p> : <ScrollableRegion className="overflow-x-auto rounded-lg border bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr>{["Payment", ...(!portal ? ["Customer"] : []), "Invoice", "Amount", "Method", "Date", "Reference", ...(!portal ? ["Recorded by"] : [])].map(title => <th className="p-3" key={title}>{title}</th>)}</tr></thead><tbody>{items.map(payment => <tr className="border-t" key={payment.id}><td className="p-3"><button type="button" className="text-blue-700 underline" onClick={() => setSelected(payment.id)}>{payment.id}</button></td>{!portal && <td className="p-3">{payment.customer_name}</td>}<td className="p-3"><Link href={`${base}/invoices/${payment.invoice_id}`} className="text-blue-700 underline">{payment.invoice_number}</Link></td><td className="p-3 whitespace-nowrap">{formatCurrency(payment.amount)}</td><td className="p-3">{payment.method.replaceAll("_", " ")}</td><td className="p-3 whitespace-nowrap">{payment.payment_date}</td><td className="p-3">{payment.reference || "—"}</td>{!portal && <td className="p-3">{payment.recorded_by}</td>}</tr>)}</tbody></table>{!items.length && <p className="p-8 text-center text-slate-500">No payments match these filters.</p>}</ScrollableRegion>}
    <div className="flex items-center justify-between text-sm"><span>{total} payments · Page {page}</span><div className="flex gap-2"><button type="button" disabled={page === 1 || loading} className={secondaryStyle} onClick={() => setPage(page - 1)}>Previous</button><button type="button" disabled={page * 20 >= total || loading} className={secondaryStyle} onClick={() => setPage(page + 1)}>Next</button></div></div>
    <PaymentDrawer id={selected} portal={portal} onClose={() => setSelected(null)} />
  </section>;
}
