import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { Category, ProductSummary } from '../api/types';
import { ProductCard } from '../components/Cards';
import { Alert, Empty, Spinner } from '../components/common';
import { useAuth } from '../lib/auth';
import { useApi } from '../lib/useApi';
import './store.css';

type Sort = 'relevance' | 'price-asc' | 'price-desc' | 'member';

export default function Store() {
  const [params, setParams] = useSearchParams();
  const category = params.get('category') || '';
  const food = params.get('food') === '1';
  const q = params.get('q') || '';
  const { user } = useAuth();
  const [sort, setSort] = useState<Sort>('relevance');
  const [onlyMember, setOnlyMember] = useState(false);
  const query = new URLSearchParams();
  if (category) query.set('category', category);
  if (food) query.set('food', '1');
  if (q) query.set('q', q);
  const products = useApi<ProductSummary[]>(`/catalog/products/?${query.toString()}`);
  const categories = useApi<Category[]>('/catalog/categories/');
  const current = categories.data?.find((c) => c.slug === category);

  const hasMember = (p: ProductSummary) => p.from_member_price_cents !== null
    || (p.from_price_cents !== null && p.from_list_price_cents !== null && p.from_price_cents < p.from_list_price_cents);
  const list = (products.data || []).filter((p) => !onlyMember || hasMember(p));
  const price = (p: ProductSummary) => p.from_price_cents ?? Number.MAX_SAFE_INTEGER;
  const sorted = sort === 'relevance' ? list : [...list].sort((a, b) => {
    if (sort === 'price-asc') return price(a) - price(b);
    if (sort === 'price-desc') return price(b) - price(a);
    return Number(hasMember(b)) - Number(hasMember(a));
  });

  const title = q ? `Resultados para “${q}”` : food ? 'Ração recorrente' : current?.name || 'Todos os produtos';
  const go = (next: Record<string, string>) => setParams(next, { replace: true });

  return (
    <div className="wrap shop">
      <nav className="shop__crumbs small muted" aria-label="Trilha">
        <Link to="/">Início</Link> / <Link to="/loja">Loja</Link>{(current || food) && <> / <span>{current?.name || 'Ração recorrente'}</span></>}
      </nav>
      <header className="shop__head">
        <h1>{title}</h1>
        {food && <p className="muted">Escolha a ração e a frequência. A recorrência mantém SKU e quantidade, com calendário próprio. Nunca trocamos marca ou fórmula automaticamente.</p>}
      </header>

      {!user?.is_member && (
        <Link to="/planos" className="shop__club">
          <span><strong>Preço de membro:</strong> quem assina o Club paga menos nos produtos marcados.</span>
          <span className="shop__club-cta">Conhecer o Club</span>
        </Link>
      )}

      <div className="shop__layout">
        <aside className="shop__side" aria-label="Filtros">
          <p className="shop__side-title">Categorias</p>
          <ul className="shop__cats">
            <li><button type="button" className={!category && !food ? 'is-on' : ''} onClick={() => go(q ? { q } : {})}>Todos os produtos</button></li>
            {categories.data?.map((c) => (
              <li key={c.slug}><button type="button" className={category === c.slug ? 'is-on' : ''} onClick={() => go({ category: c.slug })}>{c.name}</button></li>
            ))}
            <li><button type="button" className={food ? 'is-on' : ''} onClick={() => go({ food: '1' })}>Ração recorrente</button></li>
          </ul>
          <label className="check shop__member">
            <input type="checkbox" checked={onlyMember} onChange={(e) => setOnlyMember(e.target.checked)} />
            Só produtos com preço de membro
          </label>
        </aside>

        <section className="shop__results" aria-label="Produtos">
          <div className="shop__bar">
            <p className="small muted" aria-live="polite">{products.data ? `${sorted.length} ${sorted.length === 1 ? 'produto' : 'produtos'}` : ''}</p>
            <label className="shop__sort small">
              <span>Ordenar por</span>
              <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
                <option value="relevance">Destaques</option>
                <option value="member">Preço de membro primeiro</option>
                <option value="price-asc">Menor preço</option>
                <option value="price-desc">Maior preço</option>
              </select>
            </label>
          </div>
          {products.loading && <Spinner />}
          {products.error && <Alert tone="error">{products.error.message}</Alert>}
          {products.data && sorted.length === 0 && <Empty title="Nada por aqui ainda">Tente outra categoria ou busca.</Empty>}
          {sorted.length > 0 && <div className="shop__grid">{sorted.map((p) => <ProductCard key={p.slug} product={p} />)}</div>}
        </section>
      </div>
    </div>
  );
}
