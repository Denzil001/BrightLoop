"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Plus,
  Search,
  RefreshCw,
  FileText,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
  Layers,
  Edit,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import CollectionSort from "@/components/CollectionSort";
import { useQueryState } from "@/lib/useUrlFilters";
import CatalogChoiceSearch from "@/components/CatalogChoiceSearch";
import { useCatalogChoices } from "@/lib/useCatalogChoices";
import { useDialogChanges, useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient, ApiError } from "@/lib/api";

interface TemplateItem {
  id: string;
  name: string;
  description?: string;
  plan_id: string;
  plan_name?: string;
  validity_days: number;
  active: boolean;
  version: number;
  created_at: string;
  lines: Array<{ id: string; ordinal: number; quantity: number }>;
}

interface PlanItem {
  id: string;
  name: string;
  active: boolean;
}

interface PaginatedTemplates {
  items: TemplateItem[];
  page: number;
  page_size: number;
  total: number;
}

export default function QuotationTemplatesListPage() {
  const requestSequence = useRef(0);
  const { user } = useAuth();
  const router = useRouter();

  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useQueryState("page", 1);
  const [pageSize] = useState(15);
  const [search, setSearch] = useQueryState("search", "");
  const [planFilter, setPlanFilter] = useQueryState("plan_id", "");
  const [activeFilter, setActiveFilter] = useQueryState("active", "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [planId, setPlanId] = useState("");
  const [validityDays, setValidityDays] = useState("30");
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const planChoices = useCatalogChoices<PlanItem>("/plans", [planId, planFilter]);
  const plans = planChoices.items;

  const dialogDirty0 = useDialogChanges(createModalOpen, [name, description, planId, validityDays]);
  useUnsavedChanges(dialogDirty0);

  const fetchTemplates = useCallback(async () => {const request = ++requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", page.toString());
      params.set("page_size", pageSize.toString());
      if (search.trim()) params.set("search", search.trim());
      if (planFilter) params.set("plan_id", planFilter);
      if (activeFilter === "active") params.set("active", "true");
      if (activeFilter === "inactive") params.set("active", "false");

      const res = await apiClient<PaginatedTemplates>(`/quotation-templates?${params.toString()}`); if (request !== requestSequence.current) return;
      setTemplates(res.items);
      setTotal(res.total);
    } catch (err) {if (request !== requestSequence.current) return;
      setError(err instanceof ApiError ? err.message : "Failed to load quotation templates.");
    } finally {
      if (request === requestSequence.current) setLoading(false);
    }
  }, [page, pageSize, search, planFilter, activeFilter]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  if (user && user.role !== "ADMIN") {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <ShieldAlert className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Access Restricted</h2>
        <p className="text-sm text-slate-600 mt-1">
          Quotation template configuration is reserved exclusively for System Administrators.
        </p>
      </div>
    );
  }

  const handleCreateTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    const valDays = parseInt(validityDays, 10);
    if (Number.isNaN(valDays) || valDays < 1) {
      setCreateError("Validity days must be at least 1.");
      return;
    }
    if (!planId) {
      setCreateError("Please select a base subscription plan.");
      return;
    }

    setCreateLoading(true);
    try {
      const res = await apiClient<TemplateItem>("/quotation-templates", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          plan_id: planId,
          validity_days: valDays,
          active: false, // Incomplete without lines
          lines: [],
        }),
      });

      setCreateModalOpen(false);
      // Navigate directly to editor to complete line items
      router.push(`/app/quotation-templates/${res.id}`);
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to create quotation template.");
    } finally {
      setCreateLoading(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Quotation Templates
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Preconfigure commercial packages with bundled line items and default quote validity windows.
          </p>
        </div>
        <button type="button"
          onClick={() => setCreateModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          <span>New Template</span>
        </button>
      </div>
      <CatalogChoiceSearch label="Find plans for template filter" source={planChoices} />
      <CollectionSort fields={[["name", "Name"], ["created_at", "Created"], ["validity_days", "Validity days"]]} initial="name" descending={false} onChange={() => {if (page === 1) fetchTemplates(); else setPage(1);}} />

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex-1 w-full md:w-auto relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search templates by name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          <select aria-label="Plan filter"
            value={planFilter}
            onChange={(e) => {
              setPlanFilter(e.target.value);
              setPage(1);
            }}
            className="border border-slate-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Plans</option>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
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
            <option value="inactive">Inactive Only</option>
          </select>

          <button type="button"
            onClick={() => fetchTemplates()}
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
            onClick={() => fetchTemplates()}
            className="text-xs font-semibold underline hover:text-red-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* Templates Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <ScrollableRegion className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-slate-600 font-medium">
              <tr>
                <th className="px-6 py-3">Template Name</th>
                <th className="px-6 py-3">Default Plan</th>
                <th className="px-6 py-3">Validity Days</th>
                <th className="px-6 py-3">Configured Lines</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && templates.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    Loading quotation templates...
                  </td>
                </tr>
              ) : templates.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center">
                    <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-slate-600 font-medium">No quotation templates found</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {search || planFilter || activeFilter
                        ? "Try clearing filters to find templates."
                        : "Create quotation templates to streamline sales quotation generation."}
                    </p>
                  </td>
                </tr>
              ) : (
                templates.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50/75 transition">
                    <td className="px-6 py-4 font-semibold text-slate-900">
                      <Link
                        href={`/app/quotation-templates/${t.id}`}
                        className="hover:text-blue-600 hover:underline flex items-center gap-2"
                      >
                        <FileText className="w-4 h-4 text-blue-500 shrink-0" />
                        <span>{t.name}</span>
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-800">
                        <Layers className="w-3.5 h-3.5 text-slate-500" />
                        {t.plan_name || "Plan"}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-slate-900">
                      {t.validity_days} days
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      <span className="inline-block px-2 py-0.5 rounded bg-slate-100 text-xs font-medium">
                        {t.lines.length} line{t.lines.length === 1 ? "" : "s"}
                      </span>
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
                          {t.lines.length === 0 ? "Incomplete" : "Inactive"}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link
                        href={`/app/quotation-templates/${t.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border border-slate-300 text-slate-700 hover:bg-slate-100 transition"
                      >
                        <Edit className="w-3 h-3" />
                        <span>Configure</span>
                      </Link>
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
              {Math.min(page * pageSize, total)} of {total} templates
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

      {/* Create Modal */}
      {createModalOpen && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setCreateModalOpen(false)} busy={createLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Create Quotation Template</h2>

            {createError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateTemplate} className="space-y-4">
              <div>
                <label htmlFor="field-app-quotation-templates-page-tsx-1" className="block text-xs font-medium text-slate-700 mb-1">
                  Template Name *
                </label>
                <input id="field-app-quotation-templates-page-tsx-1"
                  type="text"
                  required
                  placeholder="e.g. Standard SaaS Onboarding"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="field-app-quotation-templates-page-tsx-2" className="block text-xs font-medium text-slate-700 mb-1">Description</label>
                <textarea id="field-app-quotation-templates-page-tsx-2"
                  rows={2}
                  placeholder="Summary of template usage..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <p className="block text-xs font-medium text-slate-700 mb-1">
                  Base Subscription Plan *
                </p>
                <CatalogChoiceSearch label="Find template plan" source={planChoices} />
                <select
                  required
                  aria-label="Template base plan"
                  value={planId}
                  onChange={(e) => setPlanId(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
                >
                  <option value="">Select a plan...</option>
                  {plans.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="field-app-quotation-templates-page-tsx-3" className="block text-xs font-medium text-slate-700 mb-1">
                  Quote Validity Days *
                </label>
                <input id="field-app-quotation-templates-page-tsx-3"
                  type="number"
                  min="1"
                  required
                  value={validityDays}
                  onChange={(e) => setValidityDays(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

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
                  {createLoading ? "Creating..." : "Create & Configure Lines"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}
    </div>
  );
}
