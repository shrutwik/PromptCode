/**
 * Outbound delivery worker.
 * deliverOne posts one job, up to policy.maxAttempts, and waits policy.backoffMs between tries.
 * It sends header X-Delivery-Id. A true return means the client responded ok.
 * deliverAll runs deliverOne for each job. recordCharge is the billing side effect, keyed by delivery id.
 * wrapClientWithStats counts how many posts are in flight at once. getMaxInFlight reads the high-water mark.
 */
import type { DeliveryJob, HttpClient } from './types.js';
import { defaultPolicy, type RetryPolicy } from './retryPolicy.js';
import { recordCharge } from './sideEffects.js';

async function sleep(ms: number): Promise<void> {
  if (ms <= 0) return;
  await new Promise((r) => setTimeout(r, ms));
}

export async function deliverOne(job: DeliveryJob, client: HttpClient, policy: RetryPolicy = defaultPolicy): Promise<boolean> {
  for (let attempt = 1; attempt <= policy.maxAttempts; attempt++) {
    job.attempts = attempt;
    recordCharge(job.id);
    const res = await client.post(job.url, job.payload, { 'X-Delivery-Id': job.id });
    if (res.ok) return true;
    await sleep(policy.backoffMs);
  }
  return false;
}

export async function deliverAll(jobs: DeliveryJob[], client: HttpClient, policy: RetryPolicy = defaultPolicy): Promise<boolean[]> {
  return Promise.all(jobs.map((job) => deliverOne(job, client, policy)));
}

let inFlight = 0;
let maxInFlight = 0;
export function resetConcurrencyStats(): void { inFlight = 0; maxInFlight = 0; }
export function getMaxInFlight(): number { return maxInFlight; }
export function wrapClientWithStats(client: HttpClient): HttpClient {
  return {
    async post(url, body, headers) {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      try { return await client.post(url, body, headers); }
      finally { inFlight -= 1; }
    },
  };
}
