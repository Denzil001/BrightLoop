"use client";
import { useParams } from "next/navigation";
import SubscriptionDetail from "@/components/subscriptions/SubscriptionDetail";
export default function Page() {const params = useParams<{subscriptionId: string}>(); return <SubscriptionDetail id={params.subscriptionId} portal />;}
