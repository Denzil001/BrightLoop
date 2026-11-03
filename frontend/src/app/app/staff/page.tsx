"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback, useRef } from "react";
import { Plus, Search, Filter, RefreshCw, ChevronLeft, ChevronRight, UserCheck, UserX, ShieldAlert } from "lucide-react";
import { PasswordChecklist } from "@/components/PasswordChecklist";
import { useAuth } from "@/context/AuthContext";
import CollectionSort from "@/components/CollectionSort";
import { useQueryState } from "@/lib/useUrlFilters";
import { useDialogChanges, useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient, ApiError } from "@/lib/api";

interface StaffItem {
  id: string;
  name: string;
  email: string;
  role: string;
  active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

interface StaffListResponse {
  items: StaffItem[];
  page: number;
  page_size: number;
  total: number;
}

export default function StaffManagementPage() {
  const requestSequence = useRef(0);
  const { user } = useAuth();

  const [staffList, setStaffList] = useState<StaffItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useQueryState("page", 1);
  const [pageSize] = useState(15);
  const [search, setSearch] = useQueryState("search", "");
  const [activeFilter, setActiveFilter] = useQueryState<string>("active", "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Deactivate/Reactivate confirmation modal
  const [confirmModalUser, setConfirmModalUser] = useState<StaffItem | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const dialogDirty0 = useDialogChanges(drawerOpen, [name, email, password, confirmPassword]);
  useUnsavedChanges(dialogDirty0);

  const fetchStaff = useCallback(async () => {const request = ++requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", page.toString());
      params.set("page_size", pageSize.toString());
      if (search.trim()) params.set("search", search.trim());
      if (activeFilter === "active") params.set("active", "true");
      if (activeFilter === "inactive") params.set("active", "false");

      const res = await apiClient<StaffListResponse>(`/staff?${params.toString()}`); if (request !== requestSequence.current) return;
      setStaffList(res.items);
      setTotal(res.total);
    } catch (err) {if (request !== requestSequence.current) return;
      setError(err instanceof ApiError ? err.message : "Failed to load staff list.");
    } finally {
      if (request === requestSequence.current) setLoading(false);
    }
  }, [page, pageSize, search, activeFilter]);

  useEffect(() => {
    if (user?.role === "ADMIN") {
      fetchStaff();
    }
  }, [fetchStaff, user]);

  if (user && user.role !== "ADMIN") {
    return (
      <div className="p-8 text-center bg-white border border-red-200 rounded-lg">
        <ShieldAlert className="w-8 h-8 text-red-600 mx-auto mb-2" />
        <h2 className="text-lg font-bold text-slate-900">Access Restricted</h2>
        <p className="text-sm text-slate-600 mt-1">
          Staff management is reserved exclusively for System Administrators.
        </p>
      </div>
    );
  }

  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    if (password !== confirmPassword) {
      setCreateError("Passwords do not match.");
      return;
    }

    setCreateLoading(true);

    try {
      await apiClient("/staff", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          initial_password: password,
        }),
      });

      setDrawerOpen(false);
      setName("");
      setEmail("");
      setPassword("");
      setConfirmPassword("");
      fetchStaff();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to provision staff member.");
    } finally {
      setCreateLoading(false);
    }
  };

  const handleToggleActive = async () => {
    if (!confirmModalUser) return;
    setActionLoading(true);
    setActionError(null);

    const action = confirmModalUser.active ? "deactivate" : "reactivate";
    try {
      await apiClient(`/staff/${confirmModalUser.id}/${action}`, {
        method: "POST",
      });
      setConfirmModalUser(null);
      fetchStaff();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : `Failed to ${action} staff.`);
    } finally {
      setActionLoading(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Staff Management
          </h1>
          <p className="text-sm text-slate-600">
            Provision staff members, configure operational access and manage account lifecycles
          </p>
        </div>
        <button type="button"
          onClick={() => setDrawerOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          <span>Provision Staff</span>
        </button>
      </div>
      <CollectionSort fields={[["created_at", "Created"], ["name", "Name"], ["email", "Email"]]} initial="created_at" descending={true} onChange={() => {if (page === 1) fetchStaff(); else setPage(1);}} />

      {/* Filter / Search Bar */}
      <div className="bg-white p-4 border border-slate-200 rounded-lg shadow-sm flex flex-col md:flex-row gap-4 justify-between items-center">
        <div className="relative w-full md:w-96">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search staff by name or email..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-1.5 text-sm text-slate-600">
            <Filter className="w-4 h-4" />
            <span>Status:</span>
          </div>
          <select aria-label="Activity filter"
            value={activeFilter}
            onChange={(e) => {
              setActiveFilter(e.target.value);
              setPage(1);
            }}
            className="py-1.5 px-3 border border-slate-300 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>

          <button type="button"
            onClick={() => fetchStaff()}
            title="Refresh"
            className="p-2 border border-slate-300 rounded-md hover:bg-slate-50 text-slate-600 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Staff Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <ScrollableRegion className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <th className="px-6 py-3">Staff Member</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Joined Date</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                    Loading staff records...
                  </td>
                </tr>
              ) : staffList.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                    No staff members found matching the selected criteria.
                  </td>
                </tr>
              ) : (
                staffList.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50 transition">
                    <td className="px-6 py-4">
                      <p className="font-medium text-slate-900">{s.name}</p>
                      <p className="text-xs text-slate-500">{s.email}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-block text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-800">
                        {s.role}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {s.active ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                          <UserCheck className="w-3 h-3" />
                          <span>Active</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-800">
                          <UserX className="w-3 h-3" />
                          <span>Deactivated</span>
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-500">
                      {new Date(s.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {s.id === user?.id ? (
                        <span className="text-xs text-slate-500 italic">Current User</span>
                      ) : (
                        <button type="button"
                          onClick={() => setConfirmModalUser(s)}
                          className={`text-xs font-medium ${
                            s.active
                              ? "text-red-600 hover:text-red-800"
                              : "text-emerald-700 hover:text-emerald-800"
                          }`}
                        >
                          {s.active ? "Deactivate" : "Reactivate"}
                        </button>
                      )}
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
            Showing {staffList.length > 0 ? (page - 1) * pageSize + 1 : 0} to{" "}
            {Math.min(page * pageSize, total)} of {total} staff member{total !== 1 ? "s" : ""}
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

      {/* Provision Staff Drawer */}
      {drawerOpen && (
        <Modal className="fixed inset-0 z-50 overflow-y-auto flex justify-end" onDismiss={() => setDrawerOpen(false)} busy={createLoading}>
          <div className="w-full max-w-md bg-white h-full shadow-2xl flex flex-col">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                Provision Staff Account
              </h2>
              <button type="button" aria-label="Close dialog"
                data-discard-form onClick={() => setDrawerOpen(false)}
                className="text-slate-500 hover:text-slate-600 text-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateStaff} className="flex-1 overflow-y-auto p-6 space-y-4 text-sm">
              {createError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
                  {createError}
                </div>
              )}

              <div>
                <label htmlFor="field-app-staff-page-tsx-1" className="block text-xs font-semibold text-slate-700 mb-1">
                  Full Name <span className="text-red-500">*</span>
                </label>
                <input id="field-app-staff-page-tsx-1"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Staff member full name"
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="field-app-staff-page-tsx-2" className="block text-xs font-semibold text-slate-700 mb-1">
                  Email Address <span className="text-red-500">*</span>
                </label>
                <input id="field-app-staff-page-tsx-2"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="staff@brightloop.test"
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="field-app-staff-page-tsx-3" className="block text-xs font-semibold text-slate-700 mb-1">
                  Assigned Role
                </label>
                <input id="field-app-staff-page-tsx-3"
                  type="text"
                  readOnly
                  value="STAFF"
                  className="w-full px-3 py-2 border border-slate-200 bg-slate-100 text-slate-600 rounded text-sm cursor-not-allowed"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Role is fixed to STAFF. Staff members can operate quotations, subscriptions, and customers.
                </p>
              </div>

              <div>
                <label htmlFor="field-app-staff-page-tsx-4" className="block text-xs font-semibold text-slate-700 mb-1">
                  Initial Password <span className="text-red-500">*</span>
                </label>
                <input id="field-app-staff-page-tsx-4"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="•••••••••"
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
                <PasswordChecklist password={password} />
              </div>

              <div>
                <label htmlFor="field-app-staff-page-tsx-5" className="block text-xs font-semibold text-slate-700 mb-1">
                  Confirm Password <span className="text-red-500">*</span>
                </label>
                <input id="field-app-staff-page-tsx-5"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="•••••••••"
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div className="pt-4 border-t border-slate-200 flex justify-end gap-3">
                <button
                  type="button"
                  data-discard-form onClick={() => setDrawerOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium disabled:opacity-50"
                >
                  {createLoading ? "Creating..." : "Provision Staff"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}

      {/* Confirmation Modal */}
      {confirmModalUser && (
        <Modal className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4" onDismiss={() => setConfirmModalUser(null)} busy={actionLoading}>
          <div className="w-full max-w-md bg-white rounded-xl shadow-2xl p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-2">
              {confirmModalUser.active ? "Deactivate Staff Member?" : "Reactivate Staff Member?"}
            </h3>
            <p className="text-sm text-slate-600 mb-4">
              {confirmModalUser.active
                ? `Deactivating ${confirmModalUser.name} (${confirmModalUser.email}) will immediately revoke all active sessions. They will be logged out and cannot sign in until reactivated.`
                : `Reactivating ${confirmModalUser.name} (${confirmModalUser.email}) will permit them to sign in again.`}
            </p>

            {actionError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
                {actionError}
              </div>
            )}

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmModalUser(null)}
                className="px-4 py-2 border border-slate-300 rounded text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={actionLoading}
                onClick={handleToggleActive}
                className={`px-4 py-2 text-white rounded text-sm font-medium disabled:opacity-50 ${
                  confirmModalUser.active
                    ? "bg-red-600 hover:bg-red-700"
                    : "bg-emerald-600 hover:bg-emerald-700"
                }`}
              >
                {actionLoading
                  ? "Processing..."
                  : confirmModalUser.active
                  ? "Confirm Deactivation"
                  : "Confirm Reactivation"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
