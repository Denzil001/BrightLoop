"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { Plus, Search, Filter, RefreshCw, ChevronLeft, ChevronRight, CheckCircle2, Clock } from "lucide-react";
import CollectionSort from "@/components/CollectionSort";
import { useQueryState } from "@/lib/useUrlFilters";
import { useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient, ApiError } from "@/lib/api";

interface CustomerItem {
  id: string;
  name: string;
  email: string;
  company: string | null;
  phone: string | null;
  billing_city: string | null;
  billing_country: string | null;
  has_portal_login: boolean;
  version: number;
  created_at: string;
}

interface CustomerListResponse {
  items: CustomerItem[];
  page: number;
  page_size: number;
  total: number;
}

export default function CustomersPage() {
  const requestSequence = useRef(0);
  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useQueryState("page", 1);
  const [pageSize] = useState(15);
  const [search, setSearch] = useQueryState("search", "");
  const [portalFilter, setPortalFilter] = useQueryState<string>("portal_status", "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formEmail, setFormEmail] = useState("");
  const [formCompany, setFormCompany] = useState("");
  const [formPhone, setFormPhone] = useState("");
  const [formAddress1, setFormAddress1] = useState("");
  const [formCity, setFormCity] = useState("");
  const [formState, setFormState] = useState("");
  const [formPostal, setFormPostal] = useState("");
  const [formCountry, setFormCountry] = useState("India");
  useUnsavedChanges(drawerOpen && Boolean(formName || formEmail || formCompany || formPhone || formAddress1 || formCity || formState || formPostal || formCountry !== "India"));

  const fetchCustomers = useCallback(async () => {const request = ++requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", page.toString());
      params.set("page_size", pageSize.toString());
      if (search.trim()) params.set("search", search.trim());
      if (portalFilter) params.set("portal_status", portalFilter);

      const res = await apiClient<CustomerListResponse>(`/customers?${params.toString()}`); if (request !== requestSequence.current) return;
      setCustomers(res.items);
      setTotal(res.total);
    } catch (err) {if (request !== requestSequence.current) return;
      setError(err instanceof ApiError ? err.message : "Failed to load customers.");
    } finally {
      if (request === requestSequence.current) setLoading(false);
    }
  }, [page, pageSize, search, portalFilter]);

  useEffect(() => {
    fetchCustomers();
  }, [fetchCustomers]);

  const handleCreateCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    setCreateLoading(true);

    try {
      await apiClient("/customers", {
        method: "POST",
        body: JSON.stringify({
          name: formName,
          email: formEmail,
          company: formCompany.trim() || undefined,
          phone: formPhone.trim() || undefined,
          billing_address_line1: formAddress1.trim() || undefined,
          billing_city: formCity.trim() || undefined,
          billing_state: formState.trim() || undefined,
          billing_postal_code: formPostal.trim() || undefined,
          billing_country: formCountry.trim() || undefined,
        }),
      });

      setDrawerOpen(false);
      // Reset form
      setFormName("");
      setFormEmail("");
      setFormCompany("");
      setFormPhone("");
      setFormAddress1("");
      setFormCity("");
      setFormState("");
      setFormPostal("");
      fetchCustomers();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to create customer.");
    } finally {
      setCreateLoading(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6">

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Customers
          </h1>
          <p className="text-sm text-slate-600">
            Operational customer directory and portal linking status
          </p>
        </div>
        <button type="button"
          onClick={() => setDrawerOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          <span>New Customer</span>
        </button>
      </div>
      <CollectionSort fields={[["created_at", "Created"], ["name", "Name"], ["email", "Email"]]} initial="created_at" descending={true} onChange={() => {if (page === 1) fetchCustomers(); else setPage(1);}} />

      {/* Filters & Search */}
      <div className="bg-white p-4 border border-slate-200 rounded-lg shadow-sm flex flex-col md:flex-row gap-4 justify-between items-center">
        <div className="relative w-full md:w-96">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search by name, company, or email..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-1.5 text-sm text-slate-600">
            <Filter className="w-4 h-4" />
            <span>Portal:</span>
          </div>
          <select aria-label="Portal login filter"
            value={portalFilter}
            onChange={(e) => {
              setPortalFilter(e.target.value);
              setPage(1);
            }}
            className="py-1.5 px-3 border border-slate-300 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
          >
            <option value="">All statuses</option>
            <option value="linked">Portal Linked</option>
            <option value="unlinked">Unlinked</option>
          </select>

          <button type="button"
            onClick={() => fetchCustomers()}
            title="Refresh"
            className="p-2 border border-slate-300 rounded-md hover:bg-slate-50 text-slate-600 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Customers Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <ScrollableRegion className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <th className="px-6 py-3">Customer / Company</th>
                <th className="px-6 py-3">Contact</th>
                <th className="px-6 py-3">Location</th>
                <th className="px-6 py-3">Portal Login</th>
                <th className="px-6 py-3">Created</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                    Loading customer records...
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center">
                    <p className="text-slate-600 font-medium mb-1">No customers found</p>
                    <p className="text-xs text-slate-500 mb-4">
                      {search || portalFilter
                        ? "Try adjusting your search filters."
                        : "Get started by creating your first operational customer profile."}
                    </p>
                    {!search && !portalFilter && (
                      <button type="button"
                        onClick={() => setDrawerOpen(true)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded text-xs font-medium hover:bg-blue-700"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>Create Customer</span>
                      </button>
                    )}
                  </td>
                </tr>
              ) : (
                customers.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50 transition">
                    <td className="px-6 py-4">
                      <Link
                        href={`/app/customers/${c.id}`}
                        className="font-medium text-blue-600 hover:text-blue-800"
                      >
                        {c.name}
                      </Link>
                      {c.company && (
                        <p className="text-xs text-slate-500">{c.company}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      <div>{c.email}</div>
                      {c.phone && <div className="text-xs text-slate-500">{c.phone}</div>}
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      {c.billing_city ? `${c.billing_city}, ${c.billing_country || ""}` : "—"}
                    </td>
                    <td className="px-6 py-4">
                      {c.has_portal_login ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Linked</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                          <Clock className="w-3 h-3" />
                          <span>Unlinked</span>
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-500 text-xs">
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link
                        href={`/app/customers/${c.id}`}
                        className="text-xs font-medium text-slate-600 hover:text-blue-600"
                      >
                        View details →
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </ScrollableRegion>

        {/* Pagination Bar */}
        <div className="bg-slate-50 px-6 py-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
          <div>
            Showing {customers.length > 0 ? (page - 1) * pageSize + 1 : 0} to{" "}
            {Math.min(page * pageSize, total)} of {total} customer{total !== 1 ? "s" : ""}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" aria-label="Previous page"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1 border border-slate-300 rounded hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="font-medium">
              Page {page} of {totalPages}
            </span>
            <button type="button" aria-label="Next page"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1 border border-slate-300 rounded hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Create Customer Drawer / Modal */}
      {drawerOpen && (
        <Modal className="fixed inset-0 z-50 overflow-y-auto flex justify-end" onDismiss={() => setDrawerOpen(false)} busy={createLoading}>
          <div className="w-full max-w-md bg-white h-full shadow-2xl flex flex-col">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                Create Operational Customer
              </h2>
              <button type="button"
                data-discard-form
                aria-label="Close customer form"
                onClick={() => setDrawerOpen(false)}
                className="text-slate-500 hover:text-slate-600 text-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCustomer} className="flex-1 overflow-y-auto p-6 space-y-4">
              {createError && (
                <div id="customer-create-error" role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
                  {createError}
                </div>
              )}

              <div>
                <label htmlFor="customer-name" className="block text-xs font-semibold text-slate-700 mb-1">
                  Customer / Primary Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  id="customer-name"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Acme Corporation or John Smith"
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="customer-email" className="block text-xs font-semibold text-slate-700 mb-1">
                  Email Address <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  required
                  id="customer-email"
                  aria-describedby={createError ? "customer-create-error" : undefined}
                  value={formEmail}
                  onChange={(e) => setFormEmail(e.target.value)}
                  placeholder="billing@company.com"
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Used for verified portal linking and future invoice delivery.
                </p>
              </div>

              <div>
                <label htmlFor="field-app-customers-page-tsx-1" className="block text-xs font-semibold text-slate-700 mb-1">
                  Company Name (optional)
                </label>
                <input id="field-app-customers-page-tsx-1"
                  type="text"
                  value={formCompany}
                  onChange={(e) => setFormCompany(e.target.value)}
                  placeholder="Acme Global Ltd"
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="field-app-customers-page-tsx-2" className="block text-xs font-semibold text-slate-700 mb-1">
                  Phone Number (optional)
                </label>
                <input id="field-app-customers-page-tsx-2"
                  type="text"
                  value={formPhone}
                  onChange={(e) => setFormPhone(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div className="pt-2 border-t border-slate-100">
                <p className="text-xs font-bold text-slate-800 mb-2">Billing Address</p>
                <div className="space-y-3">
                  <input
                    type="text"
                    value={formAddress1}
                    onChange={(e) => setFormAddress1(e.target.value)}
                    placeholder="Address Line 1"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={formCity}
                      onChange={(e) => setFormCity(e.target.value)}
                      placeholder="City"
                      className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                    />
                    <input
                      type="text"
                      value={formState}
                      onChange={(e) => setFormState(e.target.value)}
                      placeholder="State"
                      className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={formPostal}
                      onChange={(e) => setFormPostal(e.target.value)}
                      placeholder="Postal Code"
                      className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                    />
                    <input
                      type="text"
                      value={formCountry}
                      onChange={(e) => setFormCountry(e.target.value)}
                      placeholder="Country"
                      className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-200 flex justify-end gap-3">
                <button
                  type="button"
                  data-discard-form
                  onClick={() => setDrawerOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium disabled:opacity-50"
                >
                  {createLoading ? "Creating..." : "Save Customer"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}
    </div>
  );
}
