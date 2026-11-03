import type { ReactNode } from "react";

/** A named table scroll area must be reachable before ArrowLeft/ArrowRight. */
export default function ScrollableRegion({ children, className }: {
  children: ReactNode; className?: string;
}) {
  return (
    // biome-ignore lint/a11y/noNoninteractiveTabindex: Keyboard users need to focus this overflow region to scroll its table; covered by desktop/mobile keyboard journeys.
    <section aria-label="Scrollable table" tabIndex={0} className={className}>
      {children}
    </section>
  );
}
