"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiClient, downloadFile } from "@/lib/api";
import type { Payment } from "@/lib/payments";
import { buttonStyle, errorMessage, secondaryStyle } from "@/lib/subscriptions";
import { formatCurrency } from "@/lib/utils";
import { trapDialogFocus } from "@/lib/dialogFocus";

export default function PaymentDrawer({id, portal = false, onClose}: {id: string | null; portal?: boolean; onClose: () => void}) {
  const dialog = useRef<HTMLDialogElement>(null); const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!id) {dialog.current?.close(); return;}
    dialog.current?.showModal(); setPayment(null); setError("");
    const controller = new AbortController();
    apiClient<Payment>(`/payments/${id}`, {signal: controller.signal}).then(setPayment).catch(error => {if (!controller.signal.aborted) setError(errorMessage(error));});
    return () => controller.abort();
  }, [id, retry]);
  const base = portal ? "/portal" : "/app";
  return <dialog ref={dialog} tabIndex={-1} onKeyDown={event => trapDialogFocus(event, dialog.current)} aria-labelledby="payment-detail-title" onCancel={event => {event.preventDefault(); onClose();}}
    className="fixed left-auto right-0 top-0 m-0 h-[100dvh] max-h-none w-full max-w-xl overflow-y-auto border-l border-slate-200 p-0 backdrop:bg-slate-900/40">
    <div className="space-y-5 p-6"><div className="flex items-center justify-between gap-3"><h2 id="payment-detail-title" className="text-xl font-semibold">Payment details</h2><button type="button" className={secondaryStyle} onClick={onClose}>Close payment details</button></div>
      {error && <p role="alert" className="rounded bg-red-50 p-3 text-red-700">{error} <button type="button" className="underline" onClick={() => setRetry(retry + 1)}>Retry</button></p>}
      {!payment && !error && <p role="status">Loading payment…</p>}
      {payment && <><p className="break-all text-xs text-slate-500">{payment.id}</p><p className="text-3xl font-bold text-blue-800">{formatCurrency(payment.amount)}</p><dl className="space-y-3 text-sm"><div><dt className="text-slate-500">Invoice</dt><dd><Link className="break-all text-blue-700 underline" href={`${base}/invoices/${payment.invoice_id}`}>{payment.invoice_number}</Link></dd></div>{!portal && <div><dt className="text-slate-500">Customer</dt><dd>{payment.customer_name}</dd></div>}<div><dt className="text-slate-500">Payment date</dt><dd>{payment.payment_date}</dd></div><div><dt className="text-slate-500">Method</dt><dd>{payment.method.replaceAll("_", " ")}</dd></div><div><dt className="text-slate-500">Reference</dt><dd className="break-all">{payment.reference || "Not provided"}</dd></div><div><dt className="text-slate-500">Customer-visible note</dt><dd className="whitespace-pre-wrap break-words">{payment.note}</dd></div>{!portal && <div><dt className="text-slate-500">Recorded by / at</dt><dd>{payment.recorded_by} · {payment.recorded_at && new Date(payment.recorded_at).toLocaleString()}</dd></div>}</dl>
        <button type="button" disabled={busy} className={buttonStyle} onClick={async () => {setBusy(true); setError(""); try {await downloadFile(`/payments/${payment.id}/receipt`, `receipt-${payment.id}.pdf`);} catch (e) {setError(errorMessage(e));} finally {setBusy(false);}}}>Download receipt</button><p className="text-sm text-slate-500">Payments are permanent records. Contact the team with this payment ID for any queries.</p>
      </>}
    </div>
  </dialog>;
}
