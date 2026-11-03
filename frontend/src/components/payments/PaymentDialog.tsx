"use client";
import { decimalKey, subtractMoney } from "@/lib/decimal";
import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { InvoiceDetail } from "@/lib/invoices";
import { businessDate, paymentMethods } from "@/lib/payments";
import { buttonStyle, errorMessage, inputStyle, secondaryStyle } from "@/lib/subscriptions";
import { formatCurrency } from "@/lib/utils";
import { useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { trapDialogFocus } from "@/lib/dialogFocus";

export default function PaymentDialog({invoice, open, onClose, onRecorded, onRefresh}: {
  invoice: InvoiceDetail; open: boolean; onClose: () => void;
  onRecorded: (invoice: InvoiceDetail) => void; onRefresh: () => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null); const requestKey = useRef("");
  const {user} = useAuth();
  const storageKey = `brightloop-payment:${user?.id || "session"}:${invoice.id}`;
  const [amount, setAmount] = useState(""); const [method, setMethod] = useState("");
  const [date, setDate] = useState(businessDate()); const [note, setNote] = useState(""); const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [canStartNew, setCanStartNew] = useState(false);
  const dirty = open && Boolean(method || note || reference || (amount && decimalKey(amount) !== decimalKey(invoice.remaining)) || date !== businessDate());
  useUnsavedChanges(dirty);
  const projectedBalance = (() => {try {return subtractMoney(invoice.remaining, amount || "0", true);} catch {return null;}})();
  useEffect(() => {
    if (open) {
      if (!requestKey.current) {
        let pending = null;
        try {pending = JSON.parse(sessionStorage.getItem(storageKey) || "null");} catch { /* A malformed local draft is ignored. */ }
        if (typeof pending?.request_key === "string" && typeof pending.amount === "string" && typeof pending.method === "string" && typeof pending.note === "string" && typeof pending.payment_date === "string" && pending.invoice_id === invoice.id) {
          requestKey.current = pending.request_key; setAmount(pending.amount); setMethod(pending.method);
          setNote(pending.note); setReference(pending.reference || ""); setDate(pending.payment_date);
          setError("Your previous payment entry was restored. Review and retry to confirm its result.");
        } else {requestKey.current = crypto.randomUUID(); setAmount(invoice.remaining); setMethod(""); setNote(""); setReference(""); setDate(businessDate()); setError("");}
      }
      dialog.current?.showModal();
    } else dialog.current?.close();
  }, [open, invoice.remaining, invoice.id, storageKey]);
  return <dialog ref={dialog} tabIndex={-1} onKeyDown={event => trapDialogFocus(event, dialog.current)} aria-labelledby="record-payment-title" onCancel={event => {event.preventDefault(); if (!busy && (!dirty || window.confirm("You have unsaved payment details. Close without recording?"))) onClose();}}
    className="max-h-[90dvh] w-[90vw] max-w-lg overflow-y-auto rounded-xl border border-slate-200 p-0 backdrop:bg-slate-900/40">
    <form className="space-y-4 p-6" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(""); setCanStartNew(false);
      const payload = {amount, method, payment_date: date, note, reference: reference || null, request_key: requestKey.current};
      try {sessionStorage.setItem(storageKey, JSON.stringify({...payload, invoice_id: invoice.id}));} catch { /* Retry key remains in memory if browser storage is unavailable. */ }
      try {const result = await apiClient<{invoice: InvoiceDetail}>(`/invoices/${invoice.id}/payments`, {method: "POST",
        body: JSON.stringify(payload)});
        try {sessionStorage.removeItem(storageKey);} catch { /* Recording already succeeded. */ }
        requestKey.current = ""; onRecorded(result.invoice); onClose();
      } catch (error) {
        await onRefresh();
        if (error instanceof ApiError && error.status === 409 && error.message.includes("request key was already used")) {
          setCanStartNew(true); setError("A payment from this entry was already recorded with different details. Review payment history before starting a new entry.");
        } else setError(errorMessage(error));
      } finally {setBusy(false);}
    }}>
      <h2 id="record-payment-title" className="text-xl font-semibold">Record payment</h2><p className="text-sm text-slate-600">Outstanding balance: {formatCurrency(invoice.remaining)}</p>
      {error && <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {canStartNew && <button type="button" disabled={busy || Number(invoice.remaining) <= 0} className={secondaryStyle} onClick={() => {
        try {sessionStorage.removeItem(storageKey);} catch { /* The new in-memory key still separates the intent. */ }
        requestKey.current = crypto.randomUUID(); setAmount(invoice.remaining); setMethod(""); setNote(""); setReference(""); setDate(businessDate()); setError(""); setCanStartNew(false);
      }}>Start a new payment entry</button>}
      <label className="block text-sm">Amount received (₹)<input required type="number" min="0.01" step="0.01" max={invoice.remaining} className={inputStyle} value={amount} onChange={event => setAmount(event.target.value)} /></label>
      <label className="block text-sm">Payment method<select required aria-label="Payment method" className={inputStyle} value={method} onChange={event => setMethod(event.target.value)}><option value="">Select method</option>{paymentMethods.map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
      <label className="block text-sm">Payment date<input required type="date" max={businessDate()} className={inputStyle} value={date} onChange={event => setDate(event.target.value)} /></label>
      <label className="block text-sm">Customer-visible payment note<textarea required maxLength={2000} className={inputStyle} value={note} onChange={event => setNote(event.target.value)} /><span className="text-xs text-slate-500">This note appears in the customer&apos;s payment history.</span></label>
      <label className="block text-sm">Reference (optional)<input maxLength={128} className={inputStyle} value={reference} onChange={event => setReference(event.target.value)} /></label>
      <p className="rounded bg-blue-50 p-3 text-sm text-blue-900">Balance after payment: {projectedBalance === null ? "Enter a valid amount" : formatCurrency(projectedBalance)}</p>
      <div className="flex flex-wrap gap-2"><button type="submit" disabled={busy} className={buttonStyle}>{busy ? "Recording…" : "Save payment"}</button><button disabled={busy} type="button" data-discard-form className={secondaryStyle} onClick={onClose}>Close</button></div>
    </form>
  </dialog>;
}
