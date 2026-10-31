"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Layers, User } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function CustomerPortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push(`/login?returnUrl=${encodeURIComponent(pathname)}`);
    } else if (!loading && user && user.role !== "CUSTOMER") {
      router.push("/app/customers");
    }
  }, [user, loading, router, pathname]);

  if (loading || !user) {
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
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link
              href="/portal/profile"
              className="flex items-center gap-2 text-blue-600 font-bold text-xl tracking-tight"
            >
              <Layers className="w-6 h-6" />
              <span>Customer Portal</span>
            </Link>
            <nav className="flex items-center gap-1 text-sm font-medium text-slate-700">
              <Link
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
            <button
              onClick={() => logout()}
              className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:text-slate-900 border border-slate-300 hover:bg-slate-100 rounded-md transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-500">
        Secure Customer Self-Service &bull; Brightloop
      </footer>
    </div>
  );
}
