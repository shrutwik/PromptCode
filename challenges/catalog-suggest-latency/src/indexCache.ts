/**
 * In-memory boolean flags keyed by string.
 * getFlag returns fallback when the key was never set. This map is not the product list.
 */
const flags = new Map<string, boolean>();
export function getFlag(key: string, fallback = false): boolean { return flags.get(key) ?? fallback; }
export function setFlag(key: string, value: boolean): void { flags.set(key, value); }
