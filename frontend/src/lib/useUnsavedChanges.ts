"use client";
import { useEffect, useState } from "react";

/** Dialog values are initialized before opening; compare edits to that snapshot. */
export function useDialogChanges(open: boolean, values: unknown) {
  const snapshot = JSON.stringify(values);
  const [baseline, setBaseline] = useState<string | null>(null);
  useEffect(() => {
    if (!open) setBaseline(null);
    else if (baseline === null) setBaseline(snapshot);
  }, [open, snapshot, baseline]);
  return open && baseline !== null && snapshot !== baseline;
}

/** Cover in-app links/close controls as well as browser reload/closing the tab. */
const dirtyForms = new Set<symbol>();
export function confirmDiscard() {
  return !dirtyForms.size || window.confirm("You have unsaved changes. Leave without saving?");
}
const unload = (event: BeforeUnloadEvent) => {event.preventDefault(); event.returnValue = "";};
type TraverseEvent = Event & {navigationType: string; destination: {sameDocument: boolean}};
const navigation = () => (window as Window & {navigation?: EventTarget}).navigation;
const traverse = (event: Event) => {
  const intent = event as TraverseEvent;
  // Other documents use beforeunload. Only cancellable same-document history
  // traversals can be guarded through the browser Navigation API.
  if (intent.navigationType === "traverse" && intent.destination.sameDocument && intent.cancelable && !confirmDiscard()) intent.preventDefault();
};
const click = (event: MouseEvent) => {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const element = event.target instanceof Element ? event.target : null;
  const control = element?.closest("a[href], [data-discard-form], [data-leave-page]");
  if (!control) return;
  if (control instanceof HTMLAnchorElement) {
    if (control.target === "_blank" || control.hasAttribute("download")) return;
    const url = new URL(control.href, window.location.href);
    if (url.pathname === location.pathname && url.search === location.search && url.origin === location.origin) return;
  }
  if (!window.confirm("You have unsaved changes. Leave without saving?")) {
    event.preventDefault(); event.stopImmediatePropagation();
  }
};

export function useUnsavedChanges(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const identity = Symbol("dirty form");
    if (!dirtyForms.size) {
      window.addEventListener("beforeunload", unload);
      document.addEventListener("click", click, true);
      navigation()?.addEventListener("navigate", traverse);
    }
    dirtyForms.add(identity);
    return () => {
      dirtyForms.delete(identity);
      if (!dirtyForms.size) {window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true); navigation()?.removeEventListener("navigate", traverse);}
    };
  }, [dirty]);
}
