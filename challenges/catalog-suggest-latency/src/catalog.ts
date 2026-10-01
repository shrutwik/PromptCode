export interface Product {
  id: string; title: string; category: string; popularity: number; tokens: string[];
}
export function buildCatalog(size: number): Product[] {
  const categories = ['kitchen', 'garden', 'tools', 'apparel', 'electronics'];
  const out: Product[] = [];
  for (let i = 0; i < size; i++) {
    const category = categories[i % categories.length];
    const title = `${category} item ${i}`;
    out.push({ id: `p_${i}`, title, category, popularity: (i * 37) % 1000, tokens: title.toLowerCase().split(/\s+/) });
  }
  return out;
}
