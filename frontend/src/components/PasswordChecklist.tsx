"use client";

import React from "react";

interface PasswordChecklistProps {
  password: string;
}

export function PasswordChecklist({ password }: PasswordChecklistProps) {
  const hasMinLength = password.length >= 9;
  const hasUppercase = /[A-Z]/.test(password);
  const hasLowercase = /[a-z]/.test(password);
  const hasSpecial = /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/~`'"\\]/.test(password);

  const criteria = [
    { label: "At least 9 characters", met: hasMinLength },
    { label: "At least one uppercase letter", met: hasUppercase },
    { label: "At least one lowercase letter", met: hasLowercase },
    { label: "At least one special character (!@#$%^&*...)", met: hasSpecial },
  ];

  return (
    <div className="text-xs space-y-1 mt-2 p-3 bg-slate-50 border border-slate-200 rounded-md">
      <p className="font-semibold text-slate-700 mb-1">Password requirements:</p>
      <ul className="space-y-0.5">
        {criteria.map((item, idx) => (
          <li
            key={idx}
            className={`flex items-center space-x-1.5 ${
              item.met ? "text-emerald-600 font-medium" : "text-slate-500"
            }`}
          >
            <span>{item.met ? "✓" : "○"}</span>
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
