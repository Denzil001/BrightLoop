export interface Payment {
  id: string; invoice_id: string; invoice_number: string; customer_id: string; customer_name: string;
  amount: string; currency: string; method: string; payment_date: string; note: string;
  reference: string | null; recorded_by?: string; recorded_at?: string;
}
export const paymentMethods = ["CASH", "BANK_TRANSFER", "UPI", "CARD", "CHEQUE", "OTHER"];
export function businessDate(value = new Date()) {
  return new Intl.DateTimeFormat("en-CA", {timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit"}).format(value);
}
