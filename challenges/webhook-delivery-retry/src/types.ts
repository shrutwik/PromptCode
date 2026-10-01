export interface DeliveryJob { id: string; url: string; payload: Record<string, unknown>; attempts: number; }
export interface HttpClient {
  post(url: string, body: unknown, headers?: Record<string, string>): Promise<{ ok: boolean; status: number }>;
}
