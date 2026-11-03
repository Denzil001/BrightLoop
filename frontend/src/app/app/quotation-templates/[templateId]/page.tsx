"use client";
import { formatAdjustment } from "@/lib/decimal";
import { formatCurrency } from "@/lib/utils";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  FileText,
  Save,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ShieldAlert,
  Calculator,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import CatalogChoiceSearch from "@/components/CatalogChoiceSearch";
import { useCatalogChoices } from "@/lib/useCatalogChoices";
import { useDialogChanges, useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient, ApiError } from "@/lib/api";

interface TemplateLine {
  id?: string;
  ordinal: number;
  product_id: string;
  variant_id?: string | null;
  quantity: number;
  line_kind: string; // 'INCLUDED' | 'ADDON'
  product_name?: string;
  variant_name?: string;
}

interface TemplateDetail {
  id: string;
  name: string;
  description?: string;
  plan_id: string;
  plan_name?: string;
  validity_days: number;
  active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  lines: TemplateLine[];
}

interface PlanItem {
  id: string;
  name: string;
  base_fee: string;
  minimum_seats: number;
}

interface ProductItem {
  id: string;
  name: string;
  sales_price: string;
  variants: Array<{ id: string; name: string; price_adjustment: string }>;
}

interface PricingPreviewResult {
  plan_name: string;
  base_fee: string;
  minimum_seats: number;
  seat_quantity: number;
  subtotal: string;
  total_discount: string;
  taxable_amount: string;
  total_tax: string;
  total: string;
  lines: Array<{
    ordinal: number;
    line_kind: string;
    description: string;
    quantity: number;
    unit_price: string;
    subtotal: string;
    discount_amount: string;
    tax_amount: string;
    total: string;
  }>;
}

