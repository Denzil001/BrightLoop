"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { formatCurrency } from "@/lib/utils";
import { decimalInput, DecimalInputError, decimalKey, addMoney, formatAdjustment } from "@/lib/decimal";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Package,
  Layers,
  Plus,
  Save,
  Archive,
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

interface ProductVariant {
  id: string;
  product_id: string;
  name: string;
  price_adjustment: string;
  active: boolean;
  effective_sales_price?: string;
}

interface ProductDetail {
  id: string;
  name: string;
  type: string;
  sales_price: string;
  cost_price?: string;
  notes?: string;
  active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  variants: ProductVariant[];
  tax_rule_ids: string[];
}

interface TaxRuleItem {
  id: string;
  name: string;
  classification: string;
  rate: string;
  active: boolean;
}

export default function ProductDetailPage() {
  const { user } = useAuth();
  const params = useParams();
  const productId = params?.productId as string;

  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Editable fields
  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [salesPrice, setSalesPrice] = useState("");
  const [costPrice, setCostPrice] = useState("");
  const [notes, setNotes] = useState("");
  const [active, setActive] = useState(true);
  const [selectedTaxIds, setSelectedTaxIds] = useState<string[]>([]);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Variant Modal state
  const [variantModalOpen, setVariantModalOpen] = useState(false);
  const [editingVariant, setEditingVariant] = useState<ProductVariant | null>(null);
  const [varName, setVarName] = useState("");
  const [varAdjustment, setVarAdjustment] = useState("0.00");
  const [varActive, setVarActive] = useState(true);
  const [varLoading, setVarLoading] = useState(false);
  const [varError, setVarError] = useState<string | null>(null);

  const taxChoices = useCatalogChoices<TaxRuleItem>("/taxes", selectedTaxIds);
  const taxes = taxChoices.items;

  const variantDirty = useDialogChanges(variantModalOpen, [varName, varAdjustment, varActive]);
  const productDirty = Boolean(product && JSON.stringify([name, type, decimalKey(salesPrice), decimalKey(costPrice), notes, active, [...selectedTaxIds].sort()]) !== JSON.stringify([product.name, product.type, decimalKey(product.sales_price), decimalKey(product.cost_price || 0), product.notes || "", product.active, [...(product.tax_rule_ids || [])].sort()]));
  useUnsavedChanges(productDirty || variantDirty);

  const fetchProduct = useCallback(async (preserveEdits = false) => {
    if (!productId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient<ProductDetail>(`/products/${productId}`);
      setProduct(res);
      if (!preserveEdits) {
      setName(res.name);
      setType(res.type);
      setSalesPrice(res.sales_price);
      setCostPrice(res.cost_price || "0.00");
      setNotes(res.notes || "");
      setActive(res.active);
      setSelectedTaxIds(res.tax_rule_ids || []);
      }
    } catch (err) {
      setError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to load product details.");
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchProduct();
  }, [fetchProduct]);

  if (user && user.role !== "ADMIN") {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <ShieldAlert className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Access Restricted</h2>
        <p className="text-sm text-slate-600 mt-1">
          Catalog management is reserved exclusively for System Administrators.
        </p>
      </div>
    );
  }

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(false);

    const sPrice = parseFloat(salesPrice);
    const cPrice = parseFloat(costPrice);
    if (Number.isNaN(sPrice) || sPrice < 0) {
      setSaveError("Sales price must be a valid non-negative number.");
      return;
    }
    if (Number.isNaN(cPrice) || cPrice < 0) {
      setSaveError("Cost price must be a valid non-negative number.");
      return;
    }

    setSaveLoading(true);
    try {
      await apiClient(`/products/${productId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          type: type.trim(),
          sales_price: decimalInput(salesPrice, {label: "Sales price"}),
          cost_price: decimalInput(costPrice, {label: "Cost price"}),
          notes: notes.trim() || null,
          active,
          tax_rule_ids: selectedTaxIds,
        }),
      });
      setSaveSuccess(true);
      fetchProduct();
    } catch (err) {
      setSaveError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to save product.");
    } finally {
      setSaveLoading(false);
    }
  };

  const openAddVariant = () => {
    setEditingVariant(null);
    setVarName("");
    setVarAdjustment("0.00");
    setVarActive(true);
    setVarError(null);
    setVariantModalOpen(true);
  };

  const openEditVariant = (v: ProductVariant) => {
    setEditingVariant(v);
    setVarName(v.name);
    setVarAdjustment(v.price_adjustment);
    setVarActive(v.active);
    setVarError(null);
    setVariantModalOpen(true);
  };

  const handleSaveVariant = async (e: React.FormEvent) => {
    e.preventDefault();
    setVarError(null);

    try {
      const effective = addMoney(product?.sales_price || "0", varAdjustment);
      if (effective.startsWith("-")) {setVarError("Effective sales price cannot be negative."); return;}
    } catch (error) {setVarError(error instanceof Error ? error.message : "Enter a valid price adjustment."); return;}

    setVarLoading(true);
    try {
      if (editingVariant) {
        await apiClient(`/products/${productId}/variants/${editingVariant.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: varName.trim(),
            price_adjustment: decimalInput(varAdjustment, {signed: true, label: "Price adjustment"}),
            active: varActive,
          }),
        });
      } else {
        await apiClient(`/products/${productId}/variants`, {
          method: "POST",
          body: JSON.stringify({
            name: varName.trim(),
            price_adjustment: decimalInput(varAdjustment, {signed: true, label: "Price adjustment"}),
            active: varActive,
          }),
        });
      }
      setVariantModalOpen(false);
      fetchProduct(true);
    } catch (err) {
      setVarError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to save variant.");
    } finally {
      setVarLoading(false);
    }
  };

  const handleArchiveVariant = async (variantId: string) => {
    try {
      await apiClient(`/products/${productId}/variants/${variantId}/archive`, {
        method: "POST",
      });
      fetchProduct(true);
    } catch (err) {
      alert((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to archive variant.");
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-slate-500">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
        <p className="text-sm">Loading product details...</p>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <AlertCircle className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Error Loading Product</h2>
        <p className="text-sm text-slate-600 mt-1">{error || "Product not found."}</p>
        <Link
          href="/app/products"
          className="mt-4 inline-flex items-center gap-2 text-sm text-blue-600 font-medium hover:underline"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Products</span>
        </Link>
      </div>
    );
  }

  const adjustment = decimalKey(varAdjustment || "0");
  let previewEffective = "0.00", previewError = "";
  try {previewEffective = addMoney(product?.sales_price || "0", varAdjustment || "0");}
  catch (error) {previewError = error instanceof Error ? error.message : "Enter a valid price adjustment.";}

  return (
    <div className="space-y-8">
      {/* Back button and title */}
      <div>
        <Link
          href="/app/products"
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 transition mb-3"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Products</span>
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Package className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                {product.name}
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Version {product.version} &bull; Created {new Date(product.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
          <div>
            {product.active ? (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Active Product
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

      {/* Main product form */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-6 space-y-6">
        <h2 className="text-base font-bold text-slate-900 border-b border-slate-100 pb-3">
          General Settings
        </h2>

        {saveSuccess && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded text-emerald-800 text-sm flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-700" />
            <span>Product details saved successfully.</span>
          </div>
        )}

        {saveError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{saveError}</span>
          </div>
        )}

        <form onSubmit={handleSaveProduct} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="field-app-products-productId-page-tsx-1" className="block text-xs font-medium text-slate-700 mb-1">Product Name</label>
              <input id="field-app-products-productId-page-tsx-1"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="field-app-products-productId-page-tsx-2" className="block text-xs font-medium text-slate-700 mb-1">Product Type</label>
              <input id="field-app-products-productId-page-tsx-2"
                type="text"
                required
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="field-app-products-productId-page-tsx-3" className="block text-xs font-medium text-slate-700 mb-1">
                Base Sales Price (₹)
              </label>
              <input id="field-app-products-productId-page-tsx-3"
                type="number"
                step="0.01"
                min="0"
                required
                value={salesPrice}
                onChange={(e) => setSalesPrice(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="field-app-products-productId-page-tsx-4" className="block text-xs font-medium text-slate-700 mb-1">
                Cost Price (₹) (Internal Admin Only)
              </label>
              <input id="field-app-products-productId-page-tsx-4"
                type="number"
                step="0.01"
                min="0"
                required
                value={costPrice}
                onChange={(e) => setCostPrice(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <CatalogChoiceSearch label="Find tax rule" source={taxChoices} />
          {taxes.length > 0 && (
            <div>
              <p className="block text-xs font-medium text-slate-700 mb-1">
                Associated Tax Rules
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

          <div>
            <label htmlFor="field-app-products-productId-page-tsx-5" className="block text-xs font-medium text-slate-700 mb-1">
              Internal Admin Notes
            </label>
            <textarea id="field-app-products-productId-page-tsx-5"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="productActive"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="productActive" className="text-sm font-medium text-slate-700">
              Active in catalog
            </label>
          </div>

          <div className="flex justify-end pt-3 border-t border-slate-100">
            <button
              type="submit"
              disabled={saveLoading}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50 shadow-sm"
            >
              <Save className="w-4 h-4" />
              <span>{saveLoading ? "Saving..." : "Save Product Details"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Product Variants Section */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-base font-bold text-slate-900">Product Variants</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Specific variations with price adjustments (e.g. +₹560.00 for High-Memory variant).
            </p>
          </div>
          <button type="button"
            onClick={openAddVariant}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold rounded-md transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Variant</span>
          </button>
        </div>

        <ScrollableRegion className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-slate-600 font-medium">
              <tr>
                <th className="px-4 py-2.5">Variant Name</th>
                <th className="px-4 py-2.5">Price Adjustment</th>
                <th className="px-4 py-2.5">Effective Sales Price</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {product.variants.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500 text-xs">
                    No variants created yet. This product sells at its base sales price.
                  </td>
                </tr>
              ) : (
                product.variants.map((v) => {
                  const adjustment = formatAdjustment(v.price_adjustment);
                  const effective = v.effective_sales_price || "0.00";
                  return (
                    <tr key={v.id} className="hover:bg-slate-50/75 transition">
                      <td className="px-4 py-3 font-semibold text-slate-900 flex items-center gap-2">
                        <Layers className="w-4 h-4 text-slate-500" />
                        <span>{v.name}</span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {adjustment}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-900 font-mono text-sm">
                        {formatCurrency(effective)}
                      </td>
                      <td className="px-4 py-3">
                        {v.active ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700">
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                            Archived
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        <button type="button"
                          onClick={() => openEditVariant(v)}
                          className="px-2 py-1 text-xs font-medium rounded border border-slate-200 text-slate-700 hover:bg-slate-100 transition"
                        >
                          Edit
                        </button>
                        {v.active && (
                          <button type="button"
                            onClick={() => handleArchiveVariant(v.id)}
                            className="px-2 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 rounded transition"
                          >
                            Archive
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
      </div>

      {/* Add / Edit Variant Modal */}
      {variantModalOpen && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setVariantModalOpen(false)} busy={varLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">
              {editingVariant ? "Edit Product Variant" : "Add Product Variant"}
            </h2>

            {varError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {varError}
              </div>
            )}

            <form onSubmit={handleSaveVariant} className="space-y-4">
              <div>
                <label htmlFor="field-app-products-productId-page-tsx-6" className="block text-xs font-medium text-slate-700 mb-1">
                  Variant Name *
                </label>
                <input id="field-app-products-productId-page-tsx-6"
                  type="text"
                  required
                  placeholder="e.g. 24/7 Dedicated SOC / High Memory"
                  value={varName}
                  onChange={(e) => setVarName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="field-app-products-productId-page-tsx-7" className="block text-xs font-medium text-slate-700 mb-1">
                  Price Adjustment ($) *
                </label>
                <input id="field-app-products-productId-page-tsx-7"
                  type="number"
                  step="0.01"
                  required
                  placeholder="e.g. 560.00"
                  value={varAdjustment}
                  onChange={(e) => setVarAdjustment(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Enter positive number to add to base price, or negative to discount.
                </p>
              </div>

              {/* Live Preview Box */}
              <div className="p-3 bg-slate-50 rounded-md border border-slate-200 text-xs space-y-1">
                <div className="flex justify-between text-slate-600">
                  <span>Saved product base price:</span>
                  <span className="font-mono">{formatCurrency(product?.sales_price)}</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Variant Adjustment:</span>
                  <span className="font-mono">
                    {adjustment.startsWith("-") ? `-${formatCurrency(adjustment.slice(1))}` : `+${formatCurrency(adjustment)}`}
                  </span>
                </div>
                <div className="flex justify-between font-bold text-slate-900 border-t border-slate-200 pt-1">
                  <span>Effective Sales Price:</span>
                  <span className={`font-mono ${(previewError || previewEffective.startsWith("-")) ? "text-red-600" : "text-emerald-700"}`}>
                    {previewError || formatCurrency(previewEffective)}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="variantActive"
                  checked={varActive}
                  onChange={(e) => setVarActive(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="variantActive" className="text-xs font-medium text-slate-700">
                  Active
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  data-discard-form onClick={() => setVariantModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={varLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition disabled:opacity-50"
                >
                  {varLoading ? "Saving..." : "Save Variant"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}
    </div>
  );
}
