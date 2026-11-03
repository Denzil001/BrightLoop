"use client";

import type React from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Layers, User } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function CustomerPortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading, logout, authError } = useAuth();
  const pathname = usePathname();
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => setNavOpen(false), [pathname]);
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push(`/login?returnUrl=${encodeURIComponent(pathname)}`);
    } else if (!loading && user && user.role !== "CUSTOMER") {
      router.push("/app");
    }
  }, [user, loading, router, pathname]);

  if (loading || !user || user.role !== "CUSTOMER") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <p className="text-sm text-slate-500">Loading portal session...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Customer Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 min-h-16 flex flex-wrap items-center justify-between gap-3 py-3">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
            <Link prefetch={false}
              href="/portal"
              className="flex items-center gap-2 text-blue-600 font-bold text-xl tracking-tight"
            >
              <Layers className="w-6 h-6" />
              <span>Customer Portal</span>
            </Link>
            <button type="button" className="rounded border px-3 py-2 text-sm sm:hidden" aria-expanded={navOpen} aria-controls="workspace-navigation" onClick={() => setNavOpen(!navOpen)}>Menu</button>
            <nav id="workspace-navigation" aria-label="Workspace navigation" className={`${navOpen ? "flex" : "hidden"} sm:flex max-w-full flex-wrap items-center gap-1 text-sm font-medium text-slate-700`}>
              <Link prefetch={false} href="/portal" className="px-3 py-2 rounded-md hover:bg-slate-100">Overview</Link>
              <Link prefetch={false} href="/portal/subscriptions" className="px-3 py-2 rounded-md hover:bg-slate-100">My subscriptions</Link>
              <Link prefetch={false} href="/portal/invoices" className="px-3 py-2 rounded-md hover:bg-slate-100">My invoices</Link>
              <Link prefetch={false} href="/portal/payments" className="px-3 py-2 rounded-md hover:bg-slate-100">My payments</Link>
              <Link prefetch={false}
                href="/portal/profile"
                className={`px-3 py-2 rounded-md flex items-center gap-1.5 transition ${
                  pathname.startsWith("/portal/profile")
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "hover:bg-slate-100 text-slate-700"
                }`}
              >
                <User className="w-4 h-4" />
                <span>My Profile</span>
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-4 text-sm">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-slate-900 leading-tight">
                {user.name}
              </p>
              <span className="inline-block text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                Customer
              </span>
            </div>
            <button type="button"
              data-leave-page onClick={() => logout()}
              className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:text-slate-900 border border-slate-300 hover:bg-slate-100 rounded-md transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {authError && <p role="alert" className="mb-4 rounded bg-red-50 p-3 text-red-700">{authError}</p>}{children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-500">
        Secure Customer Self-Service &bull; Brightloop
      </footer>
    </div>
  );
}
