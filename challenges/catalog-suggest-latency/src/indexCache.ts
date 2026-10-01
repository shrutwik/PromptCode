const flags = new Map<string, boolean>();
export function getFlag(key: string, fallback = false): boolean { return flags.get(key) ?? fallback; }
export function setFlag(key: string, value: boolean): void { flags.set(key, value); }
