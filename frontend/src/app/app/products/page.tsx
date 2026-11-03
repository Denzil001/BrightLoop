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
  Filter,
  RefreshCw,
  Package,
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

interface ProductVariant {
  id: string;
  name: string;
  price_adjustment: string;
  active: boolean;
  effective_sales_price?: string;
}

interface ProductItem {
  id: string;
  name: string;
  type: string;
  sales_price: string;
  cost_price?: string;
  notes?: string;
  active: boolean;
  version: number;
  created_at: string;
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

interface PaginatedProducts {
  items: ProductItem[];
  page: number;
  page_size: number;
  total: number;
}

export default function ProductsListPage() {
  const requestSequence = useRef(0);
  const { user } = useAuth();

  const [products, setProducts] = useState<ProductItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useQueryState("page", 1);
  const [pageSize] = useState(15);
  const [search, setSearch] = useQueryState("search", "");
  const [activeFilter, setActiveFilter] = useQueryState<string>("active", "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create product modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [type, setType] = useState("SERVICE");
  const [salesPrice, setSalesPrice] = useState("0.00");
  const [costPrice, setCostPrice] = useState("0.00");
  const [notes, setNotes] = useState("");
  const [selectedTaxIds, setSelectedTaxIds] = useState<string[]>([]);

  // Archive modal
  const [archiveTarget, setArchiveTarget] = useState<ProductItem | null>(null);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const taxChoices = useCatalogChoices<TaxRuleItem>("/taxes", selectedTaxIds, createModalOpen);
  const taxes = taxChoices.items;

  const dialogDirty0 = useDialogChanges(createModalOpen, [name, type, salesPrice, costPrice, notes, selectedTaxIds]);
  useUnsavedChanges(dialogDirty0);

  const fetchProducts = useCallback(async () => {const request = ++requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", page.toString());
      params.set("page_size", pageSize.toString());
      if (search.trim()) params.set("search", search.trim());
      if (activeFilter === "active") params.set("active", "true");
      if (activeFilter === "inactive") params.set("active", "false");

      const res = await apiClient<PaginatedProducts>(`/products?${params.toString()}`); if (request !== requestSequence.current) return;
      setProducts(res.items);
      setTotal(res.total);
    } catch (err) {if (request !== requestSequence.current) return;
      setError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to load products.");
    } finally {
      if (request === requestSequence.current) setLoading(false);
    }
  }, [page, pageSize, search, activeFilter]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

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

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    const sPrice = parseFloat(salesPrice);
    const cPrice = parseFloat(costPrice);
    if (Number.isNaN(sPrice) || sPrice < 0) {
      setCreateError("Sales price must be a valid non-negative number.");
      return;
    }
    if (Number.isNaN(cPrice) || cPrice < 0) {
      setCreateError("Cost price must be a valid non-negative number.");
      return;
    }

    setCreateLoading(true);
    try {
      await apiClient("/products", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          type: type.trim(),
          sales_price: decimalInput(salesPrice, {label: "Sales price"}),
          cost_price: decimalInput(costPrice, {label: "Cost price"}),
          notes: notes.trim() || null,
          active: true,
          tax_rule_ids: selectedTaxIds,
        }),
      });

