import { ApiError } from "@/lib/api";

export interface SubscriptionSummary {
  id: string; number: string; customer_id: string; customer_name: string;
  plan_id: string; plan_name: string; state: string; seat_quantity: number;
  version: number; next_billing_date: string | null;
  recurring_amount?: string; expiry_date?: string; request_count?: number; ended?: boolean;
}
export interface AgreementLine {
  id: string; ordinal: number; kind: string; name: string; variant_name: string | null;
  product_id: string | null; variant_id: string | null; quantity: number;
  unit_price: string; subtotal: string; override_reason?: string | null;
  discount_amount?: string | null; tax_amount?: string | null; total?: string | null;
  taxes: {name: string; rate: string}[];
}
export interface Agreement {
  id: string; sequence: number; state: string; quote_number: string | null;
  issued_date: string | null; valid_until: string | null; start_date: string; expiry_date: string;
  interval: string; payment_term_days: number; seat_quantity: number; currency: string;
  effective_from: string | null;
  pending_change: boolean;
  policies: Record<string, boolean>; lines: AgreementLine[]; discount_revision_ids: string[]; discount_rule_ids: string[];
  pricing_estimate: {subtotal?: string; total_discount?: string; total_tax?: string; total?: string};
}
export interface SubscriptionDetail extends SubscriptionSummary {
  agreements: Agreement[];
  invoices: {id: string; number: string; state: string; period_start: string; total: string}[];
  terms: {id: string; sequence: number; start_date: string; expiry_date: string; interval: string; policies: Record<string, boolean>}[];
  events: {id: string; action: string; effective_date: string; applied_at: string | null}[];
  requests: {id: string; action: string; effective_date: string; status: string;
      note: string; review_reason: string | null; reviewed_at: string | null; reviewer_name: string | null;
    proposal: unknown; price_summary: unknown}[];
}
export interface DraftLine {
  product_id: string; variant_id: string | null; quantity: number;
  line_kind: string; agreed_unit_price?: string; override_reason?: string;
}
export interface DraftPayload {
  customer_id: string; plan_id: string; template_id: string | null; seat_quantity: number;
  start_date: string; expiry_date: string; payment_term_days: number; validity_days: number;
  lines: DraftLine[]; discount_id: string | null; discount_ids: string[];
}
export const inputStyle = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";
export const buttonStyle = "rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50";
export const secondaryStyle = "rounded-md border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50";
export function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.fields?.length) return error.fields.map(field => `${field.path.replace(/^body\./, "").replaceAll("_", " ")}: ${field.message}`).join(" ");
  return error instanceof Error ? error.message : "Something went wrong. Please retry.";
}
