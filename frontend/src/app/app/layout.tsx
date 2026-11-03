"use client";

import type React from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Layers,
  Users,
  UserCog,
  User,
  Package,
  Receipt,
  Percent,
  FileText,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function OperationalAppLayout({
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
    } else if (!loading && user && user.role === "CUSTOMER") {
      router.push("/portal");
    }
  }, [user, loading, router, pathname]);

  if (loading || !user || user.role === "CUSTOMER") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <p className="text-sm text-slate-500">Authenticating session...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 min-h-16 flex flex-wrap items-center justify-between gap-3 py-3">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
            <Link prefetch={false}
              href="/app"
              className="flex items-center gap-2 text-blue-600 font-bold text-xl tracking-tight"
            >
              <Layers className="w-6 h-6" />
              <span>Brightloop</span>
            </Link>
            <button type="button" className="rounded border px-3 py-2 text-sm sm:hidden" aria-expanded={navOpen} aria-controls="workspace-navigation" onClick={() => setNavOpen(!navOpen)}>Menu</button>
            <nav id="workspace-navigation" aria-label="Workspace navigation" className={`${navOpen ? "flex" : "hidden"} sm:flex max-w-full flex-wrap items-center gap-1 text-sm font-medium text-slate-700 overflow-x-auto`}>
              <Link prefetch={false} href="/app" className="px-3 py-2 rounded-md hover:bg-slate-100">Overview</Link>
              {user.role === "ADMIN" && <Link prefetch={false} href="/app/reports" className="px-3 py-2 rounded-md hover:bg-slate-100">Reports</Link>}
              <Link prefetch={false}
                href="/app/customers"
                className={`px-3 py-2 rounded-md flex items-center gap-1.5 transition whitespace-nowrap ${
                  pathname.startsWith("/app/customers")
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "hover:bg-slate-100 text-slate-700"
                }`}
              >
                <Users className="w-4 h-4" />
                <span>Customers</span>
              </Link>

              <Link prefetch={false} href="/app/subscriptions" className="px-3 py-2 rounded-md hover:bg-slate-100 whitespace-nowrap">Subscriptions</Link>
              <Link prefetch={false} href="/app/invoices" className="px-3 py-2 rounded-md hover:bg-slate-100 whitespace-nowrap">Invoices</Link>
              <Link prefetch={false} href="/app/payments" className="px-3 py-2 rounded-md hover:bg-slate-100 whitespace-nowrap">Payments</Link>
              {user.role === "ADMIN" && <Link prefetch={false} href="/app/billing-runs" className="px-3 py-2 rounded-md hover:bg-slate-100 whitespace-nowrap">Billing runs</Link>}
              {user.role === "ADMIN" && (
                <>
                  <Link prefetch={false}
                    href="/app/products"
                    className={`px-3 py-2 rounded-md flex items-center gap-1.5 transition whitespace-nowrap ${
                      pathname.startsWith("/app/products")
                        ? "bg-blue-50 text-blue-700 font-semibold"
                        : "hover:bg-slate-100 text-slate-700"
                    }`}
                  >
                    <Package className="w-4 h-4" />
                    <span>Products</span>
                  </Link>

                  <Link prefetch={false}
                    href="/app/plans"
                    className={`px-3 py-2 rounded-md flex items-center gap-1.5 transition whitespace-nowrap ${
                      pathname.startsWith("/app/plans")
                        ? "bg-blue-50 text-blue-700 font-semibold"
                        : "hover:bg-slate-100 text-slate-700"
                    }`}
                  >
                    <Layers className="w-4 h-4" />
                    <span>Plans</span>
                  </Link>

                  <Link prefetch={false}
                    href="/app/taxes"
                    className={`px-3 py-2 rounded-md flex items-center gap-1.5 transition whitespace-nowrap ${
                      pathname.startsWith("/app/taxes")
                        ? "bg-blue-50 text-blue-700 font-semibold"
                        : "hover:bg-slate-100 text-slate-700"
                    }`}
                  >
                    <Receipt className="w-4 h-4" />
                    <span>Taxes</span>
                  </Link>

                  <Link prefetch={false}
                    href="/app/discounts"
                    className={`px-3 py-2 rounded-md flex items-center gap-1.5 transition whitespace-nowrap ${
                      pathname.startsWith("/app/discounts")
                        ? "bg-blue-50 text-blue-700 font-semibold"
                        : "hover:bg-slate-100 text-slate-700"
                    }`}
                  >
                    <Percent className="w-4 h-4" />
                    <span>Discounts</span>
                  </Link>

                  <Link prefetch={false}
                    href="/app/quotation-templates"
                    className={`px-3 py-2 rounded-md flex items-center gap-1.5 transition whitespace-nowrap ${
                      pathname.startsWith("/app/quotation-templates")
                        ? "bg-blue-50 text-blue-700 font-semibold"
                        : "hover:bg-slate-100 text-slate-700"
                    }`}
                  >
                    <FileText className="w-4 h-4" />
                    <span>Templates</span>
                  </Link>

                  <Link prefetch={false}
                    href="/app/staff"
                    className={`px-3 py-2 rounded-md flex items-center gap-1.5 transition whitespace-nowrap ${
                      pathname.startsWith("/app/staff")
                        ? "bg-blue-50 text-blue-700 font-semibold"
                        : "hover:bg-slate-100 text-slate-700"
                    }`}
                  >
                    <UserCog className="w-4 h-4" />
                    <span>Staff</span>
                  </Link>
                </>
              )}

              <Link prefetch={false}
                href="/app/profile"
                className={`px-3 py-2 rounded-md flex items-center gap-1.5 transition whitespace-nowrap ${
                  pathname.startsWith("/app/profile")
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "hover:bg-slate-100 text-slate-700"
                }`}
              >
                <User className="w-4 h-4" />
                <span>Profile</span>
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-4 text-sm shrink-0">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-slate-900 leading-tight">
                {user.name}
              </p>
              <span className="inline-block text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                {user.role}
              </span>
            </div>
            <button type="button"
              data-leave-page onClick={() => logout()}
              className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:text-slate-900 border border-slate-300 hover:bg-slate-100 rounded-md transition"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {authError && <p role="alert" className="mb-4 rounded bg-red-50 p-3 text-red-700">{authError}</p>}{children}
      </main>
    </div>
  );
}
