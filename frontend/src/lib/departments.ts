import type { Department, ProductSummary } from '../api/types';

/** Cor da ilustração por departamento da loja. */
const HUE: Record<string, string> = {
  alimentos: 'var(--terra)', 'higiene-e-cuidado': '#6f7f5a', mordedores: '#8b5a2b', brinquedos: 'var(--patinha)',
  acessorios: 'var(--fucinho)',
};

export function departmentOf(product: ProductSummary): string | null {
  const sc = product.store_category;
  if (!sc) return null;
  return sc.parent?.slug ?? sc.slug;
}

export function hueFor(slug: string | null | undefined) {
  return (slug && HUE[slug]) || 'var(--terra)';
}

export function productLabel(product: ProductSummary) {
  return product.store_category?.name ?? product.category.name;
}

/** Encontra departamento e subcategoria a partir de um slug de seção (pode ser qualquer um dos dois). */
export function findSection(departments: Department[] | null, slug: string) {
  for (const d of departments || []) {
    if (d.slug === slug) return { department: d, sub: null };
    const sub = d.children.find((c) => c.slug === slug);
    if (sub) return { department: d, sub };
  }
  return { department: null, sub: null };
}
