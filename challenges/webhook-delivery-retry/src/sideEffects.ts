const charges: string[] = [];
export function resetCharges(): void { charges.length = 0; }
export function recordCharge(deliveryId: string): void { charges.push(deliveryId); }
export function chargeCount(deliveryId?: string): number {
  if (!deliveryId) return charges.length;
  return charges.filter((id) => id === deliveryId).length;
}
