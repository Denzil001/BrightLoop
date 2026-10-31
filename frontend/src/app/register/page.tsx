"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { PasswordChecklist } from "@/components/PasswordChecklist";
import { apiClient, ApiError } from "@/lib/api";

export default function RegisterPage() {
  return (
    <React.Suspense fallback={<div className="min-h-screen flex items-center justify-center p-4"><p className="text-sm text-slate-500">Loading registration...</p></div>}>
      <RegisterContent />
    </React.Suspense>
  );
}

function RegisterContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const verifyToken = searchParams.get("token");

  // Standard registration state
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [company, setCompany] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Verification mode state
  const [verifying, setVerifying] = useState(false);
  const [verificationSuccess, setVerificationSuccess] = useState(false);
  const [verificationError, setVerificationError] = useState<string | null>(null);

  // Auto-verify if token is in query params
  useEffect(() => {
    if (verifyToken) {
      setVerifying(true);
      apiClient<{ message: string; email: string }>("/auth/verify-signup", {
        method: "POST",
        body: JSON.stringify({ token: verifyToken }),
      })
        .then(() => {
          setVerificationSuccess(true);
        })
        .catch((err) => {
          setVerificationError(
            err instanceof ApiError
              ? err.message
              : "Invalid, expired, or already used verification link."
          );
        })
        .finally(() => {
          setVerifying(false);
        });
    }
  }, [verifyToken]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const res = await apiClient<{
        message: string;
        requires_verification: boolean;
      }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          name,
          email,
          password,
          company: company.trim() || undefined,
        }),
      });

      if (res.requires_verification) {
        setSuccessMessage(res.message);
      } else {
        router.push("/login?registered=true");
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Registration failed. Please check your inputs and try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  // If in token verification mode
  if (verifyToken) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl shadow-sm p-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 mb-2">
            Account Verification
          </h1>

          {verifying && (
            <p className="text-slate-600 my-6">Verifying your link, please wait...</p>
          )}

          {verificationSuccess && (
            <div className="my-6">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-emerald-100 text-emerald-600 text-xl font-bold mb-4">
                ✓
              </div>
              <p className="text-emerald-800 font-medium mb-2">
                Account Verified and Connected!
              </p>
              <p className="text-sm text-slate-600 mb-6">
                Your email has been verified and linked to your customer records.
              </p>
              <Link
                href="/login"
                className="inline-block py-2.5 px-6 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md text-sm transition"
              >
                Sign in to your account
              </Link>
            </div>
          )}

          {verificationError && (
            <div className="my-6">
              <div className="p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg mb-6 text-left">
                {verificationError}
              </div>
              <Link
                href="/register"
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                Back to registration
              </Link>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl shadow-sm p-8">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Create Customer Account
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Access your subscriptions, invoices, and profile
          </p>
        </div>

        {error && (
          <div className="mb-4 p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg">
            {error}
          </div>
        )}

        {successMessage ? (
          <div className="p-6 bg-blue-50 border border-blue-200 rounded-lg text-center">
            <h3 className="font-semibold text-blue-900 mb-2">Verification Required</h3>
            <p className="text-sm text-blue-800 mb-4">{successMessage}</p>
            <p className="text-xs text-blue-600">
              Please check your inbox (or local Mailpit interface) and click the link to finalize your account.
            </p>
            <div className="mt-6">
              <Link
                href="/login"
                className="text-sm font-medium text-blue-700 hover:underline"
              >
                Return to sign in
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="name"
                className="block text-sm font-medium text-slate-700 mb-1"
              >
                Full name <span className="text-red-500">*</span>
              </label>
              <input
                id="name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm"
                placeholder="Jane Doe"
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-slate-700 mb-1"
              >
                Email address <span className="text-red-500">*</span>
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm"
                placeholder="name@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="company"
                className="block text-sm font-medium text-slate-700 mb-1"
              >
                Company name (optional)
              </label>
              <input
                id="company"
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm"
                placeholder="Acme Corp"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-slate-700"
                >
                  Password <span className="text-red-500">*</span>
                </label>
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-xs text-slate-500 hover:text-slate-700"
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm"
                placeholder="•••••••••"
              />
              <PasswordChecklist password={password} />
            </div>

            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-medium text-slate-700 mb-1"
              >
                Confirm password <span className="text-red-500">*</span>
              </label>
              <input
                id="confirmPassword"
                type={showPassword ? "text" : "password"}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm"
                placeholder="•••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md text-sm shadow-sm transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Creating account..." : "Sign up"}
            </button>
          </form>
        )}

        <div className="mt-6 pt-6 border-t border-slate-100 text-center text-sm text-slate-600">
          Already have an account?{" "}
          <Link
            href="/login"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
