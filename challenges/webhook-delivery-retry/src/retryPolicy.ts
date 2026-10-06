/** How many times deliverOne may post, and how long it waits between tries. Tests use backoffMs 0. */
export interface RetryPolicy { maxAttempts: number; backoffMs: number; }
export const defaultPolicy: RetryPolicy = { maxAttempts: 3, backoffMs: 0 };
