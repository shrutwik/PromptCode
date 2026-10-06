/**
 * DeliveryJob is one outbound webhook. attempts is how many posts this process has tried.
 * HttpClient.post returns ok and an HTTP status. Headers are optional.
 */
export interface DeliveryJob { id: string; url: string; payload: Record<string, unknown>; attempts: number; }
export interface HttpClient {
  post(url: string, body: unknown, headers?: Record<string, string>): Promise<{ ok: boolean; status: number }>;
}
