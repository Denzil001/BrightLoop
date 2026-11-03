export interface FinanceSummary {
  active_subscriptions: number; received: string; receipt_count: number;
  outstanding: string; outstanding_count: number; overdue: string; overdue_count: number;
  date_from: string; date_to: string; as_of_date: string; query_time_ms: number;
}
export interface ReportRow {
  id: string; number?: string; invoice_id?: string; invoice_number?: string; subscription_id?: string;
  customer_name: string; plan_name?: string; amount?: string; method?: string; payment_date?: string;
  reference?: string; state?: string; total?: string; paid?: string; remaining?: string; due_date?: string; next_billing_date?: string;
}
export interface Dashboard {
  role: string; as_of_date: string; date_from: string; date_to: string; next_billing_date: string | null;
  pending_request_count: number; quote_count?: number; due_subscription_count?: number;
  invoice_action_count?: number; overdue_count?: number; metrics?: FinanceSummary;
  pending_requests: {id: string; subscription_id: string; type: string; requested_date: string; number: string}[];
  ending_subscriptions: {id: string; number: string; plan_name: string; expiry_date: string}[];
  recent_invoices: ReportRow[]; recent_payments: ReportRow[]; quotes?: ReportRow[]; due_subscriptions?: ReportRow[];
  query_time_ms: number;
}
