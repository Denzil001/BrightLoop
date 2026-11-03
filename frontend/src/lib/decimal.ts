/** Decimal form values and minor-unit previews never pass through floating point. */
export class DecimalInputError extends Error {}

interface DecimalOptions {
  scale?: number;
  signed?: boolean;
  maxIntegerDigits?: number;
  label?: string;
}

export function decimalInput(value: string, {scale = 2, signed = false, maxIntegerDigits = 16, label = "Amount"}: DecimalOptions = {}): string {
  const match = /^([+-]?)(\d+)(?:\.(\d*))?$/.exec(value.trim());
  const invalid = () => new DecimalInputError(`${label}: enter a decimal with up to ${maxIntegerDigits} whole digits and ${scale} decimal places.`);
  if (!match) throw invalid();
  const whole = match[2].replace(/^0+(?=\d)/, "");
  const fraction = (match[3] || "").replace(/0+$/, "");
  if (whole.length > maxIntegerDigits || fraction.length > scale) throw invalid();
  const negative = match[1] === "-" && (whole !== "0" || /[1-9]/.test(fraction));
  if (negative && !signed) throw new DecimalInputError(`${label} cannot be negative.`);
  return `${negative ? "-" : ""}${whole}.${fraction.padEnd(scale, "0")}`;
}

export function decimalKey(value: string | number | null | undefined, scale = 2): string {
  try {return decimalInput(String(value ?? "0"), {signed: true, scale});}
  catch {return String(value ?? "");}
}

function minor(value: string, signed = false): bigint {
  return BigInt(decimalInput(value, {signed}).replace(".", ""));
}

function fromMinor(value: bigint): string {
  const negative = value < BigInt(0);
  const digits = (negative ? -value : value).toString().padStart(3, "0");
  return `${negative ? "-" : ""}${digits.slice(0, -2)}.${digits.slice(-2)}`;
}

export function addMoney(left: string, right: string): string {
  return decimalInput(fromMinor(minor(left, true) + minor(right, true)), {signed: true, label: "Calculated amount"});
}

export function formatAdjustment(value: string): string {
  const amount = decimalInput(value, {signed: true, label: "Price adjustment"});
  return amount.startsWith("-") ? `-${formatCurrency(amount.slice(1))}` : `+${formatCurrency(amount)}`;
}

export function subtractMoney(left: string, right: string, floorAtZero = false): string {
  const difference = minor(left) - minor(right);
  return fromMinor(floorAtZero && difference < BigInt(0) ? BigInt(0) : difference);
}

export function formatCurrency(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "₹0.00";
  try {
    const value = typeof amount === "number" ? amount.toFixed(2) : amount;
    return `₹${decimalInput(value, {signed: true, maxIntegerDigits: Infinity})}`;
  } catch {return "₹0.00";}
}
