"use client";
import { decimalInput, DecimalInputError, decimalKey } from "@/lib/decimal";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Layers,
  Save,
  Archive,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import CatalogChoiceSearch from "@/components/CatalogChoiceSearch";
import { useCatalogChoices } from "@/lib/useCatalogChoices";
import { useDialogChanges, useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient, ApiError } from "@/lib/api";

interface PlanItemIncluded {
  id?: string;
  ordinal: number;
  product_id: string;
  variant_id?: string | null;
  included_quantity: number;
  product_name?: string;
  variant_name?: string;
}

interface PlanDetail {
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
  created_at: string;
  updated_at: string;
  items: PlanItemIncluded[];
  tax_rule_ids: string[];
}

interface ProductItem {
  id: string;
  name: string;
  active: boolean;
  variants: Array<{ id: string; name: string; active: boolean }>;
}

interface TaxRuleItem {
  id: string;
  name: string;
  rate: string;
}

export default function PlanDetailPage() {
  const { user } = useAuth();
  const params = useParams();
  const planId = params?.planId as string;

  const [plan, setPlan] = useState<PlanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form fields
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseFee, setBaseFee] = useState("1000.00");
  const [minSeats, setMinSeats] = useState(5);
  const [extraSeatPrice, setExtraSeatPrice] = useState("100.00");
  const [interval, setInterval] = useState("MONTHLY");
  const [paymentTerms, setPaymentTerms] = useState(15);
  const [availFrom, setAvailFrom] = useState("");
  const [availTo, setAvailTo] = useState("");
  const [active, setActive] = useState(true);
  const [selectedTaxIds, setSelectedTaxIds] = useState<string[]>([]);

  // Policy toggles
  const [allowPause, setAllowPause] = useState(true);
  const [allowResume, setAllowResume] = useState(true);
  const [allowRenewal, setAllowRenewal] = useState(true);
  const [allowEarlyClosure, setAllowEarlyClosure] = useState(true);
  const [autoClose, setAutoClose] = useState(true);

  // Included Items state
  const [includedItems, setIncludedItems] = useState<PlanItemIncluded[]>([]);
  const [addItemModalOpen, setAddItemModalOpen] = useState(false);
  const [selectedProdId, setSelectedProdId] = useState("");
  const [selectedVarId, setSelectedVarId] = useState("");
  const [incQty, setIncQty] = useState(1);

  const [saveLoading, setSaveLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const productChoices = useCatalogChoices<ProductItem>("/products", [selectedProdId, ...includedItems.map(item => item.product_id)]);
  const taxChoices = useCatalogChoices<TaxRuleItem>("/taxes", selectedTaxIds);
  const products = productChoices.items;
  const taxes = taxChoices.items;

  const bundleDirty = useDialogChanges(addItemModalOpen, [selectedProdId, selectedVarId, incQty]);
  const planDirty = Boolean(plan && JSON.stringify([name, description, decimalKey(baseFee), minSeats, decimalKey(extraSeatPrice), interval, paymentTerms, availFrom, availTo, active, [...selectedTaxIds].sort(), allowPause, allowResume, allowRenewal, allowEarlyClosure, autoClose, includedItems.map(item => [item.product_id, item.variant_id || null, item.included_quantity])]) !== JSON.stringify([plan.name, plan.description || "", decimalKey(plan.base_fee), plan.minimum_seats, decimalKey(plan.extra_seat_unit_price), plan.interval, plan.payment_term_days, plan.available_from || "", plan.available_to || "", plan.active, [...(plan.tax_rule_ids || [])].sort(), plan.allow_pause, plan.allow_resume, plan.allow_renewal, plan.allow_early_closure, plan.auto_close_on_expiry, (plan.items || []).map(item => [item.product_id, item.variant_id || null, item.included_quantity])]));
  useUnsavedChanges(planDirty || bundleDirty);

  const fetchData = useCallback(async () => {
    if (!planId) return;
    setLoading(true);
    setError(null);
    try {
      const planRes = await apiClient<PlanDetail>(`/plans/${planId}`);

      setPlan(planRes);
      setName(planRes.name);
      setDescription(planRes.description || "");
      setBaseFee(planRes.base_fee);
      setMinSeats(planRes.minimum_seats);
      setExtraSeatPrice(planRes.extra_seat_unit_price);
      setInterval(planRes.interval);
      setPaymentTerms(planRes.payment_term_days);
      setAvailFrom(planRes.available_from || "");
      setAvailTo(planRes.available_to || "");
      setActive(planRes.active);
      setSelectedTaxIds(planRes.tax_rule_ids || []);
      setAllowPause(planRes.allow_pause);
      setAllowResume(planRes.allow_resume);
      setAllowRenewal(planRes.allow_renewal);
      setAllowEarlyClosure(planRes.allow_early_closure);
      setAutoClose(planRes.auto_close_on_expiry);
      setIncludedItems(planRes.items || []);

    } catch (err) {
      setError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to load plan details.");
    } finally {
      setLoading(false);
    }
  }, [planId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  const handleSavePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(false);

    const bFee = parseFloat(baseFee);
    const ePrice = parseFloat(extraSeatPrice);
    if (Number.isNaN(bFee) || bFee < 0) {
      setSaveError("Base fee must be a valid non-negative number.");
      return;
    }
    if (minSeats < 1) {
      setSaveError("Minimum seats must be at least 1.");
      return;
    }
    if (Number.isNaN(ePrice) || ePrice < 0) {
      setSaveError("Extra seat price must be a valid non-negative number.");
      return;
    }

    setSaveLoading(true);
    try {
      const itemsPayload = includedItems.map((item, idx) => ({
        ordinal: idx + 1,
        product_id: item.product_id,
        variant_id: item.variant_id || null,
        included_quantity: item.included_quantity,
      }));

      await apiClient(`/plans/${planId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          base_fee: decimalInput(baseFee, {label: "Base fee"}),
          minimum_seats: minSeats,
          extra_seat_unit_price: decimalInput(extraSeatPrice, {label: "Extra seat price"}),
          interval,
          payment_term_days: paymentTerms,
          available_from: availFrom || null,
          available_to: availTo || null,
          allow_pause: allowPause,
          allow_resume: allowResume,
          allow_renewal: allowRenewal,
          allow_early_closure: allowEarlyClosure,
          auto_close_on_expiry: autoClose,
          active,
          items: itemsPayload,
          tax_rule_ids: selectedTaxIds,
        }),
      });

      setSaveSuccess(true);
      fetchData();
    } catch (err) {
      setSaveError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to save plan.");
    } finally {
      setSaveLoading(false);
    }
  };

  const handleAddIncludedItem = () => {
    if (!selectedProdId) return;
    const prod = products.find((p) => p.id === selectedProdId);
    const variant = prod?.variants.find((v) => v.id === selectedVarId);

    const newItem: PlanItemIncluded = {
      id: crypto.randomUUID(),
      ordinal: includedItems.length + 1,
      product_id: selectedProdId,
      variant_id: selectedVarId || null,
      included_quantity: incQty,
      product_name: prod?.name,
      variant_name: variant?.name,
    };

    setIncludedItems([...includedItems, newItem]);
    setAddItemModalOpen(false);
    setSelectedProdId("");
    setSelectedVarId("");
    setIncQty(1);
  };

  const handleRemoveIncludedItem = (index: number) => {
    setIncludedItems(includedItems.filter((_, i) => i !== index));
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-slate-500">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
        <p className="text-sm">Loading plan details...</p>
      </div>
    );
  }

  if (error || !plan) {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <AlertCircle className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Error Loading Plan</h2>
        <p className="text-sm text-slate-600 mt-1">{error || "Plan not found."}</p>
        <Link
          href="/app/plans"
          className="mt-4 inline-flex items-center gap-2 text-sm text-blue-600 font-medium hover:underline"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Plans</span>
        </Link>
      </div>
    );
  }

  const selectedProdObj = products.find((p) => p.id === selectedProdId);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link
          href="/app/plans"
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 transition mb-3"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Plans</span>
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Layers className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">{plan.name}</h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Version {plan.version} &bull; {plan.interval} billing &bull; Created{" "}
                {new Date(plan.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
          <div>
            {plan.active ? (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Active Plan
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                <Archive className="w-3.5 h-3.5" />
                Archived
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Main Form */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-6 space-y-6">
        <h2 className="text-base font-bold text-slate-900 border-b border-slate-100 pb-3">
          Plan Configuration
        </h2>

        {saveSuccess && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded text-emerald-800 text-sm flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-700" />
            <span>Plan configuration updated successfully.</span>
          </div>
        )}

        {saveError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{saveError}</span>
          </div>
        )}

        <form onSubmit={handleSavePlan} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="field-app-plans-planId-page-tsx-1" className="block text-xs font-medium text-slate-700 mb-1">Plan Name</label>
              <input id="field-app-plans-planId-page-tsx-1"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="field-app-plans-planId-page-tsx-2" className="block text-xs font-medium text-slate-700 mb-1">Billing Interval</label>
              <select aria-label="Billing interval" id="field-app-plans-planId-page-tsx-2"
                value={interval}
                onChange={(e) => setInterval(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
              >
                <option value="DAILY">DAILY</option>
                <option value="WEEKLY">WEEKLY</option>
                <option value="MONTHLY">MONTHLY</option>
                <option value="YEARLY">YEARLY</option>
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="field-app-plans-planId-page-tsx-3" className="block text-xs font-medium text-slate-700 mb-1">Description</label>
            <textarea id="field-app-plans-planId-page-tsx-3"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label htmlFor="field-app-plans-planId-page-tsx-4" className="block text-xs font-medium text-slate-700 mb-1">
                Base Fee (₹)
              </label>
              <input id="field-app-plans-planId-page-tsx-4"
                type="number"
                step="0.01"
                min="0"
                required
                value={baseFee}
                onChange={(e) => setBaseFee(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
              />
            </div>
            <div>
              <label htmlFor="field-app-plans-planId-page-tsx-5" className="block text-xs font-medium text-slate-700 mb-1">
                Included Minimum Seats
              </label>
              <input id="field-app-plans-planId-page-tsx-5"
                type="number"
                min="1"
                required
                value={minSeats}
                onChange={(e) => setMinSeats(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="field-app-plans-planId-page-tsx-6" className="block text-xs font-medium text-slate-700 mb-1">
                Excess Seat Unit Price (₹)
              </label>
              <input id="field-app-plans-planId-page-tsx-6"
                type="number"
                step="0.01"
                min="0"
                required
                value={extraSeatPrice}
                onChange={(e) => setExtraSeatPrice(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label htmlFor="field-app-plans-planId-page-tsx-7" className="block text-xs font-medium text-slate-700 mb-1">
                Payment Terms (Days)
              </label>
              <input id="field-app-plans-planId-page-tsx-7"
                type="number"
                min="0"
                required
                value={paymentTerms}
                onChange={(e) => setPaymentTerms(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="field-app-plans-planId-page-tsx-8" className="block text-xs font-medium text-slate-700 mb-1">
                Available From
              </label>
              <input id="field-app-plans-planId-page-tsx-8"
                type="date"
                value={availFrom}
                onChange={(e) => setAvailFrom(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="field-app-plans-planId-page-tsx-9" className="block text-xs font-medium text-slate-700 mb-1">
                Available To
              </label>
              <input id="field-app-plans-planId-page-tsx-9"
                type="date"
                value={availTo}
                onChange={(e) => setAvailTo(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Governance switches */}
          <div className="border border-slate-200 rounded-md p-4 space-y-3 bg-slate-50/50">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Subscription Lifecycle Governance Policy
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
              <label className="flex items-center gap-2 text-slate-700">
                <input
                  type="checkbox"
                  checked={allowPause}
                  onChange={(e) => setAllowPause(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Allow Term Pause</span>
              </label>
              <label className="flex items-center gap-2 text-slate-700">
                <input
                  type="checkbox"
                  checked={allowResume}
                  onChange={(e) => setAllowResume(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Allow Term Resume</span>
              </label>
              <label className="flex items-center gap-2 text-slate-700">
                <input
                  type="checkbox"
                  checked={allowRenewal}
                  onChange={(e) => setAllowRenewal(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Allow Explicit Renewal</span>
              </label>
              <label className="flex items-center gap-2 text-slate-700">
                <input
                  type="checkbox"
                  checked={allowEarlyClosure}
                  onChange={(e) => setAllowEarlyClosure(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Allow Early Closure</span>
              </label>
              <label className="flex items-center gap-2 text-slate-700">
                <input
                  type="checkbox"
                  checked={autoClose}
                  onChange={(e) => setAutoClose(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Auto-Close on Expiry</span>
              </label>
            </div>
          </div>

          {/* Tax Rules */}
          <CatalogChoiceSearch label="Find tax rule" source={taxChoices} />
          {taxes.length > 0 && (
            <div>
              <p className="block text-xs font-medium text-slate-700 mb-1">
                Plan-Level Tax Rules
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 border border-slate-200 rounded-md p-3">
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

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="planActive"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="planActive" className="text-sm font-medium text-slate-700">
              Active in catalog
            </label>
          </div>

          {/* Included Items Section */}
          <div className="border-t border-slate-200 pt-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Included Product Entitlements (Zero Incremental Charge)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Products bundled with this plan fee. These represent entitlements and never increase recurring totals.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setAddItemModalOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold rounded-md transition"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Included Product</span>
              </button>
            </div>

            <div className="border border-slate-200 rounded-md overflow-hidden">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-medium">
                  <tr>
                    <th className="px-4 py-2">Ordinal</th>
                    <th className="px-4 py-2">Product</th>
                    <th className="px-4 py-2">Variant</th>
                    <th className="px-4 py-2">Included Quantity</th>
                    <th className="px-4 py-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {includedItems.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                        No product lines bundled into this plan.
                      </td>
                    </tr>
                  ) : (
                    includedItems.map((item, idx) => (
                      <tr key={item.id} className="hover:bg-slate-50">
                        <td className="px-4 py-2.5 font-mono text-slate-500">{idx + 1}</td>
                        <td className="px-4 py-2.5 font-semibold text-slate-900">
                          {item.product_name || item.product_id}
                        </td>
                        <td className="px-4 py-2.5 text-slate-600">
                          {item.variant_name || "—"}
                        </td>
                        <td className="px-4 py-2.5 font-medium text-slate-900">
                          {item.included_quantity} unit{item.included_quantity === 1 ? "" : "s"}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          <button
                            type="button"
                            onClick={() => handleRemoveIncludedItem(idx)}
                            aria-label={`Remove included line ${idx + 1}`}
                            className="text-rose-600 hover:text-rose-800 p-1"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex justify-end pt-4 border-t border-slate-100">
            <button
              type="submit"
              disabled={saveLoading}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50 shadow-sm"
            >
              <Save className="w-4 h-4" />
              <span>{saveLoading ? "Saving..." : "Save Plan Configuration"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Add Included Product Modal */}
      {addItemModalOpen && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setAddItemModalOpen(false)} busy={false}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Add Included Product Bundle</h2>
            <CatalogChoiceSearch label="Find bundle product" source={productChoices} />

            <div className="space-y-4">
              <div>
                <label htmlFor="field-app-plans-planId-page-tsx-10" className="block text-xs font-medium text-slate-700 mb-1">Product *</label>
                <select id="field-app-plans-planId-page-tsx-10"
                  aria-label="Bundle product"
                  value={selectedProdId}
                  onChange={(e) => {
                    setSelectedProdId(e.target.value);
                    setSelectedVarId("");
                  }}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select a product...</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              {selectedProdObj && selectedProdObj.variants.length > 0 && (
                <div>
                  <label htmlFor="field-app-plans-planId-page-tsx-11" className="block text-xs font-medium text-slate-700 mb-1">
                    Variant (Optional)
                  </label>
                  <select id="field-app-plans-planId-page-tsx-11"
                    aria-label="Bundle variant"
                  value={selectedVarId}
                    onChange={(e) => setSelectedVarId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Base product</option>
                    {selectedProdObj.variants.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label htmlFor="field-app-plans-planId-page-tsx-12" className="block text-xs font-medium text-slate-700 mb-1">
                  Included Quantity *
                </label>
                <input id="field-app-plans-planId-page-tsx-12"
                  type="number"
                  min="1"
                  required
                  value={incQty}
                  onChange={(e) => setIncQty(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  data-discard-form onClick={() => setAddItemModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleAddIncludedItem}
                  disabled={!selectedProdId}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50"
                >
                  Add to Plan
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
