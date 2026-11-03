"use client";
import { useRouter } from "next/navigation";
import { useRef } from "react";
import SubscriptionEditor from "@/components/subscriptions/SubscriptionEditor";
import { apiClient } from "@/lib/api";
import type { SubscriptionDetail } from "@/lib/subscriptions";

export default function Page() {
  const router = useRouter();
  const creationKey = useRef("");
  return <section className="space-y-6"><div><h1 className="text-2xl font-bold">New subscription</h1><p className="text-sm text-slate-500">Prepare the service dates and commercial terms before issuing an offer.</p></div>
    <SubscriptionEditor onSave={async (payload, issue) => {
      if (!creationKey.current) creationKey.current = crypto.randomUUID();
      const sub = await apiClient<SubscriptionDetail>(`/subscriptions?issue=${issue}`, {method: "POST",
        headers: {"Idempotency-Key": creationKey.current}, body: JSON.stringify(payload)});
      router.push(`/app/subscriptions/${sub.id}`);
    }} />
  </section>;
}
