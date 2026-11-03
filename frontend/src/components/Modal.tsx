"use client";

import { type ReactNode, useId, useLayoutEffect, useRef } from "react";
import { confirmDiscard } from "@/lib/useUnsavedChanges";
import { trapDialogFocus } from "@/lib/dialogFocus";

/** Native modal semantics contain keyboard focus and make the workspace inert. */
export default function Modal({children, className, onDismiss, busy = false}: {
  children: ReactNode; className?: string; onDismiss: () => void; busy?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useLayoutEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const previous = document.activeElement;
    const title = element.querySelector("h2,h3");
    if (title) {title.id ||= titleId; element.setAttribute("aria-labelledby", title.id);}
    else element.setAttribute("aria-label", "Form dialog");
    element.showModal();
    return () => {
      element.close();
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, [titleId]);
  return <dialog ref={dialog} tabIndex={-1} aria-busy={busy} onKeyDown={event => trapDialogFocus(event, dialog.current)} onCancel={event => {
    event.preventDefault();
    if (!busy && confirmDiscard()) onDismiss();
  }} className="m-0 h-dvh max-h-none w-screen max-w-none border-0 bg-transparent p-0 backdrop:bg-slate-900/40">
    <div className={className} inert={busy}>{children}</div>
  </dialog>;
}
