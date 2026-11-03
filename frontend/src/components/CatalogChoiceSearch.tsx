"use client";

interface Props {
  label: string;
  source: {search: string; setSearch: (value: string) => void; loading: boolean; error: string;
    hasMore: boolean; loadMore: () => void; retry: () => void};
}

export default function CatalogChoiceSearch({label, source}: Props) {
  return <div className="my-2 space-y-2 text-sm">
    <label className="block">{label}<input type="search" className="mt-1 w-full rounded border border-slate-300 px-3 py-2" value={source.search} onChange={event => source.setSearch(event.target.value)} /></label>
    {source.loading && <p role="status" className="text-xs text-slate-500">Loading choices…</p>}
    {source.error && <p role="alert" className="text-red-700">{source.error} <button type="button" className="underline" onClick={source.retry}>Retry choices</button></p>}
    {source.hasMore && <button type="button" disabled={source.loading} className="rounded border px-3 py-1 disabled:opacity-50" onClick={source.loadMore}>Load more choices</button>}
    <p className="text-xs text-slate-500">Search to find other records. Selected records stay available.</p>
  </div>;
}
