"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "./api";

interface Choice { id: string; name: string }

/** Bounded catalog lookup, independent of the form's saved values. */
export function useCatalogChoices<T extends Choice>(endpoint: string, selectedIds: string[] = [], enabled = true) {
  const [items, setItems] = useState<T[]>([]);
  const [selected, setSelected] = useState<T[]>([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const selectedKey = [...new Set(selectedIds.filter(Boolean))].sort().join(",");

  useEffect(() => {
    if (!enabled) {setLoading(false); return;}
    let alive = true;
    setLoading(true); setError("");
    const timer = setTimeout(() => {
      const params = new URLSearchParams({active: "true", page_size: "50", page: String(page), search, sort: "name", descending: "false"});
      apiClient<{items: T[]; total: number}>(`${endpoint}?${params}`).then(result => {
        if (!alive) return;
        setItems(previous => [...new Map((page === 1 ? result.items : [...previous, ...result.items]).map(item => [item.id, item])).values()]);
        setTotal(result.total);
      }).catch(reason => {if (alive) setError(reason instanceof ApiError ? reason.message : "Unable to load choices.");})
        .finally(() => {if (alive) setLoading(false);});
    }, 200);
    return () => {alive = false; clearTimeout(timer);};
  }, [endpoint, search, page, retry, enabled]);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const ids = selectedKey.split(",").filter(Boolean);
    if (!ids.length) {setSelected([]); return;}
    Promise.all(ids.map(id => apiClient<T>(`${endpoint}/${encodeURIComponent(id)}`)))
      .then(records => {if (alive) setSelected(records);})
      .catch(reason => {if (alive) setError(reason instanceof ApiError ? reason.message : "Unable to load selected choices.");});
    return () => {alive = false;};
  }, [endpoint, selectedKey, retry, enabled]);

  const ids = new Set(selectedKey.split(","));
  const choices = [...new Map([...items, ...selected.filter(item => ids.has(item.id))].map(item => [item.id, item])).values()];
  return {items: choices, search, loading, error, hasMore: page * 50 < total,
    setSearch: (value: string) => {setSearch(value); setPage(1); setItems([]); setTotal(0);},
    loadMore: () => setPage(value => value + 1), retry: () => setRetry(value => value + 1)};
}
