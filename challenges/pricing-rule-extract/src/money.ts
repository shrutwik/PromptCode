/** Half-up rounding for percent math, and a display string of cents / 100. Display is not the quote. */
export function roundHalfUp(n: number): number { return Math.round(n + Number.EPSILON); }
export function centsToDisplay(cents: number): string { return (cents / 100).toFixed(2); }
