"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { useCallback, useEffect, useState, useRef } from "react";
import Link from "next/link";
import CollectionSort from "@/components/CollectionSort";
import { useQueryState } from "@/lib/useUrlFilters";
import { apiClient } from "@/lib/api";
import type { BillingRun, BillingRunDetail } from "@/lib/invoices";
import { buttonStyle, errorMessage, inputStyle, secondaryStyle } from "@/lib/subscriptions";
import { useAuth } from "@/context/AuthContext";

export default function Page() {
  const requestSequence = useRef(0);
  const {user} = useAuth(); const [runs, setRuns] = useState<BillingRun[]>([]); const [total, setTotal] = useState(0);
  const [scheduler, setScheduler] = useState<{message: string; active: boolean; heartbeat_at?: string} | null>(null);
  const [page, setPage] = useQueryState("page", 1); const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const today = new Intl.DateTimeFormat("en-CA", {timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date());
  const [asOf, setAsOf] = useState(today); const [selected, setSelected] = useState<BillingRunDetail | null>(null);
  const [targetId, setTargetId] = useState<string | null>(null);
  useEffect(() => {setTargetId(new URLSearchParams(window.location.search).get("subscription_id"));}, []);
  const load = useCallback(async () => {const request = ++requestSequence.current; if (user?.role !== "ADMIN") return; setLoading(true); try {
    const result = await apiClient<{items: BillingRun[]; total: number; scheduler: {message: string; active: boolean; heartbeat_at?: string}}>(`/billing-runs?page=${page}`); if (request !== requestSequence.current) return; setRuns(result.items); setTotal(result.total); setScheduler(result.scheduler);
  } catch (e) {if (request !== requestSequence.current) return; setError(errorMessage(e));} finally {if (request === requestSequence.current) setLoading(false);}}, [page, user?.role]);
  useEffect(() => {load();}, [load]);
  const open = async (id: string, outcomePage = 1) => {setError(""); try {setSelected(await apiClient<BillingRunDetail>(`/billing-runs/${id}?page=${outcomePage}`));} catch (e) {setError(errorMessage(e));}};
  const run = async (date: string, cursor: string | null = null, scope: string | null = targetId, previous: string | null = null) => {
    if (!window.confirm(`Run billing through ${date}? Each request processes at most 100 periods. Existing periods will be preserved.`)) return;
    setBusy(true); setError(""); setNotice("");
    try {const result = await apiClient<BillingRun>("/billing-runs", {method: "POST", body: JSON.stringify({as_of_date: date, after_subscription_id: cursor, max_periods: 100, subscription_id: scope, retry_of_id: previous})});
      await load(); await open(result.id); setNotice(result.summary?.failed ? "Run finished with failed periods. Earlier successful periods were kept." : result.summary?.has_more ? "Batch finished. Continue remaining work below." : "Billing run finished.");
    } catch (e) {setError(errorMessage(e));} finally {setBusy(false);}
  };
  if (user?.role !== "ADMIN") return <section><h1 className="text-xl font-semibold">Access restricted</h1><p>Billing runs are available to administrators.</p></section>;
  return <section className="space-y-6">
      <div><h1 className="text-2xl font-bold">Billing runs & recovery</h1><p className="text-sm text-slate-500">Reconcile historical service periods. Each invoice commits independently.</p></div>
      <CollectionSort fields={[["started_at", "Started"], ["as_of_date", "Business date"], ["state", "State"]]} initial="started_at" descending={true} onChange={() => {if (page === 1) load(); else setPage(1);}} />
    {targetId && <p className="rounded bg-blue-50 p-4 text-sm text-blue-900">This run is limited to the <Link href={`/app/subscriptions/${targetId}`} className="underline">selected subscription</Link>. <button type="button" className="underline" onClick={() => setTargetId(null)}>Switch to all subscriptions</button></p>}
    <form className="flex flex-wrap items-end gap-4 rounded-lg border bg-white p-5" onSubmit={e => {e.preventDefault(); run(asOf);}}><label className="text-sm">As-of business date<input className={inputStyle} type="date" required max={today} value={asOf} onChange={e => setAsOf(e.target.value)} /></label><button type="submit" disabled={busy} className={buttonStyle}>{busy ? "Running…" : "Run billing now"}</button><p className="text-sm text-slate-500">{scheduler?.message || "Checking scheduler status…"}{scheduler?.heartbeat_at && <> Last heartbeat: {new Date(scheduler.heartbeat_at).toLocaleString()}.</>}</p></form>
    {error && <p role="alert" className="rounded bg-red-50 p-4 text-red-700">{error} <button type="button" className="underline" onClick={load}>Refresh</button></p>}{notice && <p role="status" className="rounded bg-blue-50 p-4 text-blue-900">{notice}</p>}
    {loading ? <p role="status">Loading billing runs…</p> : <ScrollableRegion className="overflow-x-auto rounded-lg border bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr>{["As of", "Trigger", "Started / finished", "Status", "Created", "Existing", "Failed", "Recovery"].map(h => <th key={h} className="p-3">{h}</th>)}</tr></thead><tbody>{runs.map(item => <tr className="border-t" key={item.id}><td className="p-3"><button type="button" className="text-blue-700 underline" onClick={() => open(item.id)}>{item.as_of_date}</button></td><td className="p-3">{item.trigger}</td><td className="p-3">{new Date(item.started_at).toLocaleString()}<br />{item.finished_at ? new Date(item.finished_at).toLocaleString() : "In progress"}</td><td className="p-3">{item.state}</td>{(["created", "existing", "failed"] as const).map(key => <td className="p-3" key={key}>{item.summary?.[key] ?? "—"}</td>)}<td className="p-3 space-y-2">{item.summary?.has_more && <button type="button" disabled={busy} className={secondaryStyle} onClick={() => run(item.as_of_date, item.summary?.continue_after_id || null, item.summary?.target_subscription_id || null, item.id)}>Continue remaining work</button>}{(!!item.summary?.failed || item.state === "INTERRUPTED") && <button type="button" disabled={busy} className={secondaryStyle} onClick={() => run(item.as_of_date, null, item.summary?.target_subscription_id || null, item.id)}>Retry from start</button>}</td></tr>)}</tbody></table>{!runs.length && <p className="p-8 text-center text-slate-500">No billing runs yet.</p>}</ScrollableRegion>}
    <div className="flex items-center justify-between text-sm"><span>{total} runs · Page {page}</span><div className="flex gap-2"><button type="button" disabled={page === 1 || loading} className={secondaryStyle} onClick={() => setPage(page - 1)}>Previous</button><button type="button" disabled={page * 20 >= total || loading} className={secondaryStyle} onClick={() => setPage(page + 1)}>Next</button></div></div>
    {selected && <section className="space-y-4 rounded-lg border bg-white p-5"><div className="flex justify-between gap-3"><h2 className="font-semibold">Run outcomes · {selected.as_of_date}</h2><button type="button" className={secondaryStyle} onClick={() => setSelected(null)}>Close outcomes</button></div><p className="break-all text-xs text-slate-500">{selected.id}</p>{selected.retry_of_id && <button type="button" className="text-sm text-blue-700 underline" onClick={() => {if (selected.retry_of_id) open(selected.retry_of_id);}}>View preceding run</button>}<ScrollableRegion className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{["Subscription", "Period start", "Outcome", "Invoice / error"].map(h => <th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{selected.outcomes.map(outcome => <tr className="border-t" key={outcome.id}><td className="p-2"><Link className="text-blue-700 underline" href={`/app/subscriptions/${outcome.subscription_id}`}>View subscription</Link></td><td className="p-2">{outcome.period_start}</td><td className="p-2">{outcome.state}</td><td className="p-2">{outcome.invoice_id ? <Link href={`/app/invoices/${outcome.invoice_id}`} className="text-blue-700 underline">View invoice</Link> : "Period could not be completed. Review the subscription and retry."}</td></tr>)}</tbody></table>{!selected.outcomes.length && <p className="py-4 text-sm text-slate-500">No eligible invoice periods in this batch.</p>}</ScrollableRegion><div className="flex gap-2"><button type="button" disabled={selected.page === 1} className={secondaryStyle} onClick={() => open(selected.id, selected.page - 1)}>Previous outcomes</button><button type="button" disabled={selected.page * selected.page_size >= selected.total} className={secondaryStyle} onClick={() => open(selected.id, selected.page + 1)}>Next outcomes</button></div></section>}
  </section>;
}
