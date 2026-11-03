"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { formatCurrency } from "@/lib/utils";
import { decimalInput, DecimalInputError } from "@/lib/decimal";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback, useRef } from "react";
import {
  Plus,
  Search,
  RefreshCw,
  Percent,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { businessDate } from "@/lib/payments";
import { useAuth } from "@/context/AuthContext";
import CollectionSort from "@/components/CollectionSort";
import { useQueryState } from "@/lib/useUrlFilters";
import CatalogChoiceSearch from "@/components/CatalogChoiceSearch";
import { useCatalogChoices } from "@/lib/useCatalogChoices";
import { useDialogChanges, useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient, ApiError } from "@/lib/api";

interface DiscountRevision {
  id: string;
  revision: number;
  type: string;
  amount?: string;
  rate?: string;
  minimum_purchase?: string;
  minimum_quantity?: number;
  scope: string;
  valid_from: string;
  valid_to: string;
  product_ids: string[];
}

interface DiscountRuleItem {
  id: string;
  name: string;
  maximum_uses?: number;
  disabled_from?: string;
  version: number;
  created_at: string;
  revisions: DiscountRevision[];
  current_revision?: DiscountRevision;
  redemption_count: number;
}

interface ProductItem {
  id: string;
  name: string;
  active: boolean;
}

interface PaginatedDiscounts {
  items: DiscountRuleItem[];
  page: number;
  page_size: number;
  total: number;
}

export default function DiscountRulesPage() {
  const requestSequence = useRef(0);
  const { user } = useAuth();

  const [discounts, setDiscounts] = useState<DiscountRuleItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useQueryState("page", 1);
  const [pageSize] = useState(15);
  const [search, setSearch] = useQueryState("search", "");
  const [activeFilter, setActiveFilter] = useQueryState<string>("active", "");
  const [scopeFilter, setScopeFilter] = useQueryState("scope", "");
  const [typeFilter, setTypeFilter] = useQueryState("discount_type", "");
  const [eligibility, setEligibility] = useQueryState("eligibility", "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create Rule Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [ruleName, setRuleName] = useState("");
  const [maxUses, setMaxUses] = useState("");
  const [discScope, setDiscScope] = useState("SUBSCRIPTION");
  const [discType, setDiscType] = useState("PERCENT");
  const [discRate, setDiscRate] = useState("10.00");
  const [discAmount, setDiscAmount] = useState("10.00");
  const [minPurchase, setMinPurchase] = useState("");
  const [minQty, setMinQty] = useState("");
  const [validFrom, setValidFrom] = useState(businessDate());
  const [validTo, setValidTo] = useState(
    businessDate(new Date(Date.now() + 365 * 86400000))
  );
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Add Revision Modal
  const [revisionModalRule, setRevisionModalRule] = useState<DiscountRuleItem | null>(null);
  const [revType, setRevType] = useState("PERCENT");
  const [revRate, setRevRate] = useState("15.00");
  const [revAmount, setRevAmount] = useState("15.00");
  const [revScope, setRevScope] = useState("SUBSCRIPTION");
  const [revMinPurchase, setRevMinPurchase] = useState("");
  const [revMinQty, setRevMinQty] = useState("");
  const [revValidFrom, setRevValidFrom] = useState(businessDate());
  const [revValidTo, setRevValidTo] = useState(
    businessDate(new Date(Date.now() + 365 * 86400000))
  );
  const [revProductIds, setRevProductIds] = useState<string[]>([]);
  const [revLoading, setRevLoading] = useState(false);
  const [revError, setRevError] = useState<string | null>(null);

  // Deactivate Modal
  const [deactRule, setDeactRule] = useState<DiscountRuleItem | null>(null);
  const [deactDate, setDeactDate] = useState(businessDate());
  const [deactReason, setDeactReason] = useState("");
  const [deactLoading, setDeactLoading] = useState(false);

  const productChoices = useCatalogChoices<ProductItem>("/products", [...selectedProductIds, ...revProductIds], createModalOpen || Boolean(revisionModalRule));
  const products = productChoices.items;

  const dialogDirty0 = useDialogChanges(createModalOpen, [ruleName, maxUses, discScope, discType, discRate, discAmount, minPurchase, minQty, validFrom, validTo, selectedProductIds]);
  const dialogDirty1 = useDialogChanges(Boolean(revisionModalRule), [revType, revRate, revAmount, revScope, revMinPurchase, revMinQty, revValidFrom, revValidTo, revProductIds]);
  const dialogDirty2 = useDialogChanges(Boolean(deactRule), [deactDate, deactReason]);
  useUnsavedChanges(dialogDirty0 || dialogDirty1 || dialogDirty2);

  const fetchDiscounts = useCallback(async () => {const request = ++requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", page.toString());
      params.set("page_size", pageSize.toString());
      if (search.trim()) params.set("search", search.trim());
      if (activeFilter === "active") params.set("active", "true");
      if (activeFilter === "inactive") params.set("active", "false");
      if (scopeFilter) params.set("scope", scopeFilter);
      if (typeFilter) params.set("discount_type", typeFilter);
      if (eligibility) params.set("eligibility", eligibility);


      const res = await apiClient<PaginatedDiscounts>(`/discounts?${params.toString()}`); if (request !== requestSequence.current) return;
      setDiscounts(res.items);
      setTotal(res.total);
    } catch (err) {if (request !== requestSequence.current) return;
      setError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to load discount rules.");
    } finally {
      if (request === requestSequence.current) setLoading(false);
    }
  }, [page, pageSize, search, activeFilter, scopeFilter, typeFilter, eligibility]);

  useEffect(() => {
    fetchDiscounts();
  }, [fetchDiscounts]);

  if (user && user.role !== "ADMIN") {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <ShieldAlert className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Access Restricted</h2>
        <p className="text-sm text-slate-600 mt-1">
          Discount rule configuration is reserved exclusively for System Administrators.
        </p>
      </div>
    );
  }

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    if (discScope === "PRODUCT" && selectedProductIds.length === 0) {
      setCreateError("At least one product must be selected for PRODUCT scoped discounts.");
      return;
    }

    if (validTo < validFrom) {
      setCreateError("End validity date cannot be earlier than start date.");
      return;
    }

    const payloadRevision: Record<string, unknown> = {
      type: discType,
      scope: discScope,
      valid_from: validFrom,
      valid_to: validTo,
      product_ids: discScope === "PRODUCT" ? selectedProductIds : [],
    };

    try {
    if (discType === "PERCENT") {
      const r = parseFloat(discRate);
      if (Number.isNaN(r) || r <= 0 || r > 100) {
        setCreateError("Percentage rate must be greater than 0 and at most 100.");
        return;
      }
      payloadRevision.rate = decimalInput(discRate, {scale: 4, maxIntegerDigits: 3, label: "Discount rate"});
      payloadRevision.amount = null;
    } else {
      const a = parseFloat(discAmount);
      if (Number.isNaN(a) || a <= 0) {
        setCreateError("Fixed discount amount must be greater than 0.");
        return;
      }
      payloadRevision.amount = decimalInput(discAmount, {label: "Fixed discount"});
      payloadRevision.rate = null;
    }

    if (minPurchase) {
      payloadRevision.minimum_purchase = decimalInput(minPurchase, {label: "Minimum purchase"});
    }
    if (minQty) {
      payloadRevision.minimum_quantity = Number(minQty);
    }

    } catch (error) {setCreateError(error instanceof Error ? error.message : "Enter valid discount amounts."); return;}

    setCreateLoading(true);
    try {
      await apiClient("/discounts", {
        method: "POST",
        body: JSON.stringify({
          name: ruleName.trim(),
          maximum_uses: maxUses ? Number(maxUses) : null,
          initial_revision: payloadRevision,
        }),
      });

      setCreateModalOpen(false);
      setRuleName("");
      setMaxUses("");
      fetchDiscounts();
    } catch (err) {
      setCreateError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to create discount rule.");
    } finally {
      setCreateLoading(false);
    }
  };

  const openRevisionModal = (rule: DiscountRuleItem) => {
    setRevisionModalRule(rule);
    const curr = rule.current_revision || rule.revisions[0];
    if (curr) {
      setRevType(curr.type);
      setRevScope(curr.scope);
      setRevRate(curr.rate || "15.00");
      setRevAmount(curr.amount || "15.00");
      setRevMinPurchase(curr.minimum_purchase || "");
      setRevMinQty(curr.minimum_quantity ? curr.minimum_quantity.toString() : "");
      setRevProductIds(curr.product_ids || []);
    }
    setRevError(null);
  };

  const handleCreateRevision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!revisionModalRule) return;
    setRevError(null);

    if (revScope === "PRODUCT" && revProductIds.length === 0) {
      setRevError("At least one product must be selected for PRODUCT scoped discounts.");
      return;
    }

    const payloadRevision: Record<string, unknown> = {
      type: revType,
      scope: revScope,
      valid_from: revValidFrom,
      valid_to: revValidTo,
      product_ids: revScope === "PRODUCT" ? revProductIds : [],
    };

    try {
    if (revType === "PERCENT") {
      const r = parseFloat(revRate);
      if (Number.isNaN(r) || r <= 0 || r > 100) {
        setRevError("Percentage rate must be greater than 0 and at most 100.");
        return;
      }
      payloadRevision.rate = decimalInput(revRate, {scale: 4, maxIntegerDigits: 3, label: "Discount rate"});
      payloadRevision.amount = null;
    } else {
      const a = parseFloat(revAmount);
      if (Number.isNaN(a) || a <= 0) {
        setRevError("Fixed discount amount must be greater than 0.");
        return;
      }
      payloadRevision.amount = decimalInput(revAmount, {label: "Fixed discount"});
      payloadRevision.rate = null;
    }

    if (revMinPurchase) payloadRevision.minimum_purchase = decimalInput(revMinPurchase, {label: "Minimum purchase"});
    if (revMinQty) payloadRevision.minimum_quantity = Number(revMinQty);

    } catch (error) {setRevError(error instanceof Error ? error.message : "Enter valid discount amounts."); return;}

    setRevLoading(true);
    try {
      await apiClient(`/discounts/${revisionModalRule.id}/revisions`, {
        method: "POST",
        body: JSON.stringify(payloadRevision),
      });

      setRevisionModalRule(null);
      fetchDiscounts();
    } catch (err) {
      setRevError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to publish revision.");
    } finally {
      setRevLoading(false);
    }
  };

  const handleDeactivate = async () => {
    if (!deactRule) return;
    setDeactLoading(true);
    try {
      await apiClient(`/discounts/${deactRule.id}/deactivate`, {
        method: "POST",
        body: JSON.stringify({
          disabled_from: deactDate,
          reason: deactReason.trim() || null,
        }),
      });
      setDeactRule(null);
      fetchDiscounts();
    } catch (err) {
      alert((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to deactivate discount rule.");
    } finally {
      setDeactLoading(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Discount Rules</h1>
          <p className="text-sm text-slate-500 mt-1">
            Configure whole-subscription or product-specific discounts with versioned revisions and usage caps.
          </p>
        </div>
        <button type="button"
          onClick={() => setCreateModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          <span>New Discount Rule</span>
        </button>
      </div>
      <CollectionSort fields={[["name", "Name"], ["created_at", "Created"]]} initial="name" descending={false} onChange={() => {if (page === 1) fetchDiscounts(); else setPage(1);}} ><label className="text-sm">Scope<select aria-label="Scope" className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm" value={scopeFilter} onChange={event => {setScopeFilter(event.target.value); setPage(1);}}><option value="">All</option><option value="PRODUCT">Product</option><option value="SUBSCRIPTION">Subscription</option></select></label><label className="text-sm">Discount type<select aria-label="Discount type" className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm" value={typeFilter} onChange={event => {setTypeFilter(event.target.value); setPage(1);}}><option value="">All</option><option value="FIXED">Fixed</option><option value="PERCENT">Percentage</option></select></label><label className="text-sm">Eligibility<select aria-label="Eligibility" className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm" value={eligibility} onChange={event => {setEligibility(event.target.value); setPage(1);}}><option value="">All</option><option value="eligible">Eligible today</option><option value="not_yet_valid">Not yet valid</option><option value="expired">Expired</option><option value="exhausted">Exhausted</option><option value="disabled">Disabled</option></select></label></CollectionSort>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex-1 w-full md:w-auto relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search discount rules by name..."
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
            <option value="inactive">Deactivated Only</option>
          </select>

          <button type="button"
            onClick={() => fetchDiscounts()}
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
            onClick={() => fetchDiscounts()}
            className="text-xs font-semibold underline hover:text-red-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* Discounts Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <ScrollableRegion className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-slate-600 font-medium">
              <tr>
                <th className="px-6 py-3">Discount Rule</th>
                <th className="px-6 py-3">Scope</th>
                <th className="px-6 py-3">Value</th>
                <th className="px-6 py-3">Thresholds</th>
                <th className="px-6 py-3">Usage / Cap</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && discounts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    Loading discount rules...
                  </td>
                </tr>
              ) : discounts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <Percent className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-slate-600 font-medium">No discount rules found</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {search || activeFilter
                        ? "Try clearing filters to find discount rules."
                        : "Create discount rules to incentivize customer subscriptions."}
                    </p>
                  </td>
                </tr>
              ) : (
                discounts.map((d) => {
                  const rev = d.current_revision || d.revisions[0];
                  const isDeactivated = Boolean(d.disabled_from);
                  return (
                    <tr key={d.id} className="hover:bg-slate-50/75 transition">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900 flex items-center gap-2">
                          <Percent className="w-4 h-4 text-blue-500 shrink-0" />
                          <span>{d.name}</span>
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          Revision {rev?.revision || 1} &bull; Valid {rev?.valid_from} to {rev?.valid_to}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-block px-2 py-0.5 rounded bg-slate-100 text-xs font-mono font-medium text-slate-700">
                          {rev?.scope}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono font-bold text-slate-900">
                        {rev?.type === "PERCENT"
                          ? `${parseFloat(rev.rate || "0")}%`
                          : formatCurrency(rev?.amount)}
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-600">
                        {rev?.minimum_purchase && (
                          <div>Min spend: {formatCurrency(rev.minimum_purchase)}</div>
                        )}
                        {rev?.minimum_quantity && (
                          <div>Min qty/seats: {rev.minimum_quantity}</div>
                        )}
                        {!rev?.minimum_purchase && !rev?.minimum_quantity && (
                          <span className="text-slate-500">None</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-xs font-mono">
                        {d.redemption_count} / {d.maximum_uses !== null ? d.maximum_uses : "∞"}
                      </td>
                      <td className="px-6 py-4">
                        {!isDeactivated ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
                            <XCircle className="w-3 h-3" />
                            Deactivated
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right space-x-2">
                        <button type="button"
                          onClick={() => openRevisionModal(d)}
                          className="inline-flex items-center px-2 py-1 text-xs font-medium rounded border border-slate-300 text-slate-700 hover:bg-slate-100 transition"
                        >
                          New Revision
                        </button>
                        {!isDeactivated && (
                          <button type="button"
                            onClick={() => {
                              setDeactRule(d);
                              setDeactDate(businessDate());
                            }}
                            className="inline-flex items-center px-2 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 rounded transition"
                          >
                            Deactivate
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </ScrollableRegion>

        {/* Pagination */}
        {total > pageSize && (
          <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-sm text-slate-600">
            <span>
              Showing {(page - 1) * pageSize + 1} to{" "}
              {Math.min(page * pageSize, total)} of {total} discount rules
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

      {/* Modal: Create Discount Rule */}
      {createModalOpen && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setCreateModalOpen(false)} busy={createLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-slate-900">Create New Discount Rule</h2>

            {createError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateRule} className="space-y-4">
              <div>
                <label htmlFor="field-app-discounts-page-tsx-1" className="block text-xs font-medium text-slate-700 mb-1">
                  Discount Rule Name *
                </label>
                <input id="field-app-discounts-page-tsx-1"
                  type="text"
                  required
                  placeholder="e.g. Annual Subscription 10% Off"
                  value={ruleName}
                  onChange={(e) => setRuleName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="field-app-discounts-page-tsx-2" className="block text-xs font-medium text-slate-700 mb-1">
                  Global Usage Cap (Optional)
                </label>
                <input id="field-app-discounts-page-tsx-2"
                  type="number"
                  min="1"
                  placeholder="Leave empty for unlimited redemptions"
                  value={maxUses}
                  onChange={(e) => setMaxUses(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="border border-slate-200 rounded-md p-3 space-y-3 bg-slate-50/50">
                <p className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                  Initial Revision Terms
                </p>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="field-app-discounts-page-tsx-3" className="block text-xs font-medium text-slate-700 mb-1">Scope *</label>
                    <select id="field-app-discounts-page-tsx-3"
                      aria-label="Discount scope"
                  value={discScope}
                      onChange={(e) => setDiscScope(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
                    >
                      <option value="SUBSCRIPTION">Whole Subscription</option>
                      <option value="PRODUCT">Specific Products</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="field-app-discounts-page-tsx-4" className="block text-xs font-medium text-slate-700 mb-1">Type *</label>
                    <select aria-label="Discount type" id="field-app-discounts-page-tsx-4"
                      value={discType}
                      onChange={(e) => setDiscType(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
                    >
                      <option value="PERCENT">PERCENT (%)</option>
                      <option value="FIXED">FIXED (₹)</option>
                    </select>
                  </div>
                </div>

                {discType === "PERCENT" ? (
                  <div>
                    <label htmlFor="field-app-discounts-page-tsx-5" className="block text-xs font-medium text-slate-700 mb-1">
                      Percentage Rate (0 - 100%) *
                    </label>
                    <input id="field-app-discounts-page-tsx-5"
                      type="number"
                      step="0.0001"
                      min="0.01"
                      max="100"
                      required
                      value={discRate}
                      onChange={(e) => setDiscRate(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                    />
                  </div>
                ) : (
                  <div>
                    <label htmlFor="field-app-discounts-page-tsx-6" className="block text-xs font-medium text-slate-700 mb-1">
                      Fixed Discount Amount (₹) *
                    </label>
                    <input id="field-app-discounts-page-tsx-6"
                      type="number"
                      step="0.01"
                      min="0.01"
                      required
                      value={discAmount}
                      onChange={(e) => setDiscAmount(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                    />
                  </div>
                )}

                {discScope === "PRODUCT" && (
                  <div>
                    <CatalogChoiceSearch label="Find eligible product" source={productChoices} />
                    <p className="block text-xs font-medium text-slate-700 mb-1">
                      Eligible Products *
                    </p>
                    <div className="max-h-28 overflow-y-auto border border-slate-200 rounded-md p-2 space-y-1 bg-white">
                      {products.map((p) => (
                        <label key={p.id} className="flex items-center gap-2 text-xs text-slate-700">
                          <input
                            type="checkbox"
                            checked={selectedProductIds.includes(p.id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedProductIds([...selectedProductIds, p.id]);
                              } else {
                                setSelectedProductIds(
                                  selectedProductIds.filter((id) => id !== p.id)
                                );
                              }
                            }}
                            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                          />
                          <span>{p.name}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="field-app-discounts-page-tsx-7" className="block text-xs font-medium text-slate-700 mb-1">
                      Min Purchase (₹)
                    </label>
                    <input id="field-app-discounts-page-tsx-7"
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="e.g. 500.00"
                      value={minPurchase}
                      onChange={(e) => setMinPurchase(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="field-app-discounts-page-tsx-8" className="block text-xs font-medium text-slate-700 mb-1">
                      Min Seats / Qty
                    </label>
                    <input id="field-app-discounts-page-tsx-8"
                      type="number"
                      min="1"
                      placeholder="e.g. 5"
                      value={minQty}
                      onChange={(e) => setMinQty(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="field-app-discounts-page-tsx-9" className="block text-xs font-medium text-slate-700 mb-1">
                      Valid From *
                    </label>
                    <input id="field-app-discounts-page-tsx-9"
                      type="date"
                      required
                      value={validFrom}
                      onChange={(e) => setValidFrom(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="field-app-discounts-page-tsx-10" className="block text-xs font-medium text-slate-700 mb-1">
                      Valid To *
                    </label>
                    <input id="field-app-discounts-page-tsx-10"
                      type="date"
                      required
                      value={validTo}
                      onChange={(e) => setValidTo(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
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
                  {createLoading ? "Saving..." : "Create Rule"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}

      {/* Modal: New Revision */}
      {revisionModalRule && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setRevisionModalRule(null)} busy={revLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-slate-900">
              Publish New Revision for {revisionModalRule.name}
            </h2>

            {revError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {revError}
              </div>
            )}

            <form onSubmit={handleCreateRevision} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="field-app-discounts-page-tsx-11" className="block text-xs font-medium text-slate-700 mb-1">Scope</label>
                  <select id="field-app-discounts-page-tsx-11"
                    aria-label="Revision scope"
                  value={revScope}
                    onChange={(e) => setRevScope(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
                  >
                    <option value="SUBSCRIPTION">Whole Subscription</option>
                    <option value="PRODUCT">Specific Products</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="field-app-discounts-page-tsx-12" className="block text-xs font-medium text-slate-700 mb-1">Type</label>
                  <select aria-label="Revision discount type" id="field-app-discounts-page-tsx-12"
                    value={revType}
                    onChange={(e) => setRevType(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
                  >
                    <option value="PERCENT">PERCENT (%)</option>
                    <option value="FIXED">FIXED (₹)</option>
                  </select>
                </div>
              </div>

              {revType === "PERCENT" ? (
                <div>
                  <label htmlFor="field-app-discounts-page-tsx-13" className="block text-xs font-medium text-slate-700 mb-1">
                    Percentage Rate (%) *
                  </label>
                  <input id="field-app-discounts-page-tsx-13"
                    type="number"
                    step="0.0001"
                    min="0.01"
                    max="100"
                    required
                    value={revRate}
                    onChange={(e) => setRevRate(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>
              ) : (
                <div>
                  <label htmlFor="field-app-discounts-page-tsx-14" className="block text-xs font-medium text-slate-700 mb-1">
                    Fixed Amount (₹) *
                  </label>
                  <input id="field-app-discounts-page-tsx-14"
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={revAmount}
                    onChange={(e) => setRevAmount(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>
              )}

              {revScope === "PRODUCT" && (
                <div>
                  <CatalogChoiceSearch label="Find revision product" source={productChoices} />
                  <p className="block text-xs font-medium text-slate-700 mb-1">
                    Eligible Products *
                  </p>
                  <div className="max-h-28 overflow-y-auto border border-slate-200 rounded-md p-2 space-y-1 bg-white">
                    {products.map((p) => (
                      <label key={p.id} className="flex items-center gap-2 text-xs text-slate-700">
                        <input
                          type="checkbox"
                          checked={revProductIds.includes(p.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setRevProductIds([...revProductIds, p.id]);
                            } else {
                              setRevProductIds(revProductIds.filter((id) => id !== p.id));
                            }
                          }}
                          className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span>{p.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="field-app-discounts-page-tsx-15" className="block text-xs font-medium text-slate-700 mb-1">
                    Min Purchase (₹)
                  </label>
                  <input id="field-app-discounts-page-tsx-15"
                    type="number"
                    step="0.01"
                    min="0"
                    value={revMinPurchase}
                    onChange={(e) => setRevMinPurchase(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label htmlFor="field-app-discounts-page-tsx-16" className="block text-xs font-medium text-slate-700 mb-1">
                    Min Seats / Qty
                  </label>
                  <input id="field-app-discounts-page-tsx-16"
                    type="number"
                    min="1"
                    value={revMinQty}
                    onChange={(e) => setRevMinQty(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="field-app-discounts-page-tsx-17" className="block text-xs font-medium text-slate-700 mb-1">
                    Valid From *
                  </label>
                  <input id="field-app-discounts-page-tsx-17"
                    type="date"
                    required
                    value={revValidFrom}
                    onChange={(e) => setRevValidFrom(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label htmlFor="field-app-discounts-page-tsx-18" className="block text-xs font-medium text-slate-700 mb-1">
                    Valid To *
                  </label>
                  <input id="field-app-discounts-page-tsx-18"
                    type="date"
                    required
                    value={revValidTo}
                    onChange={(e) => setRevValidTo(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  data-discard-form onClick={() => setRevisionModalRule(null)}
                  className="px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={revLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50"
                >
                  {revLoading ? "Publishing..." : "Publish Revision"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}

      {/* Modal: Deactivate Discount Rule */}
      {deactRule && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setDeactRule(null)} busy={deactLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Deactivate Discount Rule</h2>
            <p className="text-sm text-slate-600">
              Deactivate <strong>{deactRule.name}</strong> from offering new redemptions.
            </p>

            <div className="space-y-3">
              <div>
                <label htmlFor="field-app-discounts-page-tsx-19" className="block text-xs font-medium text-slate-700 mb-1">
                  Disabled From Date *
                </label>
                <input id="field-app-discounts-page-tsx-19"
                  type="date"
                  required
                  value={deactDate}
                  onChange={(e) => setDeactDate(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="field-app-discounts-page-tsx-20" className="block text-xs font-medium text-slate-700 mb-1">
                  Reason for Deactivation
                </label>
                <textarea id="field-app-discounts-page-tsx-20"
                  rows={2}
                  placeholder="e.g. Promotion ended"
                  value={deactReason}
                  onChange={(e) => setDeactReason(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                data-discard-form onClick={() => setDeactRule(null)}
                className="px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeactivate}
                disabled={deactLoading}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50"
              >
                {deactLoading ? "Deactivating..." : "Deactivate Rule"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