      setCreateModalOpen(false);
      setName("");
      setSalesPrice("0.00");
      setCostPrice("0.00");
      setNotes("");
      setSelectedTaxIds([]);
      fetchProducts();
    } catch (err) {
      setCreateError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to create product.");
    } finally {
      setCreateLoading(false);
    }
  };

  const handleArchive = async () => {
    if (!archiveTarget) return;
    setArchiveLoading(true);
    setArchiveError(null);
    try {
      await apiClient(`/products/${archiveTarget.id}/archive`, {
        method: "POST",
      });
      setArchiveTarget(null);
      fetchProducts();
    } catch (err) {
      setArchiveError((err instanceof ApiError || err instanceof DecimalInputError) ? err.message : "Failed to archive product.");
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
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Products Catalog</h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage standalone products, add-on components, and pricing adjustments.
          </p>
        </div>
        <button type="button"
          onClick={() => setCreateModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          <span>New Product</span>
        </button>
      </div>
      <CollectionSort fields={[["name", "Name"], ["sales_price", "Sales price"], ["type", "Type"], ["created_at", "Created"]]} initial="name" descending={false} onChange={() => {if (page === 1) fetchProducts(); else setPage(1);}} />

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex-1 w-full md:w-auto relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search products by name or type..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Filter className="w-4 h-4" />
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
          </div>

          <button type="button"
            onClick={() => fetchProducts()}
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
            onClick={() => fetchProducts()}
            className="text-xs font-semibold underline hover:text-red-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* Products Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <ScrollableRegion className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-slate-600 font-medium">
              <tr>
                <th className="px-6 py-3">Product Name</th>
                <th className="px-6 py-3">Type</th>
                <th className="px-6 py-3">Sales Price</th>
                <th className="px-6 py-3">Cost Price</th>
                <th className="px-6 py-3">Variants</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && products.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    Loading products catalog...
                  </td>
                </tr>
              ) : products.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <Package className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-slate-600 font-medium">No products found</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {search || activeFilter
                        ? "Try clearing filters to find products."
                        : "Create your first product to get started."}
                    </p>
                  </td>
                </tr>
              ) : (
                products.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/75 transition">
                    <td className="px-6 py-4 font-semibold text-slate-900">
                      <Link
                        href={`/app/products/${p.id}`}
                        className="hover:text-blue-600 hover:underline flex items-center gap-2"
                      >
                        <Package className="w-4 h-4 text-blue-500 shrink-0" />
                        <span>{p.name}</span>
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      <span className="inline-block px-2 py-0.5 rounded bg-slate-100 text-xs font-mono font-medium text-slate-700">
                        {p.type}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-900">
                      {formatCurrency(p.sales_price)}
                    </td>
                    <td className="px-6 py-4 text-slate-500">
                      {p.cost_price ? formatCurrency(p.cost_price) : "—"}
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium">
                        <Layers className="w-3 h-3" />
                        {p.variants.length} variant{p.variants.length === 1 ? "" : "s"}
                      </span>
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
                        href={`/app/products/${p.id}`}
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
              {Math.min(page * pageSize, total)} of {total} products
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

      {/* New Product Modal */}
      {createModalOpen && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setCreateModalOpen(false)} busy={createLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Create New Product</h2>

            {createError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateProduct} className="space-y-4">
              <div>
                <label htmlFor="field-app-products-page-tsx-1" className="block text-xs font-medium text-slate-700 mb-1">
                  Product Name *
                </label>
                <input id="field-app-products-page-tsx-1"
                  type="text"
                  required
                  placeholder="e.g. Cloud Server Hosting"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="field-app-products-page-tsx-2" className="block text-xs font-medium text-slate-700 mb-1">
                  Product Type *
                </label>
                <input id="field-app-products-page-tsx-2"
                  type="text"
                  required
                  placeholder="e.g. INFRASTRUCTURE, ADDON, SERVICE"
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="field-app-products-page-tsx-3" className="block text-xs font-medium text-slate-700 mb-1">
                    Sales Price (₹) *
                  </label>
                  <input id="field-app-products-page-tsx-3"
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
                  <label htmlFor="field-app-products-page-tsx-4" className="block text-xs font-medium text-slate-700 mb-1">
                    Cost Price (₹) *
                  </label>
                  <input id="field-app-products-page-tsx-4"
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
                    Applicable Tax Rules
                  </p>
                  <div className="max-h-32 overflow-y-auto border border-slate-200 rounded-md p-2 space-y-1">
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
                <label htmlFor="field-app-products-page-tsx-5" className="block text-xs font-medium text-slate-700 mb-1">
                  Internal Notes (Admin Only)
                </label>
                <textarea id="field-app-products-page-tsx-5"
                  rows={2}
                  placeholder="Notes for internal staffing/operations..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
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
                  {createLoading ? "Saving..." : "Create Product"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}

      {/* Archive Confirmation Modal */}
      {archiveTarget && (
        <Modal className="fixed inset-0 z-50 flex items-center justify-center p-4" onDismiss={() => setArchiveTarget(null)} busy={archiveLoading}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Archive Product</h2>
            <p className="text-sm text-slate-600">
              Are you sure you want to archive <strong>{archiveTarget.name}</strong>?
            </p>
            <div className="p-3 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
              Archiving removes this product from new quotes and plan bundles. Historical
              subscriptions and agreed invoices referencing this product remain intact.
            </div>

            {archiveError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {archiveError}
              </div>
            )}

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
