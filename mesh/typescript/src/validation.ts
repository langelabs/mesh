import type { AtomicTypes, BaseTypes } from "./types.js";

/** Check whether a value is an ordinary string-keyed record. */
export function isRecord(value: unknown): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const prototype: unknown = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

/** Check whether a value is a finite Mesh scalar. */
function isAtomicValue(value: unknown): value is AtomicTypes {
  return typeof value === "string" || typeof value === "boolean"
    || (typeof value === "number" && Number.isFinite(value));
}

/** Check whether a value can be carried as a single Mesh argument or result. */
export function isBaseValue(value: unknown): value is BaseTypes {
  if (Array.isArray(value)) {
    return Array.from(value).every(isAtomicValue);
  }
  if (isRecord(value)) {
    return Object.values(value).every(isAtomicValue);
  }
  return isAtomicValue(value);
}
