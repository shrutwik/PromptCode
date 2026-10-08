import { describe, it, expect, beforeEach } from 'vitest';
import { deliverOne, deliverAll, resetConcurrencyStats, wrapClientWithStats, getMaxInFlight } from '../src/worker.js';
import { flakyClient } from '../src/httpMock.js';
import { resetCharges, chargeCount } from '../src/sideEffects.js';
import type { DeliveryJob } from '../src/types.js';
function job(id: string): DeliveryJob { return { id, url: `https://example.test/${id}`, payload: { id }, attempts: 0 }; }
beforeEach(() => { resetCharges(); resetConcurrencyStats(); });
describe('deliverOne', () => {
  it('caps failed attempts and charges an exhausted delivery only once', async () => {
    let calls = 0;
    const client = { post: async () => { calls++; return { ok: false, status: 500 }; } };
    expect(await deliverOne(job('failed'), client, { maxAttempts: 4, backoffMs: 0 })).toBe(false);
    expect(calls).toBe(4);
    expect(chargeCount('failed')).toBe(1);
  });
  it('preserves mixed batch result order and handles an empty batch', async () => {
    const jobs = Array.from({ length: 12 }, (_, i) => job(String(i)));
    const client = { post: async (url: string) => {
      const ok = Number(url.split('/').pop()) % 2 === 0;
      return { ok, status: ok ? 200 : 500 };
    } };
    expect(await deliverAll(jobs, client, { maxAttempts: 2, backoffMs: 0 })).toEqual(jobs.map((_, i) => i % 2 === 0));
    expect(chargeCount()).toBe(12);
    expect(await deliverAll([], client, { maxAttempts: 2, backoffMs: 0 })).toEqual([]);
  });
  it('eventually succeeds after transient failures', async () => {
    const client = flakyClient(new Map([['d1', 2]]));
    expect(await deliverOne(job('d1'), client, { maxAttempts: 3, backoffMs: 0 })).toBe(true);
  });
});
describe('idempotency and concurrency', () => {
  it('does not charge more than once per successful delivery id', async () => {
    const client = flakyClient(new Map([['d2', 2]]));
    await deliverOne(job('d2'), client, { maxAttempts: 3, backoffMs: 0 });
    expect(chargeCount('d2')).toBe(1);
  });
  it('bounds concurrent outbound posts when delivering a batch', async () => {
    const fail = new Map<string, number>();
    const jobs = Array.from({ length: 20 }, (_, i) => { fail.set(`j${i}`, 0); return job(`j${i}`); });
    const client = wrapClientWithStats(flakyClient(fail));
    await deliverAll(jobs, client, { maxAttempts: 1, backoffMs: 0 });
    expect(getMaxInFlight()).toBeLessThanOrEqual(5);
  });
});
