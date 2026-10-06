/**
 * Billing side effects for a delivery id.
 * recordCharge appends the id. chargeCount filters by id, or returns the full list length when id is omitted.
 */
const charges: string[] = [];
export function resetCharges(): void { charges.length = 0; }
export function recordCharge(deliveryId: string): void { charges.push(deliveryId); }
export function chargeCount(deliveryId?: string): number {
  if (!deliveryId) return charges.length;
  return charges.filter((id) => id === deliveryId).length;
}