export default function QuotationTemplateEditorPage() {
  const { user } = useAuth();
  const params = useParams();
  const templateId = params?.templateId as string;

  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form fields
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [planId, setPlanId] = useState("");
  const [validityDays, setValidityDays] = useState(30);
  const [active, setActive] = useState(false);
  const [lines, setLines] = useState<TemplateLine[]>([]);

  // Add Line Modal
  const [lineModalOpen, setLineModalOpen] = useState(false);
  const [selectedProdId, setSelectedProdId] = useState("");
  const [selectedVarId, setSelectedVarId] = useState("");
  const [lineQty, setLineQty] = useState(1);
  const [lineKind, setLineKind] = useState("ADDON");

  // Save states
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Pricing preview
  const [pricingPreview, setPricingPreview] = useState<PricingPreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const planChoices = useCatalogChoices<PlanItem>("/plans", [planId]);
  const productChoices = useCatalogChoices<ProductItem>("/products", [selectedProdId, ...lines.map(line => line.product_id)]);
  const plans = planChoices.items;
  const products = productChoices.items;

  const lineDirty = useDialogChanges(lineModalOpen, [selectedProdId, selectedVarId, lineQty, lineKind]);
  const templateDirty = Boolean(template && JSON.stringify([name, description, planId, validityDays, active, lines.map(line => [line.product_id, line.variant_id || null, line.quantity, line.line_kind])]) !== JSON.stringify([template.name, template.description || "", template.plan_id, template.validity_days, template.active, template.lines.map(line => [line.product_id, line.variant_id || null, line.quantity, line.line_kind])]));
  useUnsavedChanges(templateDirty || lineDirty);

  const fetchData = useCallback(async () => {
    if (!templateId) return;
    setLoading(true);
    setError(null);
    try {
      const tplRes = await apiClient<TemplateDetail>(`/quotation-templates/${templateId}`);

      setTemplate(tplRes);
      setName(tplRes.name);
      setDescription(tplRes.description || "");
      setPlanId(tplRes.plan_id);
      setValidityDays(tplRes.validity_days);
      setActive(tplRes.active);
      setLines(tplRes.lines || []);

    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load quotation template.");
    } finally {
      setLoading(false);
    }
  }, [templateId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (user && user.role !== "ADMIN") {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <ShieldAlert className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Access Restricted</h2>
        <p className="text-sm text-slate-600 mt-1">
          Quotation template editing is reserved exclusively for System Administrators.
        </p>
      </div>
    );
  }

  const handleSaveTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(false);

    if (active && lines.length === 0) {
      setSaveError("An active template must have at least one line item configured.");
      return;
    }

    setSaveLoading(true);
    try {
      const linesPayload = lines.map((l, idx) => ({
        ordinal: idx + 1,
        product_id: l.product_id,
        variant_id: l.variant_id || null,
        quantity: l.quantity,
        line_kind: l.line_kind,
      }));

      await apiClient(`/quotation-templates/${templateId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          plan_id: planId,
          validity_days: validityDays,
          active,
          lines: linesPayload,
        }),
      });

      setSaveSuccess(true);
      fetchData();
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to save quotation template.");
    } finally {
      setSaveLoading(false);
    }
  };

  const handleAddLine = () => {
    if (!selectedProdId) return;
    const prod = products.find((p) => p.id === selectedProdId);
    const variant = prod?.variants.find((v) => v.id === selectedVarId);

    const newLine: TemplateLine = {
      id: crypto.randomUUID(),
      ordinal: lines.length + 1,
      product_id: selectedProdId,
      variant_id: selectedVarId || null,
      quantity: lineQty,
      line_kind: lineKind,
      product_name: prod?.name,
      variant_name: variant?.name,
    };

    setLines([...lines, newLine]);
    setLineModalOpen(false);
    setSelectedProdId("");
    setSelectedVarId("");
    setLineQty(1);
    setLineKind("ADDON");
  };

  const handleRemoveLine = (idx: number) => {
    setLines(lines.filter((_, i) => i !== idx));
  };

  const handleCalculatePreview = async () => {
    if (!planId) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const planObj = plans.find((p) => p.id === planId);
      const minSeats = planObj ? planObj.minimum_seats : 1;

      const previewLines = lines.map((l) => ({
        product_id: l.product_id,
        variant_id: l.variant_id || null,
        quantity: l.quantity,
        line_kind: l.line_kind,
      }));

      const res = await apiClient<PricingPreviewResult>("/pricing/preview", {
        method: "POST",
        body: JSON.stringify({
          plan_id: planId,
          seat_quantity: minSeats,
          lines: previewLines,
        }),
      });

      setPricingPreview(res);
    } catch (err) {
      setPreviewError(err instanceof ApiError ? err.message : "Failed to calculate pricing preview.");
    } finally {
      setPreviewLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-slate-500">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
        <p className="text-sm">Loading template editor...</p>
      </div>
    );
  }

  if (error || !template) {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <AlertCircle className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Error Loading Template</h2>
        <p className="text-sm text-slate-600 mt-1">{error || "Template not found."}</p>
        <Link
          href="/app/quotation-templates"
          className="mt-4 inline-flex items-center gap-2 text-sm text-blue-600 font-medium hover:underline"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Templates</span>
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
          href="/app/quotation-templates"
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 transition mb-3"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Quotation Templates</span>
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <FileText className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">{template.name}</h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Version {template.version} &bull; Created {new Date(template.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
          <div>
            {template.active ? (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Active Template
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                <AlertCircle className="w-3.5 h-3.5" />
                {lines.length === 0 ? "Incomplete (Needs Lines)" : "Inactive"}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Main Settings Card */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-6 space-y-6">
        <h2 className="text-base font-bold text-slate-900 border-b border-slate-100 pb-3">
          Template Parameters
        </h2>

        {saveSuccess && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded text-emerald-800 text-sm flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-700" />
            <span>Quotation template saved successfully.</span>
          </div>
        )}

        {saveError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{saveError}</span>
          </div>
        )}

        <form onSubmit={handleSaveTemplate} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="field-app-quotation-templates-templateId-page-tsx-1" className="block text-xs font-medium text-slate-700 mb-1">
                Template Name *
              </label>
              <input id="field-app-quotation-templates-templateId-page-tsx-1"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <CatalogChoiceSearch label="Find template plan" source={planChoices} />
            <div>
              <label htmlFor="field-app-quotation-templates-templateId-page-tsx-2" className="block text-xs font-medium text-slate-700 mb-1">
                Default Base Plan *
              </label>
              <select id="field-app-quotation-templates-templateId-page-tsx-2"
                required
                aria-label="Template base plan"
                  value={planId}
                onChange={(e) => setPlanId(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
              >
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({formatCurrency(p.base_fee)})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="field-app-quotation-templates-templateId-page-tsx-3" className="block text-xs font-medium text-slate-700 mb-1">
                Default Quote Validity (Days) *
              </label>
              <input id="field-app-quotation-templates-templateId-page-tsx-3"
                type="number"
                min="1"
                required
                value={validityDays}
                onChange={(e) => setValidityDays(parseInt(e.target.value, 10) || 1)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
              />
            </div>

            <div>
              <p className="block text-xs font-medium text-slate-700 mb-1">
                Status
              </p>
              <div className="flex items-center gap-2 h-10">
                <input
                  type="checkbox"
                  id="tplActive"
                  checked={active}
                  onChange={(e) => setActive(e.target.checked)}
                  disabled={lines.length === 0}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
                />
                <label
                  htmlFor="tplActive"
                  className={`text-sm font-medium ${
                    lines.length === 0 ? "text-slate-500" : "text-slate-700"
                  }`}
                >
                  Active for staff sales quotations{" "}
                  {lines.length === 0 && "(configure lines first)"}
                </label>
              </div>
            </div>
          </div>

          <div>
            <label htmlFor="field-app-quotation-templates-templateId-page-tsx-4" className="block text-xs font-medium text-slate-700 mb-1">Description</label>
            <textarea id="field-app-quotation-templates-templateId-page-tsx-4"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Template Lines Section */}
          <div className="border-t border-slate-200 pt-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Configured Line Items</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Items automatically populated when a sales representative selects this quotation template.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setLineModalOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold rounded-md transition"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Template Line</span>
              </button>
            </div>

            <div className="border border-slate-200 rounded-md overflow-hidden">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-medium">
                  <tr>
                    <th className="px-4 py-2.5">Ordinal</th>
                    <th className="px-4 py-2.5">Classification</th>
                    <th className="px-4 py-2.5">Product</th>
                    <th className="px-4 py-2.5">Variant</th>
                    <th className="px-4 py-2.5">Quantity</th>
                    <th className="px-4 py-2.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {lines.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                        No lines added yet. Add at least one line to activate this template.
                      </td>
                    </tr>
                  ) : (
                    lines.map((l, idx) => (
                      <tr key={l.id} className="hover:bg-slate-50">
                        <td className="px-4 py-2.5 font-mono text-slate-500">{idx + 1}</td>
                        <td className="px-4 py-2.5">
                          {l.line_kind === "INCLUDED" ? (
                            <span className="inline-block px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-semibold text-[10px]">
                              INCLUDED (₹0.00)
                            </span>
                          ) : (
                            <span className="inline-block px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold text-[10px]">
                              PAID ADD-ON
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 font-semibold text-slate-900">
                          {l.product_name || l.product_id}
                        </td>
                        <td className="px-4 py-2.5 text-slate-600">{l.variant_name || "—"}</td>
                        <td className="px-4 py-2.5 font-medium text-slate-900">{l.quantity}</td>
                        <td className="px-4 py-2.5 text-right">
                          <button
                            type="button"
                            onClick={() => handleRemoveLine(idx)}
                            aria-label={`Remove template line ${idx + 1}`}
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

          <div className="flex items-center justify-between pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={handleCalculatePreview}
              disabled={previewLoading || !planId}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-md transition"
            >
              <Calculator className="w-4 h-4" />
              <span>{previewLoading ? "Calculating..." : "Preview Live Pricing Estimate"}</span>
            </button>

            <button
              type="submit"
              disabled={saveLoading}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50 shadow-sm"
            >
              <Save className="w-4 h-4" />
              <span>{saveLoading ? "Saving..." : "Save Template"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Live Pricing Preview Drawer / Box */}
      {previewError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">
          {previewError}
        </div>
      )}

      {pricingPreview && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Authoritative Pricing Preview ({pricingPreview.plan_name})
              </h3>
              <p className="text-xs text-slate-500">
                Calculated on backend via Decimal pricing service with default plan seats ({pricingPreview.minimum_seats}).
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500 block">Estimated Quote Total</span>
              <span className="text-xl font-bold font-mono text-emerald-700">
                {formatCurrency(pricingPreview.total)}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-white p-3 rounded-md border border-slate-200 font-mono">
            <div>
              <span className="text-slate-500 block">Subtotal:</span>
              <span className="font-semibold text-slate-800">₹{pricingPreview.subtotal}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Discount:</span>
              <span className="font-semibold text-slate-800">-₹{pricingPreview.total_discount}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Taxable Base:</span>
              <span className="font-semibold text-slate-800">₹{pricingPreview.taxable_amount}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Total Tax:</span>
              <span className="font-semibold text-slate-800">+₹{pricingPreview.total_tax}</span>
            </div>
          </div>

          <div className="border border-slate-200 rounded-md overflow-hidden bg-white">
            <table className="min-w-full divide-y divide-slate-100 text-left text-xs">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-3 py-2">Line</th>
                  <th className="px-3 py-2">Item Description</th>
                  <th className="px-3 py-2">Qty</th>
                  <th className="px-3 py-2">Unit Price</th>
                  <th className="px-3 py-2">Subtotal</th>
                  <th className="px-3 py-2">Tax</th>
                  <th className="px-3 py-2 text-right">Line Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {pricingPreview.lines.map((l) => (
                  <tr key={l.ordinal}>
                    <td className="px-3 py-2 text-slate-500">{l.ordinal}</td>
                    <td className="px-3 py-2 font-sans font-medium text-slate-800">{l.description}</td>
                    <td className="px-3 py-2">{l.quantity}</td>
                    <td className="px-3 py-2">₹{l.unit_price}</td>
                    <td className="px-3 py-2">₹{l.subtotal}</td>
                    <td className="px-3 py-2">₹{l.tax_amount}</td>
                    <td className="px-3 py-2 text-right font-semibold text-slate-900">₹{l.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add Line Modal */}
      {lineModalOpen && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setLineModalOpen(false)} busy={false}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Add Line Item to Template</h2>

            <div className="space-y-4">
              <div>
                <label htmlFor="field-app-quotation-templates-templateId-page-tsx-5" className="block text-xs font-medium text-slate-700 mb-1">
                  Line Classification *
                </label>
                <select aria-label="Template charge kind" id="field-app-quotation-templates-templateId-page-tsx-5"
                  value={lineKind}
                  onChange={(e) => setLineKind(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold"
                >
                  <option value="ADDON">Paid Add-on Line</option>
                  <option value="INCLUDED">Included Entitlement (₹0.00)</option>
                </select>
              </div>

              <div>
                <p className="block text-xs font-medium text-slate-700 mb-1">Product *</p>
                <CatalogChoiceSearch label="Find template product" source={productChoices} />
                <select
                  aria-label="Template product"
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
                      {p.name} ({formatCurrency(p.sales_price)})
                    </option>
                  ))}
                </select>
              </div>

              {selectedProdObj && selectedProdObj.variants.length > 0 && (
                <div>
                  <label htmlFor="field-app-quotation-templates-templateId-page-tsx-6" className="block text-xs font-medium text-slate-700 mb-1">
                    Variant (Optional)
                  </label>
                  <select id="field-app-quotation-templates-templateId-page-tsx-6"
                    aria-label="Template variant"
                  value={selectedVarId}
                    onChange={(e) => setSelectedVarId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Base product</option>
                    {selectedProdObj.variants.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} ({formatAdjustment(v.price_adjustment)})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label htmlFor="field-app-quotation-templates-templateId-page-tsx-7" className="block text-xs font-medium text-slate-700 mb-1">Quantity *</label>
                <input id="field-app-quotation-templates-templateId-page-tsx-7"
                  type="number"
                  min="1"
                  required
                  value={lineQty}
                  onChange={(e) => setLineQty(parseInt(e.target.value, 10) || 1)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  data-discard-form onClick={() => setLineModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleAddLine}
                  disabled={!selectedProdId}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50"
                >
                  Add Line
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
