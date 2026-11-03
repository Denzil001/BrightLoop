"use client";
import { useParams } from "next/navigation";
import InvoiceDetail from "@/components/invoices/InvoiceDetail";
export default function Page() {const params = useParams<{invoiceId: string}>(); return <InvoiceDetail id={params.invoiceId} />;}
