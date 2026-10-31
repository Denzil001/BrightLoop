import Link from "next/link";
import { Layers, CheckCircle2, ArrowRight, LogIn, UserPlus, Users, UserCheck } from "lucide-react";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
      <div className="max-w-3xl w-full bg-white rounded-2xl shadow-sm border border-slate-200 p-8 md:p-12">
        <div className="flex items-center gap-3 text-blue-600 mb-6">
          <Layers className="w-10 h-10" />
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">
              Brightloop
            </h1>
            <span className="text-xs font-semibold uppercase tracking-wider text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
              Subscription Management System &bull; Phase 2 Delivered
            </span>
          </div>
        </div>

        <p className="text-lg text-slate-600 mb-8 leading-relaxed">
          Enterprise subscription management powered by native PostgreSQL 18 relational persistence, FastAPI backend, and Next.js App Router.
        </p>

        {/* Phase 2 Access Portals */}
        <div className="mb-8">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
            Authentication &amp; User Access
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Link
              href="/login"
              className="p-5 rounded-xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-sm transition-all group flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
                  <LogIn className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 text-sm">Sign In</h3>
                  <p className="text-xs text-slate-500">Access operations or customer portal</p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link
              href="/register"
              className="p-5 rounded-xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-sm transition-all group flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-600">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 text-sm">Customer Registration</h3>
                  <p className="text-xs text-slate-500">Create new account or link records</p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Phase 2 Delivered Operational Modules */}
        <div className="mb-8">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
            Delivered Operational Workspaces
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Link
              href="/app/customers"
              className="p-4 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 transition group flex items-center gap-3"
            >
              <Users className="w-5 h-5 text-blue-600" />
              <div>
                <h4 className="text-sm font-semibold text-slate-800">Customers Directory</h4>
                <p className="text-xs text-slate-500">Search, filter, paginate, and create operational customer records</p>
              </div>
            </Link>

            <Link
              href="/app/staff"
              className="p-4 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 transition group flex items-center gap-3"
            >
              <UserCheck className="w-5 h-5 text-blue-600" />
              <div>
                <h4 className="text-sm font-semibold text-slate-800">Staff Management</h4>
                <p className="text-xs text-slate-500">Admin-only staff provisioning, active status, and session deactivation</p>
              </div>
            </Link>
          </div>
        </div>

        {/* Diagnostics Link */}
        <div className="pt-6 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-1.5 text-emerald-700">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>PostgreSQL 18 persistence active &bull; Mailpit loopback verified</span>
          </div>
          <Link
            href="/health-check"
            className="text-blue-600 hover:text-blue-800 font-medium inline-flex items-center gap-1"
          >
            <span>Readiness Diagnostic Check</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </main>
  );
}
