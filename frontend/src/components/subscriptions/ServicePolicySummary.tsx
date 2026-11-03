const policyLabels = [
  ["allow_pause", "Pause"],
  ["allow_resume", "Resume"],
  ["allow_renewal", "Renewal"],
  ["allow_early_closure", "Early closure"],
  ["auto_close_on_expiry", "Automatic closure at expiry"],
] as const;

export type ServicePolicies = Record<(typeof policyLabels)[number][0], boolean>;

export default function ServicePolicySummary({ policies, label }: {
  policies: Record<string, boolean>; label: string;
}) {
  return <section aria-label={label} className="space-y-2 text-sm">
    <h3 className="font-medium">{label}</h3>
    <dl className="flex flex-wrap gap-x-5 gap-y-2">
      {policyLabels.map(([key, name]) => <div key={key} className="flex gap-1">
        <dt>{name}:</dt><dd>{policies[key] ? "Allowed" : "Not allowed"}</dd>
      </div>)}
    </dl>
  </section>;
}
