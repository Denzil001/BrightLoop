"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { decimalInput, DecimalInputError } from "@/lib/decimal";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback, useRef } from "react";
import {
  Plus,
  Search,
  RefreshCw,
  Receipt,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
  Edit,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import CollectionSort from "@/components/CollectionSort";
import { useQueryState } from "@/lib/useUrlFilters";
import { useDialogChanges, useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient, ApiError } from "@/lib/api";

interface TaxRuleItem {
  id: string;
  name: string;
  classification: string;
  rate: string;
  active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

interface PaginatedTaxes {
  items: TaxRuleItem[];
  page: number;
  page_size: number;
  total: number;
}

export default function TaxRulesPage() {
  const requestSequence = useRef(0);
  const { user } = useAuth();

  const [taxes, setTaxes] = useState<TaxRuleItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useQueryState("page", 1);
  const [pageSize] = useState(15);
  const [search, setSearch] = useQueryState("search", "");
  const [activeFilter, setActiveFilter] = useQueryState<string>("active", "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create / Edit modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTax, setEditingTax] = useState<TaxRuleItem | null>(null);
  const [name, setName] = useState("");
  const [classification, setClassification] = useState("GST");
  const [rate, setRate] = useState("18.0000");
  const [active, setActive] = useState(true);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const dialogDirty0 = useDialogChanges(modalOpen, [name, classification, rate, active]);
  useUnsavedChanges(dialogDirty0);

  const fetchTaxes = useCallback(async () => {const request = ++requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", page.toString());
      params.set("page_size", pageSize.toString());
      if (search.trim()) params.set("search", search.trim());
      if (activeFilter === "active") params.set("active", "true");
      if (activeFilter === "inactive") params.set("active", "false");

      const res = await apiClient<PaginatedTaxes>(`/taxes?${params.toString()}`); if (request !== requestSequence.current) return;
      setTaxes(res.items);
      setTotal(res.total);
    } catch (err) {if (request !== requestSequence.current) return;
      setError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to load tax rules.");
    } finally {
      if (request === requestSequence.current) setLoading(false);
    }
  }, [page, pageSize, search, activeFilter]);

  useEffect(() => {
    fetchTaxes();
  }, [fetchTaxes]);

  if (user && user.role !== "ADMIN") {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <ShieldAlert className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Access Restricted</h2>
        <p className="text-sm text-slate-600 mt-1">
          Tax rules configuration is reserved exclusively for System Administrators.
        </p>
      </div>
    );
  }

  const openCreateModal = () => {
    setEditingTax(null);
    setName("");
    setClassification("GST");
    setRate("18.0000");
    setActive(true);
    setModalError(null);
    setModalOpen(true);
  };

  const openEditModal = (tax: TaxRuleItem) => {
    setEditingTax(tax);
    setName(tax.name);
    setClassification(tax.classification);
    setRate(tax.rate);
    setActive(tax.active);
    setModalError(null);
    setModalOpen(true);
  };

  const handleSaveTax = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);

    const rateNum = parseFloat(rate);
    if (Number.isNaN(rateNum) || rateNum < 0 || rateNum > 100) {
      setModalError("Tax rate must be between 0.00% and 100.00%.");
      return;
    }

    setModalLoading(true);
    try {
      if (editingTax) {
        await apiClient(`/taxes/${editingTax.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: name.trim(),
            classification: classification.trim(),
            rate: decimalInput(rate, {scale: 4, maxIntegerDigits: 3, label: "Tax rate"}),
            active,
          }),
        });
      } else {
        await apiClient("/taxes", {
          method: "POST",
          body: JSON.stringify({
            name: name.trim(),
            classification: classification.trim(),
            rate: decimalInput(rate, {scale: 4, maxIntegerDigits: 3, label: "Tax rate"}),
            active,
          }),
        });
      }
      setModalOpen(false);
      fetchTaxes();
    } catch (err) {
      setModalError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to save tax rule.");
    } finally {
      setModalLoading(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Tax Rules</h1>
          <p className="text-sm text-slate-500 mt-1">
            Configure jurisdiction tax rules, classifications, and exclusive percentage rates.
          </p>
        </div>
        <button type="button"
          onClick={openCreateModal}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          <span>New Tax Rule</span>
        </button>
      </div>
      <CollectionSort fields={[["created_at", "Created"], ["name", "Name"], ["rate", "Rate"]]} initial="created_at" descending={true} onChange={() => {if (page === 1) fetchTaxes(); else setPage(1);}} />

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex-1 w-full md:w-auto relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search tax rules by name or classification..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
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
            <option value="inactive">Disabled Only</option>
          </select>

          <button type="button"
            onClick={() => fetchTaxes()}
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
            onClick={() => fetchTaxes()}
            className="text-xs font-semibold underline hover:text-red-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* Taxes Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <ScrollableRegion className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-slate-600 font-medium">
              <tr>
                <th className="px-6 py-3">Rule Name</th>
                <th className="px-6 py-3">Classification</th>
                <th className="px-6 py-3">Rate</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && taxes.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                    Loading tax rules...
                  </td>
                </tr>
              ) : taxes.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center">
                    <Receipt className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-slate-600 font-medium">No tax rules found</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {search || activeFilter
                        ? "Try clearing filters to find tax rules."
                        : "Create tax rules to apply to products and subscription plans."}
                    </p>
                  </td>
                </tr>
              ) : (
                taxes.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50/75 transition">
                    <td className="px-6 py-4 font-semibold text-slate-900 flex items-center gap-2">
                      <Receipt className="w-4 h-4 text-blue-500 shrink-0" />
                      <span>{t.name}</span>
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      <span className="inline-block px-2 py-0.5 rounded bg-slate-100 text-xs font-mono font-medium text-slate-700">
                        {t.classification}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono font-semibold text-slate-900">
                      {parseFloat(t.rate)}%
                    </td>
                    <td className="px-6 py-4">
                      {t.active ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                          <XCircle className="w-3 h-3" />
                          Disabled
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button type="button"
                        onClick={() => openEditModal(t)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border border-slate-300 text-slate-700 hover:bg-slate-100 transition"
                      >
                        <Edit className="w-3 h-3" />
                        <span>Edit</span>
                      </button>
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
              {Math.min(page * pageSize, total)} of {total} tax rules
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

      {/* Modal: Create / Edit Tax Rule */}
      {modalOpen && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setModalOpen(false)} busy={modalLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">
              {editingTax ? "Edit Tax Rule" : "Create New Tax Rule"}
            </h2>

            {modalError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {modalError}
              </div>
            )}

            <form onSubmit={handleSaveTax} className="space-y-4">
              <div>
                <label htmlFor="field-app-taxes-page-tsx-1" className="block text-xs font-medium text-slate-700 mb-1">
                  Rule Name *
                </label>
                <input id="field-app-taxes-page-tsx-1"
                  type="text"
                  required
                  placeholder="e.g. Standard GST 18%"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="field-app-taxes-page-tsx-2" className="block text-xs font-medium text-slate-700 mb-1">
                  Tax Classification *
                </label>
                <input id="field-app-taxes-page-tsx-2"
                  type="text"
                  required
                  placeholder="e.g. GST, VAT, SALES_TAX"
                  value={classification}
                  onChange={(e) => setClassification(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase font-mono"
                />
              </div>

              <div>
                <label htmlFor="field-app-taxes-page-tsx-3" className="block text-xs font-medium text-slate-700 mb-1">
                  Tax Rate (%) *
                </label>
                <input id="field-app-taxes-page-tsx-3"
                  type="number"
                  step="0.0001"
                  min="0"
                  max="100"
                  required
                  placeholder="18.0000"
                  value={rate}
                  onChange={(e) => setRate(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Rate in percentage points (e.g. 18 for 18% GST).
                </p>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="taxActive"
                  checked={active}
                  onChange={(e) => setActive(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="taxActive" className="text-xs font-medium text-slate-700">
                  Active in catalog
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  data-discard-form onClick={() => setModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modalLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50"
                >
                  {modalLoading ? "Saving..." : "Save Rule"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}
    </div>
  );
}
