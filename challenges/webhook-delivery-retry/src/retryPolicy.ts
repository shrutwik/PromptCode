export interface RetryPolicy { maxAttempts: number; backoffMs: number; }
export const defaultPolicy: RetryPolicy = { maxAttempts: 3, backoffMs: 0 };
