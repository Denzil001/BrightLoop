"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import PaymentDialog from "@/components/payments/PaymentDialog";
import PaymentDrawer from "@/components/payments/PaymentDrawer";
import { apiClient } from "@/lib/api";
import type { InvoiceDetail as Detail } from "@/lib/invoices";
import { buttonStyle, errorMessage, inputStyle, secondaryStyle } from "@/lib/subscriptions";
import { formatCurrency } from "@/lib/utils";
import { useDialogChanges, useUnsavedChanges } from "@/lib/useUnsavedChanges";

export default function InvoiceDetail({id, portal = false}: {id: string; portal?: boolean}) {
  const [invoice, setInvoice] = useState<Detail | null>(null); const [error, setError] = useState("");
  const [paymentOpen, setPaymentOpen] = useState(false); const [selectedPayment, setSelectedPayment] = useState<string | null>(null);
  const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false); const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState(""); const [metadata, setMetadata] = useState({due_date: "", customer_name: "", customer_email: "", customer_company: "", customer_address: {} as Record<string, string | null>});
  const base = portal ? "/portal" : "/app";
  const correctionDirty = useDialogChanges(editing, [metadata, reason]);
  useUnsavedChanges(correctionDirty || Boolean(reason));
  const load = useCallback(async () => {setError(""); try {
    const value = await apiClient<Detail>(`/invoices/${id}`); setInvoice(value);
    setMetadata({due_date: value.due_date, customer_name: value.customer_name, customer_email: value.customer_email,
      customer_company: value.customer_company || "", customer_address: value.customer_address});
  } catch (e) {setError(errorMessage(e));}}, [id]);
  useEffect(() => {load();}, [load]);
  const act = async (path: string, body?: unknown, method = "POST") => {setBusy(true); setError(""); setNotice(""); try {
    await apiClient(`/invoices/${id}${path}`, {method, ...(body ? {body: JSON.stringify(body)} : {})});
    await load(); setNotice(path === "/send" ? "Invoice email sent." : "Invoice updated."); setEditing(false); if (path !== "/send") setReason("");
  } catch (e) {await load(); if (path === "/draft-metadata") {setMetadata(metadata); setEditing(true);} setError(errorMessage(e));} finally {setBusy(false);}};
  const download = async () => {setBusy(true); setError(""); try {
    const document = await apiClient<Blob>(`/invoices/${id}/document?download=true`, {responseType: "blob"});
    const url = URL.createObjectURL(document); const link = window.document.createElement("a");
    link.href = url; link.download = `${invoice?.number || "invoice"}.pdf`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e) {setError(errorMessage(e));} finally {setBusy(false);}};
  if (!invoice) return <section>{error ? <p role="alert">{error} <button type="button" className="underline" onClick={load}>Retry</button></p> : <p role="status">Loading invoice…</p>}</section>;
  const address = (data: Record<string, string | null>) => ["address_line1", "address_line2", "city", "state", "postal_code", "country"].map(key => data[key]).filter(Boolean).join(", ");
  const command = (action: string) => {if (window.confirm(`${action.toLowerCase()} this invoice?`)) act("/commands", {
    action, expected_version: invoice.version, request_key: crypto.randomUUID(), ...(action === "CANCEL" ? {reason} : {})});};
  return <section className="space-y-6">
    <style jsx global>{`@media print { body {background:white!important;} header,nav,footer,.no-print {display:none!important;} main {max-width:none!important;padding:0!important;} table {font-size:10px;} section {break-inside:auto;} tr {break-inside:avoid;} }`}</style>
    <Link href={`${base}/invoices`} className="no-print text-sm text-blue-700 underline">Back to invoices</Link>
    <div className="flex flex-wrap justify-between gap-4"><div><h1 className="break-all text-2xl font-bold">{invoice.number}</h1><p className="font-medium">{invoice.state}{invoice.overdue && <span className="ml-2 text-red-700">Overdue</span>}</p><p className="text-sm text-slate-500">{invoice.period_start} → {invoice.period_end} (end exclusive)</p></div><div className="no-print flex flex-wrap items-start gap-2"><button type="button" disabled={busy} className={secondaryStyle} onClick={() => window.print()}>Print</button><button type="button" disabled={busy} className={buttonStyle} onClick={download}>Download PDF</button></div></div>
    {error && <p role="alert" className="no-print rounded bg-red-50 p-4 text-red-700">{error}</p>}{notice && <p role="status" className="no-print rounded bg-emerald-50 p-4 text-emerald-800">{notice}</p>}
    {invoice.state === "DRAFT" && <p className="rounded bg-amber-50 p-4 text-amber-900">Draft preview. This invoice has not been issued and is not payable.</p>}
    {invoice.state === "CANCELLED" && <p className="rounded bg-red-50 p-4 text-red-800">Cancelled invoice. Retained as history and excluded from payable balances.</p>}
    <div className="grid gap-5 rounded-lg border bg-white p-5 sm:grid-cols-2"><div><h2 className="mb-2 text-sm font-semibold text-slate-500">From</h2><p className="font-semibold">{invoice.issuer_name}</p><p className="text-sm">Tax ID: {invoice.issuer_tax_id || "—"}</p><p className="text-sm text-slate-600">{address(invoice.issuer_address)}</p></div><div><h2 className="mb-2 text-sm font-semibold text-slate-500">Bill to</h2><p className="font-semibold">{invoice.customer_name}</p><p className="text-sm">{invoice.customer_company}</p><p className="break-all text-sm">{invoice.customer_email}</p><p className="text-sm text-slate-600">{address(invoice.customer_address)}</p></div><p className="text-sm">Invoice date: {invoice.invoice_date}<br />Due date: {invoice.due_date}<br />Currency: {invoice.currency}</p><Link className="no-print self-end text-sm text-blue-700 underline" href={`${base}/subscriptions/${invoice.subscription_id}`}>View subscription</Link></div>
    {invoice.service_days !== invoice.full_period_days && <p className="rounded bg-blue-50 p-4 text-sm text-blue-900">Partial period: {invoice.service_days}/{invoice.full_period_days} days. Unit prices show full-period agreed rates; base amounts are prorated.</p>}
    <ScrollableRegion className="overflow-x-auto rounded-lg border bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr>{["Charge", "Qty", "Unit price", "Base", "Discount", "Tax", "Total"].map(title => <th key={title} className="p-3">{title}</th>)}</tr></thead><tbody>{invoice.lines.map(line => <tr key={line.id} className="border-t align-top"><td className="p-3"><p>{line.description}</p>{line.taxes.map((tax) => <p className="text-xs text-slate-500" key={`${tax.name}:${tax.rate}`}>{tax.name} {Number(tax.rate)}% · {formatCurrency(tax.amount)}</p>)}</td><td className="p-3">{line.quantity}</td>{(["unit_price", "subtotal", "discount", "tax", "total"] as const).map(key => <td key={key} className="p-3 whitespace-nowrap">{formatCurrency(line[key])}</td>)}</tr>)}</tbody></table></ScrollableRegion>
    <div className="ml-auto max-w-md space-y-2 rounded-lg border bg-white p-5">{[["Subtotal", invoice.subtotal], ["Discount", invoice.discount_total], ["Tax", invoice.tax_total], ["Invoice total", invoice.total], ["Paid", invoice.paid], ["Outstanding", invoice.remaining]].map(([label, amount]) => <p key={label} className="flex justify-between gap-6"><span>{label}</span><span className={label === "Outstanding" ? "font-bold text-blue-800" : "font-medium"}>{formatCurrency(amount)}</span></p>)}</div>
    <section className="space-y-3 rounded-lg border bg-white p-5"><h2 className="font-semibold">Payment history</h2>{invoice.payments.length ? invoice.payments.map(payment => <p className="text-sm" key={payment.id}><button type="button" className="no-print text-blue-700 underline" onClick={() => setSelectedPayment(payment.id)}>View payment {payment.id.slice(0, 8)}</button> · {payment.payment_date} · {payment.method.replaceAll("_", " ")} · {formatCurrency(payment.amount)}{payment.reference && ` · ${payment.reference}`}</p>) : <p className="text-sm text-slate-500">No recorded payments.</p>}<Link href={`${base}/payments?invoice_id=${invoice.id}`} className="no-print text-sm text-blue-700 underline">View all {invoice.payment_count} payments</Link></section>
    <PaymentDrawer id={selectedPayment} portal={portal} onClose={() => setSelectedPayment(null)} />
    {!portal && <PaymentDialog invoice={invoice} open={paymentOpen} onClose={() => setPaymentOpen(false)} onRefresh={load} onRecorded={updated => {setInvoice(updated); setNotice("Payment recorded.");}} />}
    {portal && <p className="text-sm text-slate-500">For payment queries, contact the team using your usual contact details and quote this invoice number.</p>}
    {!portal && <section className="no-print space-y-4 rounded-lg border bg-white p-5"><h2 className="font-semibold">Invoice actions</h2>{invoice.issued_at && ["CONFIRMED", "PARTIALLY_PAID"].includes(invoice.state) && Number(invoice.remaining) > 0 && <button type="button" disabled={busy} className={buttonStyle} onClick={() => setPaymentOpen(true)}>Record payment</button>}<div className="flex flex-wrap gap-2">{invoice.state === "DRAFT" && <><button type="button" disabled={busy} className={secondaryStyle} data-discard-form onClick={() => setEditing(!editing)}>{editing ? "Close correction editor" : "Correct billing metadata"}</button><button type="button" disabled={busy || editing} className={buttonStyle} onClick={() => command("CONFIRM")}>Confirm invoice</button></>}{invoice.issued_at && invoice.state !== "CANCELLED" && <button type="button" disabled={busy} className={buttonStyle} onClick={() => act("/send")}>Send invoice email</button>}</div>
      {editing && <form className="grid gap-3 sm:grid-cols-2" onSubmit={e => {e.preventDefault(); act("/draft-metadata", {...metadata, customer_company: metadata.customer_company || null, expected_version: invoice.version, reason}, "PATCH");}}>
        <label className="text-sm">Due date<input required className={inputStyle} type="date" min={invoice.invoice_date} value={metadata.due_date} onChange={e => setMetadata({...metadata, due_date: e.target.value})} /></label>
        <label className="text-sm">Billing name<input required className={inputStyle} value={metadata.customer_name} onChange={e => setMetadata({...metadata, customer_name: e.target.value})} /></label>
        <label className="text-sm">Billing email<input required type="email" className={inputStyle} value={metadata.customer_email} onChange={e => setMetadata({...metadata, customer_email: e.target.value})} /></label>
        <label className="text-sm">Company<input className={inputStyle} value={metadata.customer_company} onChange={e => setMetadata({...metadata, customer_company: e.target.value})} /></label>
        {["address_line1", "address_line2", "city", "state", "postal_code", "country"].map(key => <label className="text-sm" key={key}>{key.replaceAll("_", " ")}<input className={inputStyle} value={metadata.customer_address[key] || ""} onChange={e => setMetadata({...metadata, customer_address: {...metadata.customer_address, [key]: e.target.value || null}})} /></label>)}
        <label className="text-sm sm:col-span-2">Correction reason<input required className={inputStyle} value={reason} onChange={e => setReason(e.target.value)} /></label><button type="submit" disabled={busy} className={buttonStyle}>Save correction</button>
      </form>}
      {["DRAFT", "CONFIRMED"].includes(invoice.state) && Number(invoice.paid) === 0 && <div className="flex flex-wrap items-end gap-3"><label className="flex-1 text-sm">Cancellation reason<input className={inputStyle} value={reason} onChange={e => setReason(e.target.value)} /></label><button type="button" disabled={busy || editing || !reason.trim()} className={`${secondaryStyle} text-red-700`} onClick={() => command("CANCEL")}>Cancel invoice</button></div>}
    </section>}
    {!portal && <section className="no-print space-y-3 rounded-lg border bg-white p-5"><h2 className="font-semibold">Delivery attempts</h2>{invoice.delivery_attempts?.length ? invoice.delivery_attempts.map(attempt => <p key={attempt.id} className="text-sm">{new Date(attempt.attempted_at).toLocaleString()} · {attempt.status}{attempt.safe_error_code && " · Delivery was not confirmed; retry when ready."}</p>) : <p className="text-sm text-slate-500">No email attempts.</p>}</section>}
    {!portal && <section className="no-print space-y-2 rounded-lg border bg-white p-5"><h2 className="font-semibold">Action history</h2>{invoice.history?.map((event) => <p className="text-sm" key={event.id}>{new Date(event.timestamp).toLocaleString()} · {event.action.replaceAll("_", " ")}{event.reason && ` · ${event.reason}`}</p>)}</section>}
  </section>;
}
