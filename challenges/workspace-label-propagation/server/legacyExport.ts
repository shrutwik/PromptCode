export function exportTicketCsv(rows: { id: string; title: string }[]): string {
  return ['id,title', ...rows.map((r) => `${r.id},${r.title}`)].join('\n');
}
