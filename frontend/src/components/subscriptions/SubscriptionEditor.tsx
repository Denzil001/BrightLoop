"use client";
import ScrollableRegion from "@/components/ScrollableRegion";
import { type FormEvent, useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api";
import { buttonStyle, type DraftLine, type DraftPayload, errorMessage, inputStyle, secondaryStyle } from "@/lib/subscriptions";
import { formatCurrency } from "@/lib/utils";
import { useUnsavedChanges } from "@/lib/useUnsavedChanges";
import ServicePolicySummary, { type ServicePolicies } from "./ServicePolicySummary";

interface Choice { id: string; name: string }
interface Plan extends Choice, ServicePolicies { minimum_seats: number; base_fee: string; extra_seat_unit_price: string; payment_term_days: number; interval: string; items: {product_id: string; variant_id: string | null; included_quantity: number}[] }
interface Product extends Choice { sales_price: string; variants: {id: string; name: string; active: boolean; effective_sales_price: string}[] }
interface Template extends Choice {plan_id: string; validity_days: number; lines: {product_id: string; variant_id: string | null; quantity: number; line_kind: string}[]}
interface Preview {subtotal: string; total_discount: string; total_tax: string; total: string; discount_ineligible_reason: string | null; lines: {ordinal: number; description: string; quantity: number; unit_price: string; discount_amount: string; tax_amount: string; total: string}[]}

// Symbol keys survive local row edits but JSON omits them from API payloads.
const rowKey = Symbol("editor-row");
type EditorLine = DraftLine & { [rowKey]: string };
type EditorDraft = Omit<DraftPayload, "lines"> & { lines: EditorLine[] };
function keyedDraft(payload: DraftPayload): EditorDraft {
  return {...payload, lines: payload.lines.map(line => ({...line,
    [rowKey]: (line as Partial<EditorLine>)[rowKey] || crypto.randomUUID(),
  }))};
}

function today() { return new Intl.DateTimeFormat("en-CA", {timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date()); }

export default function SubscriptionEditor({initial, onSave, submitLabel = "Save draft", fixedIdentity = false, portalId, changeAction, acceptedPolicies}: {
  initial?: DraftPayload; onSave: (payload: DraftPayload, issue: boolean) => Promise<void>;
  submitLabel?: string; fixedIdentity?: boolean;
  portalId?: string; changeAction?: string; acceptedPolicies?: Record<string, boolean>;
}) {
  const [form, setForm] = useState<EditorDraft>(() => keyedDraft(initial || {customer_id: "", plan_id: "", template_id: null,
    seat_quantity: 1, start_date: today(), expiry_date: "", payment_term_days: 15, validity_days: 30, lines: [], discount_id: null, discount_ids: []}));
  const [customers, setCustomers] = useState<Choice[]>([]); const [plans, setPlans] = useState<Plan[]>([]);
  const [products, setProducts] = useState<Product[]>([]); const [templates, setTemplates] = useState<Template[]>([]);
  const [discounts, setDiscounts] = useState<Choice[]>([]); const [customerSearch, setCustomerSearch] = useState("");
  const [planSearch, setPlanSearch] = useState(""); const [productSearch, setProductSearch] = useState("");
  const [templateSearch, setTemplateSearch] = useState(""); const [discountSearch, setDiscountSearch] = useState("");
  const [error, setError] = useState(""); const [fields, setFields] = useState<{path: string; message: string}[]>([]);
  const [saving, setSaving] = useState(false); const [preview, setPreview] = useState<Preview | null>(null);
  const [dirty, setDirty] = useState(false); const [previewing, setPreviewing] = useState(false);
  const [loading, setLoading] = useState(true); const [retry, setRetry] = useState(0);
  useUnsavedChanges(dirty);
  useEffect(() => {
    if (initial || fixedIdentity) return;
    const customerId = new URLSearchParams(window.location.search).get("customer_id");
    if (customerId) {
      setForm(prev => ({...prev, customer_id: customerId}));
      apiClient<Choice>(`/customers/${customerId}`).then(customer => setCustomerSearch(customer.name)).catch(e => setError(errorMessage(e)));
    }
  }, [initial, fixedIdentity]);
  const update = (patch: Partial<DraftPayload>) => {setForm(prev => keyedDraft({...prev, ...patch})); setPreview(null); setDirty(true);};
  const needsProducts = form.lines.length > 0 || productSearch.length > 0;
  useEffect(() => { let alive = true; const timer = setTimeout(async () => {
    setLoading(true);
    try {
      if (portalId) {
        const options = await apiClient<{plans: Plan[]; products: Product[]}>(`/subscriptions/${portalId}/change-options?search=${encodeURIComponent(productSearch)}`);
        if (alive) {setPlans(options.plans); setProducts(options.products); setError("");}
        return;
      }
      const [c, p, x, t, d] = await Promise.all([
        fixedIdentity ? Promise.resolve({items: [] as Choice[]}) : apiClient<{items: Choice[]}>(`/customers?page_size=100&search=${encodeURIComponent(customerSearch)}`),
        fixedIdentity && form.plan_id ? apiClient<Plan>(`/plans/${form.plan_id}`).then(plan => ({items: [plan]})) : apiClient<{items: Plan[]}>(`/plans?active=true&page_size=100&search=${encodeURIComponent(planSearch)}`),
        needsProducts ? apiClient<{items: Product[]}>(`/products?active=true&page_size=100&search=${encodeURIComponent(productSearch)}`) : Promise.resolve({items: [] as Product[]}),
        !fixedIdentity && form.plan_id ? apiClient<{items: Template[]}>(`/quotation-templates?active=true&page_size=100&plan_id=${form.plan_id}&search=${encodeURIComponent(templateSearch)}`) : Promise.resolve({items: [] as Template[]}),
        form.plan_id ? apiClient<{items: Choice[]}>(`/discounts?active=true&page_size=100&search=${encodeURIComponent(discountSearch)}`) : Promise.resolve({items: [] as Choice[]})]);
      if (alive) {setCustomers(c.items); setPlans(p.items); setProducts(x.items); setTemplates(t.items); setDiscounts(d.items); setError("");}
    } catch (e) {if (alive) setError(errorMessage(e));} finally {if (alive) setLoading(false);}
  }, customerSearch || planSearch || productSearch || templateSearch || discountSearch ? 250 : 0);
    return () => {alive = false; clearTimeout(timer);};
  }, [customerSearch, planSearch, productSearch, templateSearch, discountSearch, form.plan_id, retry, portalId, fixedIdentity, needsProducts]);
  const selectedProductIds = form.lines.map(line => line.product_id).filter(Boolean).join(",");
  const selectedDiscountIds = form.discount_ids.join(",");
  useEffect(() => {
    if (loading) return;
    const missingProducts = [...new Set(selectedProductIds.split(",").filter(Boolean))].filter(id => !products.some(product => product.id === id));
    if (portalId) {
      if (!missingProducts.length) return;
      let alive = true;
      Promise.all(missingProducts.map(id => apiClient<{products: Product[]}>(`/subscriptions/${portalId}/change-options?product_id=${encodeURIComponent(id)}`)))
        .then(results => {const selected = results.flatMap(result => result.products); if (alive && selected.length) setProducts(previous => [...previous, ...selected.filter(item => !previous.some(old => old.id === item.id))]);})
        .catch(e => {if (alive) setError(errorMessage(e));});
      return () => {alive = false;};
    }
    const missingDiscounts = selectedDiscountIds.split(",").filter(Boolean).filter(id => !discounts.some(discount => discount.id === id));
    const missingPlan = form.plan_id && !plans.some(plan => plan.id === form.plan_id);
    if (!missingProducts.length && !missingDiscounts.length && !missingPlan) return;
    let alive = true;
    Promise.all([missingPlan ? apiClient<Plan>(`/plans/${form.plan_id}`) : Promise.resolve(null),
      Promise.all(missingProducts.map(id => apiClient<Product>(`/products/${id}`))),
      Promise.all(missingDiscounts.map(id => apiClient<Choice>(`/discounts/${id}`)))]).then(([plan, selectedProducts, selectedDiscounts]) => {
      if (!alive) return;
      if (plan) setPlans(previous => [...previous.filter(item => item.id !== plan.id), plan]);
      if (selectedProducts.length) setProducts(previous => [...previous, ...selectedProducts.filter(item => !previous.some(old => old.id === item.id))]);
      if (selectedDiscounts.length) setDiscounts(previous => [...previous, ...selectedDiscounts.filter(item => !previous.some(old => old.id === item.id))]);
    }).catch(e => {if (alive) setError(errorMessage(e));});
    return () => {alive = false;};
  }, [loading, portalId, form.plan_id, selectedProductIds, selectedDiscountIds, products, plans, discounts]);
  const selectedPlan = plans.find(p => p.id === form.plan_id);
  const setPlan = (id: string) => { const p = plans.find(x => x.id === id); if (!p) return;
    update({plan_id: id, template_id: null, seat_quantity: p.minimum_seats, payment_term_days: p.payment_term_days,
      lines: p.items.map(x => ({product_id: x.product_id, variant_id: x.variant_id, quantity: x.included_quantity, line_kind: "INCLUDED"}))}); };
  const setTemplate = (id: string) => {const t = templates.find(x => x.id === id); update({template_id: id || null,
    ...(t ? {validity_days: t.validity_days, lines: t.lines.map(x => ({product_id: x.product_id, variant_id: x.variant_id, quantity: x.quantity, line_kind: x.line_kind}))} : {})});};
  const runPreview = async () => { setPreviewing(true); setError(""); setFields([]); try {
    if (portalId) setPreview(await apiClient<Preview>(`/subscriptions/${portalId}/change-preview`, {method: "POST", body: JSON.stringify({action: changeAction, effective_date: form.start_date, reason: "Preview proposed terms", proposal: form})}));
    else setPreview(await apiClient<Preview>("/pricing/preview", {method: "POST", body: JSON.stringify({plan_id: form.plan_id,
      seat_quantity: form.seat_quantity, as_of_date: form.start_date, lines: form.lines, discount_id: form.discount_id, discount_ids: form.discount_ids})}));
  } catch (e) {setError(errorMessage(e)); if (e instanceof ApiError) setFields(e.fields || []);} finally {setPreviewing(false);} };
  const save = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setSaving(true); setError(""); setFields([]);
    try {const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement; await onSave(form, submitter?.value === "issue"); setDirty(false);}
    catch (e) {setError(errorMessage(e)); if (e instanceof ApiError) setFields(e.fields || []);} finally {setSaving(false);} };
  return <form onSubmit={save} className="space-y-6">
    {error && <div role="alert" className="rounded bg-red-50 p-4 text-red-700">{error}<ul>{fields.map(f => <li key={f.path}>{f.path}: {f.message}</li>)}</ul><button type="button" className="underline" onClick={() => setRetry(retry + 1)}>Reload choices</button></div>}
    <fieldset disabled={saving} className="space-y-6">
      {!fixedIdentity && <div className="grid gap-4 rounded-lg border bg-white p-5 md:grid-cols-2">
        <label className="text-sm">Find customer<input className={inputStyle} value={customerSearch} onChange={e => setCustomerSearch(e.target.value)} placeholder="Search name or email" /></label>
        <label className="text-sm">Customer<select required className={inputStyle} value={form.customer_id} onChange={e => update({customer_id: e.target.value})}><option value="">Select customer</option>{form.customer_id && !customers.some(c => c.id === form.customer_id) && <option value={form.customer_id}>Selected customer</option>}{customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label className="text-sm">Find plan<input className={inputStyle} value={planSearch} onChange={e => setPlanSearch(e.target.value)} /></label>
        <label className="text-sm">Plan<select required className={inputStyle} value={form.plan_id} onChange={e => setPlan(e.target.value)}><option value="">Select active plan</option>{form.plan_id && !plans.some(p => p.id === form.plan_id) && <option value={form.plan_id}>Selected plan</option>}{plans.map(p => <option key={p.id} value={p.id}>{p.name} · {p.interval}</option>)}</select></label>
        <label className="text-sm">Find quotation template<input className={inputStyle} value={templateSearch} onChange={e => setTemplateSearch(e.target.value)} /></label><label className="text-sm">Quotation template<select disabled={!form.plan_id} className={inputStyle} value={form.template_id || ""} onChange={e => setTemplate(e.target.value)}><option value="">{form.plan_id ? "No template" : "Select a plan first"}</option>{templates.filter(t => t.plan_id === form.plan_id).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
      </div>}
      {loading && <p role="status" className="text-sm text-slate-500">Loading available choices…</p>}
      {selectedPlan && <p className="rounded bg-blue-50 p-4 text-sm text-blue-900">{formatCurrency(selectedPlan.base_fee)} per {selectedPlan.interval.toLowerCase()} includes {selectedPlan.minimum_seats} seats. Each excess seat: {formatCurrency(selectedPlan.extra_seat_unit_price)}.</p>}
      {selectedPlan && <ServicePolicySummary
        label={changeAction === "ADDON_CHANGE" ? "Existing term policies retained" : "Proposed term policies"}
        policies={changeAction === "ADDON_CHANGE" && acceptedPolicies ? acceptedPolicies : {
          allow_pause: selectedPlan.allow_pause, allow_resume: selectedPlan.allow_resume,
          allow_renewal: selectedPlan.allow_renewal, allow_early_closure: selectedPlan.allow_early_closure,
          auto_close_on_expiry: selectedPlan.auto_close_on_expiry,
        }} />}
      <div className="grid gap-4 rounded-lg border bg-white p-5 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm">Seat quantity<input className={inputStyle} type="number" required min={selectedPlan?.minimum_seats || 1} step="1" value={form.seat_quantity} onChange={e => update({seat_quantity: Number(e.target.value)})} /></label>
        <label className="text-sm">Service start<input className={inputStyle} type="date" required value={form.start_date} onChange={e => update({start_date: e.target.value})} /></label>
        <label className="text-sm">Service expiry (exclusive)<input className={inputStyle} type="date" required min={form.start_date} value={form.expiry_date} onChange={e => update({expiry_date: e.target.value})} /></label>
        <label className="text-sm">Payment term (days)<input className={inputStyle} type="number" required min="0" max="365" value={form.payment_term_days} onChange={e => update({payment_term_days: Number(e.target.value)})} /></label>
        <label className="text-sm">Quotation validity (days)<input className={inputStyle} type="number" required min="0" max="365" value={form.validity_days} onChange={e => update({validity_days: Number(e.target.value)})} /></label>
        {!portalId && <label className="text-sm">Discount rules<input aria-label="Find discount rule" className={inputStyle} value={discountSearch} onChange={e => setDiscountSearch(e.target.value)} placeholder="Search rule name" /><select aria-label="Discount rules" disabled={!form.plan_id} multiple className={inputStyle} value={form.discount_ids} onChange={e => update({discount_id: null, discount_ids: Array.from(e.target.selectedOptions, option => option.value)})}>{form.discount_ids.filter(id => !discounts.some(d => d.id === id)).map(id => <option key={id} value={id}>Selected rule · {id.slice(0, 8)}</option>)}{discounts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select><span className="text-xs text-slate-500">Optional. Product rules must affect disjoint charge lines; a whole-subscription rule must stand alone.</span></label>}
      </div>
      <section className="space-y-4 rounded-lg border bg-white p-5"><h2 className="font-semibold">Included items & add-ons</h2>
        <label className="block text-sm">Find product<input className={inputStyle} placeholder="Search available products" value={productSearch} onChange={e => setProductSearch(e.target.value)} /></label>
        {form.lines.map((line, i) => {const product = products.find(p => p.id === line.product_id); const edit = (patch: Partial<typeof line>) => update({lines: form.lines.map((x, index) => index === i ? {...x, ...patch} : x)});
          return <fieldset key={line[rowKey]} className="grid gap-3 rounded border p-4 sm:grid-cols-2 lg:grid-cols-4"><legend className="px-1 text-sm font-medium">Line {i + 1}</legend>
            <label className="text-sm">Product<select required className={inputStyle} value={line.product_id} onChange={e => edit({product_id: e.target.value, variant_id: null, agreed_unit_price: undefined})}><option value="">Select product</option>{line.product_id && !product && <option value={line.product_id}>Selected product</option>}{products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
            <label className="text-sm">Variant<select className={inputStyle} value={line.variant_id || ""} onChange={e => edit({variant_id: e.target.value || null, agreed_unit_price: undefined})}><option value="">Base product</option>{line.variant_id && !product?.variants.some(v => v.id === line.variant_id) && <option value={line.variant_id}>Selected variant</option>}{product?.variants.filter(v => v.active).map(v => <option key={v.id} value={v.id}>{v.name} · {formatCurrency(v.effective_sales_price)}</option>)}</select></label>
            <label className="text-sm">Quantity<input required className={inputStyle} type="number" min="1" step="1" value={line.quantity} onChange={e => edit({quantity: Number(e.target.value)})} /></label>
            <label className="text-sm">Charge<select className={inputStyle} value={line.line_kind} onChange={e => edit({line_kind: e.target.value})}><option value="ADDON">Paid add-on</option><option value="INCLUDED">Plan entitlement (₹0)</option></select></label>
            {line.line_kind === "ADDON" && <><label className="text-sm">Agreed unit price (₹, optional)<input className={inputStyle} type="number" min="0" step="0.01" placeholder={product?.sales_price} value={line.agreed_unit_price || ""} onChange={e => edit({agreed_unit_price: e.target.value || undefined})} /></label><label className="text-sm sm:col-span-2">Price override reason<input className={inputStyle} value={line.override_reason || ""} onChange={e => edit({override_reason: e.target.value})} /></label></>}
            <button type="button" className={`${secondaryStyle} self-end text-red-700`} onClick={() => update({lines: form.lines.filter((_, index) => index !== i)})}>Remove line {i + 1}</button>
          </fieldset>;})}
        {!form.lines.length && <p className="text-sm text-slate-500">Plan fee and excess seats are calculated automatically. Add products as needed.</p>}
        <button type="button" className={secondaryStyle} onClick={() => update({lines: [...form.lines, {product_id: "", variant_id: null, quantity: 1, line_kind: "ADDON"}]})}>Add product</button>
      </section>
      <section className="space-y-3 rounded-lg border bg-white p-5"><button type="button" disabled={!form.plan_id || previewing} className={secondaryStyle} onClick={runPreview}>{previewing ? "Calculating…" : "Preview pricing"}</button>
        {preview && <><ScrollableRegion className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{["Charge", "Qty", "Unit price", "Discount", "Tax", "Total"].map(h => <th key={h} className="p-2">{h}</th>)}</tr></thead><tbody>{preview.lines.map(l => <tr key={l.ordinal} className="border-t"><td className="p-2">{l.description}</td><td className="p-2">{l.quantity}</td>{(["unit_price", "discount_amount", "tax_amount", "total"] as const).map(key => <td key={key} className="p-2">{formatCurrency(l[key])}</td>)}</tr>)}</tbody></table></ScrollableRegion><p>Subtotal {formatCurrency(preview.subtotal)} · Discount {formatCurrency(preview.total_discount)} · Tax {formatCurrency(preview.total_tax)}</p><p className="text-lg font-bold">Estimated total {formatCurrency(preview.total)}</p><p className="text-sm text-slate-500">Quotation estimate; discount usage is reserved only when invoiced. {preview.discount_ineligible_reason}</p></>}
      </section>
      <div className="flex flex-wrap gap-3"><button className={buttonStyle} type="submit" disabled={saving || loading}>{saving ? "Saving…" : submitLabel}</button>{!fixedIdentity && <button type="submit" value="issue" className={secondaryStyle} disabled={saving || loading}>Save & issue quotation</button>}</div>
    </fieldset>
  </form>;
}
