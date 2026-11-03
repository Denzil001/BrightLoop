import type { KeyboardEvent } from "react";

export function trapDialogFocus(event: KeyboardEvent<HTMLElement>, element: HTMLDialogElement | null) {
  if (event.key !== "Tab" || !element) return;
  const controls = Array.from(element.querySelectorAll<HTMLElement>("a[href],button,input,select,textarea,[tabindex]"))
    .filter(control => control.tabIndex >= 0 && !control.matches(":disabled") && !control.closest("[inert]") && control.getClientRects().length > 0);
  const first = controls[0], last = controls[controls.length - 1];
  if (!first) {event.preventDefault(); element.focus(); return;}
  if (event.shiftKey && (document.activeElement === first || !element.contains(document.activeElement))) {
    event.preventDefault(); last.focus();
  } else if (!event.shiftKey && (document.activeElement === last || !element.contains(document.activeElement))) {
    event.preventDefault(); first.focus();
  }
}
