import type { Payment } from "@/lib/payments";

export interface InvoiceSummary {
  id: string; number: string; subscription_id: string; customer_id: string; customer_name: string;
  state: string; period_start: string; period_end: string; invoice_date: string; due_date: string;
  currency: string; subtotal: string; discount_total: string; tax_total: string; total: string;
  paid: string; remaining: string; overdue: boolean; version: number;
}
export interface InvoiceDetail extends InvoiceSummary {
  payments: Payment[]; payment_count: number;
  issuer_name: string; issuer_tax_id: string | null; issuer_address: Record<string, string | null>;
  customer_email: string; customer_company: string | null; customer_address: Record<string, string | null>;
  issued_at: string | null; cancelled_at: string | null; full_period_end: string | null;
  service_days: number; full_period_days: number; cancel_reason?: string;
  lines: {id: string; ordinal: number; description: string; quantity: number; unit_price: string;
    subtotal: string; discount: string; tax: string; total: string;
    taxes: {name: string; rate: string; taxable_base: string; amount: string}[]}[];
  delivery_attempts?: {id: string; status: string; attempted_at: string; safe_error_code: string | null}[];
  history?: {id: string; action: string; timestamp: string; reason: string | null}[];
}
export interface BillingRun {
  id: string; as_of_date: string; trigger: string; state: string; started_at: string; finished_at: string | null;
  retry_of_id: string | null;
  summary: {created: number; existing: number; failed: number; subscriptions_scanned: number;
    has_more: boolean; continue_after_id: string | null; target_subscription_id?: string | null} | null;
}
export interface BillingRunDetail extends BillingRun {
  outcomes: {id: string; subscription_id: string; period_start: string; invoice_id: string | null;
    state: string; safe_error_code: string | null}[]; total: number; page: number; page_size: number;
}
