"use client";
import { type Dispatch, type SetStateAction, useCallback, useEffect, useRef, useState } from "react";

type Scalar = string | number | boolean | null;
type FilterValues<T> = {[K in keyof T]: T[K] extends boolean ? boolean : T[K] extends number ? number : T[K] extends string ? string : T[K]};
const changed = "brightloop:url-filters";

/** Keep table state in the current history entry, including after detail/back. */
export function useUrlFilters<T extends Record<string, Scalar>>(defaults: T): [FilterValues<T>, Dispatch<SetStateAction<FilterValues<T>>>] {
  const initial = useRef(defaults as FilterValues<T>);
  const [value, setValue] = useState(defaults as FilterValues<T>);
  const current = useRef(value);
  useEffect(() => {
    const read = () => {
      const params = new URLSearchParams(window.location.search);
      const next = {...initial.current};
      for (const key of Object.keys(initial.current)) {
        const fallback = initial.current[key]; const raw = params.get(key);
        let parsed: Scalar = raw === null ? fallback : raw;
        if (typeof fallback === "boolean") parsed = raw === null ? fallback : raw === "true";
        if (typeof fallback === "number") parsed = raw !== null && /^\d+$/.test(raw) && Number(raw) >= 1 ? Number(raw) : fallback;
        (next as Record<string, Scalar>)[key] = parsed;
      }
      if (Object.keys(next).some(key => next[key] !== current.current[key])) {
        current.current = next; setValue(next);
      }
    };
    read(); window.addEventListener("popstate", read); window.addEventListener(changed, read);
    return () => {window.removeEventListener("popstate", read); window.removeEventListener(changed, read);};
  }, []);
  const update = useCallback<Dispatch<SetStateAction<FilterValues<T>>>>(action => {
    const next = typeof action === "function" ? action(current.current) : action;
    current.current = next; setValue(next);
    const url = new URL(window.location.href);
    for (const key of Object.keys(initial.current)) {
      const item = next[key];
      if (item === null || item === "" || item === initial.current[key]) url.searchParams.delete(key);
      else url.searchParams.set(key, String(item));
    }
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
    window.dispatchEvent(new Event(changed));
  }, []);
  return [value, update];
}

export function useQueryState<T>(key: string, initial: T): [T, Dispatch<SetStateAction<T>>] {
  const [values, setValues] = useUrlFilters({[key]: initial as Scalar});
  const update = useCallback<Dispatch<SetStateAction<T>>>(action => setValues(previous => ({...previous,
    [key]: (typeof action === "function" ? (action as (value: T) => T)(previous[key] as T) : action) as Scalar})), [key, setValues]);
  return [values[key] as T, update];
}
