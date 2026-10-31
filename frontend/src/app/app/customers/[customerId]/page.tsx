"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { ChevronLeft, Edit, CheckCircle2, Clock, MapPin, Phone, Mail, Building } from "lucide-react";
import { apiClient, ApiError } from "@/lib/api";

interface CustomerDetail {
  id: string;
  name: string;
  email: string;
  company: string | null;
  phone: string | null;
  billing_address_line1: string | null;
  billing_address_line2: string | null;
  billing_city: string | null;
  billing_state: string | null;
  billing_postal_code: string | null;
  billing_country: string | null;
  user_id: string | null;
  has_portal_login: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export default function CustomerDetailPage({
  params,
}: {
  params: Promise<{ customerId: string }>;
}) {
  const resolvedParams = use(params);
  const customerId = resolvedParams.customerId;

  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit dialog state
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [phone, setPhone] = useState("");
  const [address1, setAddress1] = useState("");
  const [address2, setAddress2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [postal, setPostal] = useState("");
  const [country, setCountry] = useState("");

  const fetchDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient<CustomerDetail>(`/customers/${customerId}`);
      setCustomer(data);
      setName(data.name);
      setCompany(data.company || "");
      setPhone(data.phone || "");
      setAddress1(data.billing_address_line1 || "");
      setAddress2(data.billing_address_line2 || "");
      setCity(data.billing_city || "");
      setState(data.billing_state || "");
      setPostal(data.billing_postal_code || "");
      setCountry(data.billing_country || "");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load customer details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [customerId]);

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customer) return;
    setEditError(null);
    setEditLoading(true);

    try {
      const updated = await apiClient<CustomerDetail>(`/customers/${customerId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          company: company.trim() || null,
          phone: phone.trim() || null,
          billing_address_line1: address1.trim() || null,
          billing_address_line2: address2.trim() || null,
          billing_city: city.trim() || null,
          billing_state: state.trim() || null,
          billing_postal_code: postal.trim() || null,
          billing_country: country.trim() || null,
          expected_version: customer.version,
        }),
      });

      setCustomer(updated);
      setEditModalOpen(false);
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Failed to update customer.");
    } finally {
      setEditLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-slate-500">
        Loading customer information...
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div className="space-y-4">
        <Link
          href="/app/customers"
          className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
        >
          <ChevronLeft className="w-4 h-4" />
          <span>Back to Customers</span>
        </Link>
        <div className="p-6 bg-red-50 border border-red-200 text-red-700 rounded-lg">
          {error || "Customer record not found."}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Navigation & Header */}
      <div>
        <Link
          href="/app/customers"
          className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-800 mb-3"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          <span>Back to Customers List</span>
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                {customer.name}
              </h1>
              {customer.has_portal_login ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Portal Connected</span>
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                  <Clock className="w-3 h-3" />
                  <span>Unlinked (No Login)</span>
                </span>
              )}
            </div>
            {customer.company && (
              <p className="text-sm text-slate-600 mt-0.5">{customer.company}</p>
            )}
          </div>

          <button
            onClick={() => setEditModalOpen(true)}
            className="inline-flex items-center gap-2 px-3.5 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50 shadow-sm transition"
          >
            <Edit className="w-4 h-4" />
            <span>Edit Profile</span>
          </button>
        </div>
      </div>

      {/* Info Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Contact Information */}
        <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm space-y-4">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider pb-2 border-b border-slate-100">
            Contact Details
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex items-start gap-3">
              <Mail className="w-4 h-4 text-slate-400 mt-0.5" />
              <div>
                <p className="text-xs text-slate-500">Email Address (Immutable)</p>
                <p className="font-medium text-slate-900">{customer.email}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Phone className="w-4 h-4 text-slate-400 mt-0.5" />
              <div>
                <p className="text-xs text-slate-500">Phone</p>
                <p className="font-medium text-slate-900">{customer.phone || "Not provided"}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Building className="w-4 h-4 text-slate-400 mt-0.5" />
              <div>
                <p className="text-xs text-slate-500">Company</p>
                <p className="font-medium text-slate-900">{customer.company || "Not provided"}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Billing Address */}
        <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm space-y-4">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider pb-2 border-b border-slate-100">
            Billing Address
          </h2>
          <div className="flex items-start gap-3 text-sm">
            <MapPin className="w-4 h-4 text-slate-400 mt-0.5" />
            <div className="space-y-1 text-slate-700">
              {customer.billing_address_line1 || customer.billing_city || customer.billing_country ? (
                <>
                  {customer.billing_address_line1 && (
                    <p className="font-medium text-slate-900">{customer.billing_address_line1}</p>
                  )}
                  {customer.billing_address_line2 && <p>{customer.billing_address_line2}</p>}
                  <p>
                    {[customer.billing_city, customer.billing_state, customer.billing_postal_code]
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                  {customer.billing_country && <p>{customer.billing_country}</p>}
                </>
              ) : (
                <p className="text-slate-500 italic">No billing address recorded.</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Upcoming Modules Information Banner */}
      <div className="p-4 bg-slate-100 border border-slate-200 rounded-lg text-xs text-slate-600">
        <span className="font-semibold text-slate-800">Domain roadmap notice:</span> Subscriptions (Phase 4), Invoices (Phase 5), and Payments (Phase 6) tabs will activate seamlessly on this page as each domain is delivered.
      </div>

      {/* Edit Customer Dialog */}
      {editModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-40 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white rounded-xl shadow-2xl p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4">
              Edit Customer Profile
            </h3>

            {editError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
                {editError}
              </div>
            )}

            <form onSubmit={handleUpdate} className="space-y-4 text-sm">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Full / Organization Name
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Company
                  </label>
                  <input
                    type="text"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Phone
                  </label>
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Billing Address Line 1
                </label>
                <input
                  type="text"
                  value={address1}
                  onChange={(e) => setAddress1(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    City
                  </label>
                  <input
                    type="text"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    State
                  </label>
                  <input
                    type="text"
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Postal Code
                  </label>
                  <input
                    type="text"
                    value={postal}
                    onChange={(e) => setPostal(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Country
                  </label>
                  <input
                    type="text"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                </div>
              </div>

              <div className="pt-4 border-t border-slate-200 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium disabled:opacity-50"
                >
                  {editLoading ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
