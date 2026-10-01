import { describe, it, expect, beforeEach } from 'vitest';
import { deliverOne, deliverAll, resetConcurrencyStats, wrapClientWithStats, getMaxInFlight } from '../src/worker.js';
import { flakyClient } from '../src/httpMock.js';
import { resetCharges, chargeCount } from '../src/sideEffects.js';
import type { DeliveryJob } from '../src/types.js';
function job(id: string): DeliveryJob { return { id, url: `https://example.test/${id}`, payload: { id }, attempts: 0 }; }
beforeEach(() => { resetCharges(); resetConcurrencyStats(); });
describe('deliverOne', () => {
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
