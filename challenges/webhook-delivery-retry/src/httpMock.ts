import type { HttpClient } from './types.js';
export function flakyClient(failTimes: Map<string, number>): HttpClient {
  const seen = new Map<string, number>();
  return {
    async post(url, _body, headers) {
      const id = headers?.['X-Delivery-Id'] ?? url;
      const n = (seen.get(id) ?? 0) + 1;
      seen.set(id, n);
      const fails = failTimes.get(id) ?? 0;
      if (n <= fails) return { ok: false, status: 500 };
      return { ok: true, status: 200 };
    },
  };
}
