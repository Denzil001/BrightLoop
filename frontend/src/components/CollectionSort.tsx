"use client";
import { useQueryState } from "@/lib/useUrlFilters";
import { inputStyle } from "@/lib/subscriptions";
import type { ReactNode } from "react";

export default function CollectionSort({fields, initial, descending = false, onChange, children}: {
  fields: [string, string][]; initial: string; descending?: boolean; onChange: () => void; children?: ReactNode;
}) {
  const [sort, setSort] = useQueryState("sort", initial);
  const [reverse, setReverse] = useQueryState("descending", descending);
  return <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-white p-3">
    <label className="text-sm">Sort by<select aria-label="Sort by" className={inputStyle} value={sort}
      onChange={event => {setSort(event.target.value); onChange();}}>{fields.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <label className="py-2 text-sm"><input type="checkbox" checked={reverse} onChange={event => {setReverse(event.target.checked); onChange();}} /> Descending</label>
    {children}
  </div>;
}
