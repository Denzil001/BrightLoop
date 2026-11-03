"use client";
import Modal from "@/components/Modal";

import type React from "react";
import { useEffect, useState, useCallback } from "react";
import { KeyRound, User, Mail, MapPin, CheckCircle2 } from "lucide-react";
import { PasswordChecklist } from "@/components/PasswordChecklist";
import { useAuth } from "@/context/AuthContext";
import { useDialogChanges, useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { apiClient, ApiError } from "@/lib/api";

interface CustomerProfileData {
  id: string;
  customer_id: string;
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
  version: number;
}

export default function CustomerProfilePage() {
  const { refreshUser } = useAuth();

  const [loading, setLoading] = useState(true);
  const [profileData, setProfileData] = useState<CustomerProfileData | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Form fields
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [phone, setPhone] = useState("");
  const [address1, setAddress1] = useState("");
  const [address2, setAddress2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [postal, setPostal] = useState("");
  const [country, setCountry] = useState("India");

  // Change password modal
  const [pwdModalOpen, setPwdModalOpen] = useState(false);
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [pwdLoading, setPwdLoading] = useState(false);
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [pwdSuccess, setPwdSuccess] = useState<string | null>(null);

  const passwordDirty = useDialogChanges(pwdModalOpen, [currentPwd, newPwd, confirmPwd]);
  const profileDirty = Boolean(!loading && profileData && JSON.stringify([name, company, phone, address1, address2, city, state, postal, country]) !== JSON.stringify([profileData.name || "", profileData.company || "", profileData.phone || "", profileData.billing_address_line1 || "", profileData.billing_address_line2 || "", profileData.billing_city || "", profileData.billing_state || "", profileData.billing_postal_code || "", profileData.billing_country || "India"]));
  useUnsavedChanges(passwordDirty || profileDirty);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient<CustomerProfileData>("/profile");
      setProfileData(data);
      setName(data.name || "");
      setCompany(data.company || "");
      setPhone(data.phone || "");
      setAddress1(data.billing_address_line1 || "");
      setAddress2(data.billing_address_line2 || "");
      setCity(data.billing_city || "");
      setState(data.billing_state || "");
      setPostal(data.billing_postal_code || "");
      setCountry(data.billing_country || "India");
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to load customer profile.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(false);
    setSaveLoading(true);

    try {
      const updated = await apiClient<CustomerProfileData>("/profile", {
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
        }),
      });

      setProfileData(updated);
      await refreshUser();
      setSaveSuccess(true);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to save profile changes.");
    } finally {
      setSaveLoading(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwdError(null);
    setPwdSuccess(null);

    if (newPwd !== confirmPwd) {
      setPwdError("New passwords do not match.");
      return;
    }

    setPwdLoading(true);

    try {
      const res = await apiClient<{ message: string }>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPwd,
          new_password: newPwd,
        }),
      });
      setPwdSuccess(res.message);
      setCurrentPwd("");
      setNewPwd("");
      setConfirmPwd("");
    } catch (err) {
      setPwdError(err instanceof ApiError ? err.message : "Failed to change password.");
    } finally {
      setPwdLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-slate-500">
        Loading customer profile...
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          My Profile & Billing Details
        </h1>
        <p className="text-sm text-slate-600">
          Manage your contact information, billing addresses, and security preferences
        </p>
      </div>

      {saveSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-sm flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-700" />
          <span>Your profile and billing details have been updated successfully.</span>
        </div>
      )}

      {saveError && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {saveError}
        </div>
      )}

      {/* Main Profile Form */}
      <form onSubmit={handleSaveProfile} className="space-y-6">
        {/* Personal & Company Details */}
        <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm space-y-4">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider pb-2 border-b border-slate-100 flex items-center gap-2">
            <User className="w-4 h-4 text-blue-600" />
            <span>Customer Details</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <label htmlFor="field-portal-profile-page-tsx-1" className="block text-xs font-semibold text-slate-700 mb-1">
                Full Name <span className="text-red-500">*</span>
              </label>
              <input id="field-portal-profile-page-tsx-1"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
              />
            </div>

            <div>
              <p className="block text-xs font-semibold text-slate-700 mb-1">
                Login Email (Read-Only)
              </p>
              <div className="flex items-center gap-2 px-3 py-2 border border-slate-200 bg-slate-50 text-slate-600 rounded text-sm cursor-not-allowed">
                <Mail className="w-4 h-4 text-slate-500" />
                <span>{profileData?.email}</span>
              </div>
            </div>

            <div>
              <p className="block text-xs font-semibold text-slate-700 mb-1">
                Company Name (Optional)
              </p>
              <div className="relative">
                <input
                  type="text"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  placeholder="Acme Corp"
                />
              </div>
            </div>

            <div>
              <label htmlFor="field-portal-profile-page-tsx-2" className="block text-xs font-semibold text-slate-700 mb-1">
                Phone Number
              </label>
              <input id="field-portal-profile-page-tsx-2"
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                placeholder="+91 98765 43210"
              />
            </div>
          </div>
        </div>

        {/* Billing Address Details */}
        <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm space-y-4">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider pb-2 border-b border-slate-100 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-blue-600" />
            <span>Billing Address</span>
          </h2>

          <p className="text-xs text-slate-500">
            Address updates will apply to future invoice snapshots. Historic issued documents remain unchanged.
          </p>

          <div className="space-y-4 text-sm">
            <div>
              <label htmlFor="field-portal-profile-page-tsx-3" className="block text-xs font-semibold text-slate-700 mb-1">
                Address Line 1
              </label>
              <input id="field-portal-profile-page-tsx-3"
                type="text"
                value={address1}
                onChange={(e) => setAddress1(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                placeholder="Street address or P.O. Box"
              />
            </div>

            <div>
              <label htmlFor="field-portal-profile-page-tsx-4" className="block text-xs font-semibold text-slate-700 mb-1">
                Address Line 2 (Optional)
              </label>
              <input id="field-portal-profile-page-tsx-4"
                type="text"
                value={address2}
                onChange={(e) => setAddress2(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                placeholder="Apartment, suite, unit, building, floor"
              />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <label htmlFor="field-portal-profile-page-tsx-5" className="block text-xs font-semibold text-slate-700 mb-1">
                  City
                </label>
                <input id="field-portal-profile-page-tsx-5"
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="field-portal-profile-page-tsx-6" className="block text-xs font-semibold text-slate-700 mb-1">
                  State
                </label>
                <input id="field-portal-profile-page-tsx-6"
                  type="text"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="field-portal-profile-page-tsx-7" className="block text-xs font-semibold text-slate-700 mb-1">
                  Postal Code
                </label>
                <input id="field-portal-profile-page-tsx-7"
                  type="text"
                  value={postal}
                  onChange={(e) => setPostal(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="field-portal-profile-page-tsx-8" className="block text-xs font-semibold text-slate-700 mb-1">
                  Country
                </label>
                <input id="field-portal-profile-page-tsx-8"
                  type="text"
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saveLoading}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md text-sm shadow-sm transition disabled:opacity-50"
          >
            {saveLoading ? "Saving..." : "Save Profile & Address"}
          </button>
        </div>
      </form>

      {/* Security Card */}
      <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm space-y-4">
        <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider pb-2 border-b border-slate-100 flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-blue-600" />
          <span>Security & Authentication</span>
        </h2>

        <p className="text-xs text-slate-600">
          Maintain your account password. Changing your password will immediately sign out all other devices and active browser sessions.
        </p>

        <button type="button"
          onClick={() => {
            setPwdError(null);
            setPwdSuccess(null);
            setPwdModalOpen(true);
          }}
          className="px-4 py-2 border border-slate-300 rounded text-sm font-medium text-slate-700 hover:bg-slate-50 shadow-sm transition"
        >
          Change Password
        </button>
      </div>

      {/* Change Password Dialog */}
      {pwdModalOpen && (
        <Modal className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4" onDismiss={() => setPwdModalOpen(false)} busy={pwdLoading}>
          <div className="w-full max-w-md bg-white rounded-xl shadow-2xl p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4">
              Change Account Password
            </h3>

            {pwdSuccess ? (
              <div className="space-y-4">
                <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-sm">
                  {pwdSuccess}
                </div>
                <div className="flex justify-end">
                  <button type="button"
                    data-discard-form onClick={() => setPwdModalOpen(false)}
                    className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700"
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleChangePassword} className="space-y-4 text-sm">
                {pwdError && (
                  <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
                    {pwdError}
                  </div>
                )}

                <div>
                  <label htmlFor="field-portal-profile-page-tsx-9" className="block text-xs font-semibold text-slate-700 mb-1">
                    Current Password <span className="text-red-500">*</span>
                  </label>
                  <input id="field-portal-profile-page-tsx-9"
                    type="password"
                    required
                    value={currentPwd}
                    onChange={(e) => setCurrentPwd(e.target.value)}
                    placeholder="•••••••••"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                </div>

                <div>
                  <label htmlFor="field-portal-profile-page-tsx-10" className="block text-xs font-semibold text-slate-700 mb-1">
                    New Password <span className="text-red-500">*</span>
                  </label>
                  <input id="field-portal-profile-page-tsx-10"
                    type="password"
                    required
                    value={newPwd}
                    onChange={(e) => setNewPwd(e.target.value)}
                    placeholder="•••••••••"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                  <PasswordChecklist password={newPwd} />
                </div>

                <div>
                  <label htmlFor="field-portal-profile-page-tsx-11" className="block text-xs font-semibold text-slate-700 mb-1">
                    Confirm New Password <span className="text-red-500">*</span>
                  </label>
                  <input id="field-portal-profile-page-tsx-11"
                    type="password"
                    required
                    value={confirmPwd}
                    onChange={(e) => setConfirmPwd(e.target.value)}
                    placeholder="•••••••••"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:outline-none"
                  />
                </div>

                <div className="pt-4 border-t border-slate-200 flex justify-end gap-3">
                  <button
                    type="button"
                    data-discard-form onClick={() => setPwdModalOpen(false)}
                    className="px-4 py-2 border border-slate-300 rounded text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={pwdLoading}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium disabled:opacity-50"
                  >
                    {pwdLoading ? "Updating..." : "Update Password"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
