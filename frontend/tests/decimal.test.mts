import assert from "node:assert/strict";
import { test } from "node:test";
import { addMoney, decimalInput, decimalKey, formatAdjustment, formatCurrency, subtractMoney } from "../src/lib/decimal.ts";

test("large stored prices retain cents through form normalization and display", () => {
  const amount = "90071992547409.93";
  assert.equal(decimalInput(amount), amount);
  assert.equal(formatCurrency(amount), "₹90071992547409.93");
  assert.notEqual(decimalKey(amount), decimalKey("90071992547409.94"));
  assert.equal(decimalInput("0001.2300"), "1.23");
});

test("minor-unit previews retain a cent near the storage limit", () => {
  assert.equal(addMoney("90071992547409.93", "0.01"), "90071992547409.94");
  assert.equal(subtractMoney("9999999999999999.99", "9999999999999999.98"), "0.01");
  assert.equal(addMoney("760.00", "-560.00"), "200.00");
  assert.equal(subtractMoney("10.00", "11.00", true), "0.00");
  assert.equal(formatAdjustment("-560.00"), "-₹560.00");
});

test("invalid precision, non-finite and out-of-range inputs fail without rounding", () => {
  for (const value of ["1.001", "Infinity", "NaN", "10000000000000000.00", "-0.01", "1e2", ""]) {
    assert.throws(() => decimalInput(value));
  }
  assert.throws(() => addMoney("9999999999999999.99", "0.01"));
  assert.equal(decimalInput("-0.00"), "0.00");
  assert.equal(decimalInput("18.1234", {scale: 4, maxIntegerDigits: 3}), "18.1234");
});

test("report aggregates can display totals larger than a single stored amount", () => {
  assert.equal(formatCurrency("1000000000000000000.01"), "₹1000000000000000000.01");
});
