"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { formatCurrency } from "@/lib/utils";
import { decimalInput, DecimalInputError } from "@/lib/decimal";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import {
  Plus,
  Search,
  RefreshCw,
  Layers,
  Archive,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import CollectionSort from "@/components/CollectionSort";
import { useQueryState } from "@/lib/useUrlFilters";
import CatalogChoiceSearch from "@/components/CatalogChoiceSearch";
import { useCatalogChoices } from "@/lib/useCatalogChoices";
import { useDialogChanges, useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient, ApiError } from "@/lib/api";

interface PlanItem {
  id: string;
  name: string;
  description?: string;
  base_fee: string;
  minimum_seats: number;
  extra_seat_unit_price: string;
  interval: string;
  available_from?: string;
  available_to?: string;
  payment_term_days: number;
  allow_pause: boolean;
  allow_resume: boolean;
  allow_renewal: boolean;
  allow_early_closure: boolean;
  auto_close_on_expiry: boolean;
  active: boolean;
  version: number;
  items: Array<{ id: string; ordinal: number; included_quantity: number }>;
  tax_rule_ids: string[];
}

interface TaxRuleItem {
  id: string;
  name: string;
  rate: string;
}

interface PaginatedPlans {
  items: PlanItem[];
  page: number;
  page_size: number;
  total: number;
}

export default function PlansListPage() {
  const requestSequence = useRef(0);
  const { user } = useAuth();

  const [plans, setPlans] = useState<PlanItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useQueryState("page", 1);
  const [pageSize] = useState(15);
  const [search, setSearch] = useQueryState("search", "");
  const [intervalFilter, setIntervalFilter] = useQueryState<string>("interval", "");
  const [activeFilter, setActiveFilter] = useQueryState<string>("active", "");
  const [availability, setAvailability] = useQueryState("availability", "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseFee, setBaseFee] = useState("1000.00");
  const [minSeats, setMinSeats] = useState("5");
  const [extraSeatPrice, setExtraSeatPrice] = useState("100.00");
  const [interval, setInterval] = useState("MONTHLY");
  const [paymentTerms, setPaymentTerms] = useState("15");
  const [availFrom, setAvailFrom] = useState("");
  const [availTo, setAvailTo] = useState("");
  const [selectedTaxIds, setSelectedTaxIds] = useState<string[]>([]);

  // Policy toggles
  const [allowPause, setAllowPause] = useState(true);
  const [allowResume, setAllowResume] = useState(true);
  const [allowRenewal, setAllowRenewal] = useState(true);
  const [allowEarlyClosure, setAllowEarlyClosure] = useState(true);
  const [autoClose, setAutoClose] = useState(true);

  // Archive modal
  const [archiveTarget, setArchiveTarget] = useState<PlanItem | null>(null);
  const [archiveLoading, setArchiveLoading] = useState(false);

  const taxChoices = useCatalogChoices<TaxRuleItem>("/taxes", selectedTaxIds, createModalOpen);
  const taxes = taxChoices.items;

  const dialogDirty0 = useDialogChanges(createModalOpen, [name, description, baseFee, minSeats, extraSeatPrice, interval, paymentTerms, availFrom, availTo, selectedTaxIds, allowPause, allowResume, allowRenewal, allowEarlyClosure, autoClose]);
  useUnsavedChanges(dialogDirty0);

  const fetchPlans = useCallback(async () => {const request = ++requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", page.toString());
      params.set("page_size", pageSize.toString());
      if (search.trim()) params.set("search", search.trim());
      if (intervalFilter) params.set("interval", intervalFilter);
      if (activeFilter === "active") params.set("active", "true");
      if (activeFilter === "inactive") params.set("active", "false");
      if (availability) params.set("availability", availability);


      const res = await apiClient<PaginatedPlans>(`/plans?${params.toString()}`); if (request !== requestSequence.current) return;
      setPlans(res.items);
      setTotal(res.total);
    } catch (err) {if (request !== requestSequence.current) return;
      setError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to load subscription plans.");
    } finally {
      if (request === requestSequence.current) setLoading(false);
    }
  }, [page, pageSize, search, intervalFilter, activeFilter, availability]);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  if (user && user.role !== "ADMIN") {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <ShieldAlert className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Access Restricted</h2>
        <p className="text-sm text-slate-600 mt-1">
          Plan configuration is reserved exclusively for System Administrators.
        </p>
      </div>
    );
  }

  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    const bFee = parseFloat(baseFee);
    const mSeats = Number(minSeats);
    const ePrice = parseFloat(extraSeatPrice);
    const pTerms = Number(paymentTerms);

    if (Number.isNaN(bFee) || bFee < 0) {
      setCreateError("Base fee must be a valid non-negative number.");
      return;
    }
    if (Number.isNaN(mSeats) || mSeats < 1) {
      setCreateError("Minimum seats must be at least 1.");
      return;
    }
    if (Number.isNaN(ePrice) || ePrice < 0) {
      setCreateError("Extra seat price must be a valid non-negative number.");
      return;
    }

    setCreateLoading(true);
    try {
      await apiClient("/plans", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          base_fee: decimalInput(baseFee, {label: "Base fee"}),
          minimum_seats: mSeats,
          extra_seat_unit_price: decimalInput(extraSeatPrice, {label: "Extra seat price"}),
          interval,
          payment_term_days: Number.isNaN(pTerms) ? 15 : pTerms,
          available_from: availFrom || null,
          available_to: availTo || null,
          allow_pause: allowPause,
          allow_resume: allowResume,
          allow_renewal: allowRenewal,
          allow_early_closure: allowEarlyClosure,
          auto_close_on_expiry: autoClose,
          active: true,
          items: [],
          tax_rule_ids: selectedTaxIds,
        }),
      });

      setCreateModalOpen(false);
      setName("");
      setDescription("");
      fetchPlans();
    } catch (err) {
      setCreateError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to create plan.");
    } finally {
      setCreateLoading(false);
    }
  };

  const handleArchive = async () => {
    if (!archiveTarget) return;
    setArchiveLoading(true);
    try {
      await apiClient(`/plans/${archiveTarget.id}/archive`, {
        method: "POST",
      });
      setArchiveTarget(null);
      fetchPlans();
    } catch (err) {
      alert((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to archive plan.");
    } finally {
      setArchiveLoading(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Subscription Plans</h1>
          <p className="text-sm text-slate-500 mt-1">
            Configure recurring pricing packages, included seat tiers, and lifecycle governance policies.
          </p>
        </div>
        <button type="button"
          onClick={() => setCreateModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          <span>New Plan</span>
        </button>
      </div>
      <CollectionSort fields={[["name", "Name"], ["base_fee", "Base fee"], ["interval", "Interval"], ["created_at", "Created"]]} initial="name" descending={false} onChange={() => {if (page === 1) fetchPlans(); else setPage(1);}} ><label className="text-sm">Availability<select aria-label="Plan availability" className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm" value={availability} onChange={event => {setAvailability(event.target.value); setPage(1);}}><option value="">All dates</option><option value="available">Available today</option><option value="future">Not yet available</option><option value="expired">No longer available</option></select></label></CollectionSort>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex-1 w-full md:w-auto relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search plans by name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          <select aria-label="Billing interval filter"
            value={intervalFilter}
            onChange={(e) => {
              setIntervalFilter(e.target.value);
              setPage(1);
            }}
            className="border border-slate-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Intervals</option>
            <option value="DAILY">Daily</option>
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
            <option value="YEARLY">Yearly</option>
          </select>

          <select aria-label="Activity filter"
            value={activeFilter}
            onChange={(e) => {
              setActiveFilter(e.target.value);
              setPage(1);
            }}
            className="border border-slate-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="inactive">Archived Only</option>
          </select>

          <button type="button"
            onClick={() => fetchPlans()}
            disabled={loading}
            className="p-2 border border-slate-200 rounded-md text-slate-600 hover:bg-slate-50 transition"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3 text-red-700 text-sm">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <div className="flex-1">{error}</div>
          <button type="button"
            onClick={() => fetchPlans()}
            className="text-xs font-semibold underline hover:text-red-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* Plans Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <ScrollableRegion className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-slate-600 font-medium">
              <tr>
                <th className="px-6 py-3">Plan Name</th>
                <th className="px-6 py-3">Interval</th>
                <th className="px-6 py-3">Base Fee</th>
                <th className="px-6 py-3">Included Seats</th>
                <th className="px-6 py-3">Excess Seat Price</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && plans.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    Loading subscription plans...
                  </td>
                </tr>
              ) : plans.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <Layers className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-slate-600 font-medium">No plans found</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {search || intervalFilter || activeFilter
                        ? "Try clearing filters to find plans."
                        : "Create your first plan to start offering subscriptions."}
                    </p>
                  </td>
                </tr>
              ) : (
                plans.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/75 transition">
                    <td className="px-6 py-4 font-semibold text-slate-900">
                      <Link
                        href={`/app/plans/${p.id}`}
                        className="hover:text-blue-600 hover:underline flex items-center gap-2"
                      >
                        <Layers className="w-4 h-4 text-blue-500 shrink-0" />
                        <span>{p.name}</span>
                      </Link>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-block px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-xs font-semibold">
                        {p.interval}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-900">
                      {formatCurrency(p.base_fee)}
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      {p.minimum_seats} seat{p.minimum_seats === 1 ? "" : "s"}
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      {formatCurrency(p.extra_seat_unit_price)} / seat
                    </td>
                    <td className="px-6 py-4">
                      {p.active ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                          <Archive className="w-3 h-3" />
                          Archived
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <Link
                        href={`/app/plans/${p.id}`}
                        className="inline-flex items-center px-2.5 py-1 text-xs font-medium rounded border border-slate-300 text-slate-700 hover:bg-slate-100 transition"
                      >
                        Manage
                      </Link>
                      {p.active && (
                        <button type="button"
                          onClick={() => setArchiveTarget(p)}
                          className="inline-flex items-center px-2 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 rounded transition"
                        >
                          Archive
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </ScrollableRegion>

        {/* Pagination */}
        {total > pageSize && (
          <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-sm text-slate-600">
            <span>
              Showing {(page - 1) * pageSize + 1} to{" "}
              {Math.min(page * pageSize, total)} of {total} plans
            </span>
            <div className="flex items-center gap-2">
              <button type="button" aria-label="Previous page"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="p-1 rounded border border-slate-200 disabled:opacity-50 hover:bg-white"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs font-medium">
                Page {page} of {totalPages}
              </span>
              <button type="button" aria-label="Next page"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="p-1 rounded border border-slate-200 disabled:opacity-50 hover:bg-white"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* New Plan Modal */}
      {createModalOpen && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setCreateModalOpen(false)} busy={createLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-slate-900">Create New Subscription Plan</h2>

            {createError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreatePlan} className="space-y-4">
              <div>
                <label htmlFor="field-app-plans-page-tsx-1" className="block text-xs font-medium text-slate-700 mb-1">Plan Name *</label>
                <input id="field-app-plans-page-tsx-1"
                  type="text"
                  required
                  placeholder="e.g. Standard Business Plan"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="field-app-plans-page-tsx-2" className="block text-xs font-medium text-slate-700 mb-1">Description</label>
                <textarea id="field-app-plans-page-tsx-2"
                  rows={2}
                  placeholder="Plan summary and marketing overview..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label htmlFor="field-app-plans-page-tsx-3" className="block text-xs font-medium text-slate-700 mb-1">
                    Base Recurring Fee (₹) *
                  </label>
                  <input id="field-app-plans-page-tsx-3"
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={baseFee}
                    onChange={(e) => setBaseFee(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label htmlFor="field-app-plans-page-tsx-4" className="block text-xs font-medium text-slate-700 mb-1">
                    Included Minimum Seats *
                  </label>
                  <input id="field-app-plans-page-tsx-4"
                    type="number"
                    min="1"
                    required
                    value={minSeats}
                    onChange={(e) => setMinSeats(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label htmlFor="field-app-plans-page-tsx-5" className="block text-xs font-medium text-slate-700 mb-1">
                    Excess Seat Unit Price (₹) *
                  </label>
                  <input id="field-app-plans-page-tsx-5"
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={extraSeatPrice}
                    onChange={(e) => setExtraSeatPrice(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="field-app-plans-page-tsx-6" className="block text-xs font-medium text-slate-700 mb-1">
                    Billing Interval *
                  </label>
                  <select aria-label="Billing interval" id="field-app-plans-page-tsx-6"
                    value={interval}
                    onChange={(e) => setInterval(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="DAILY">DAILY</option>
                    <option value="WEEKLY">WEEKLY</option>
                    <option value="MONTHLY">MONTHLY</option>
                    <option value="YEARLY">YEARLY</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="field-app-plans-page-tsx-7" className="block text-xs font-medium text-slate-700 mb-1">
                    Payment Term Days *
                  </label>
                  <input id="field-app-plans-page-tsx-7"
                    type="number"
                    min="0"
                    required
                    value={paymentTerms}
                    onChange={(e) => setPaymentTerms(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="field-app-plans-page-tsx-8" className="block text-xs font-medium text-slate-700 mb-1">
                    Available From (Optional)
                  </label>
                  <input id="field-app-plans-page-tsx-8"
                    type="date"
                    value={availFrom}
                    onChange={(e) => setAvailFrom(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label htmlFor="field-app-plans-page-tsx-9" className="block text-xs font-medium text-slate-700 mb-1">
                    Available To (Optional)
                  </label>
                  <input id="field-app-plans-page-tsx-9"
                    type="date"
                    value={availTo}
                    onChange={(e) => setAvailTo(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Policy Toggles */}
              <div className="border border-slate-200 rounded-md p-3 space-y-2">
                <p className="text-xs font-semibold text-slate-800">Lifecycle Governance Policy</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  <label className="flex items-center gap-1.5 text-slate-700">
                    <input
                      type="checkbox"
                      checked={allowPause}
                      onChange={(e) => setAllowPause(e.target.checked)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span>Allow Pause</span>
                  </label>
                  <label className="flex items-center gap-1.5 text-slate-700">
                    <input
                      type="checkbox"
                      checked={allowResume}
                      onChange={(e) => setAllowResume(e.target.checked)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span>Allow Resume</span>
                  </label>
                  <label className="flex items-center gap-1.5 text-slate-700">
                    <input
                      type="checkbox"
                      checked={allowRenewal}
                      onChange={(e) => setAllowRenewal(e.target.checked)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span>Allow Renewal</span>
                  </label>
                  <label className="flex items-center gap-1.5 text-slate-700">
                    <input
                      type="checkbox"
                      checked={allowEarlyClosure}
                      onChange={(e) => setAllowEarlyClosure(e.target.checked)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span>Allow Early Close</span>
                  </label>
                  <label className="flex items-center gap-1.5 text-slate-700">
                    <input
                      type="checkbox"
                      checked={autoClose}
                      onChange={(e) => setAutoClose(e.target.checked)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span>Auto-close on Expiry</span>
                  </label>
                </div>
              </div>

              <CatalogChoiceSearch label="Find tax rule" source={taxChoices} />

              {taxes.length > 0 && (
                <div>
                  <p className="block text-xs font-medium text-slate-700 mb-1">
                    Plan Tax Rules
                  </p>
                  <div className="max-h-24 overflow-y-auto border border-slate-200 rounded-md p-2 space-y-1">
                    {taxes.map((t) => (
                      <label key={t.id} className="flex items-center gap-2 text-xs text-slate-700">
                        <input
                          type="checkbox"
                          checked={selectedTaxIds.includes(t.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedTaxIds([...selectedTaxIds, t.id]);
                            } else {
                              setSelectedTaxIds(selectedTaxIds.filter((id) => id !== t.id));
                            }
                          }}
                          className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span>
                          {t.name} ({parseFloat(t.rate)}%)
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  data-discard-form onClick={() => setCreateModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50"
                >
                  {createLoading ? "Saving..." : "Create Plan"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}

      {/* Archive Modal */}
      {archiveTarget && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setArchiveTarget(null)} busy={archiveLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Archive Plan</h2>
            <p className="text-sm text-slate-600">
              Are you sure you want to archive <strong>{archiveTarget.name}</strong>?
            </p>
            <div className="p-3 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
              Archiving prevents new subscriptions and quotes from selecting this plan.
              Existing confirmed agreements and active terms continue operating safely.
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setArchiveTarget(null)}
                className="px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleArchive}
                disabled={archiveLoading}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50"
              >
                {archiveLoading ? "Archiving..." : "Confirm Archive"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
