import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { Department, ProductSummary } from '../api/types';
import { ProductCard } from '../components/Cards';
import { Alert, Empty, Spinner } from '../components/common';
import { useAuth } from '../lib/auth';
import { findSection } from '../lib/departments';
import { useApi } from '../lib/useApi';
import './store.css';

type Sort = 'relevance' | 'price-asc' | 'price-desc' | 'member';

export default function Store() {
  const [params, setParams] = useSearchParams();
  const section = params.get('section') || '';
  const food = params.get('food') === '1';
  const q = params.get('q') || '';
  const { user } = useAuth();
  const [sort, setSort] = useState<Sort>('relevance');
  const [onlyMember, setOnlyMember] = useState(false);
  const query = new URLSearchParams();
  if (section) query.set('section', section);
  if (food) query.set('food', '1');
  if (q) query.set('q', q);
  const products = useApi<ProductSummary[]>(`/catalog/products/?${query.toString()}`);
  const departments = useApi<Department[]>('/catalog/departments/');
  const { department, sub } = findSection(departments.data, section);

  const hasMember = (p: ProductSummary) => p.from_member_price_cents !== null
    || (p.from_price_cents !== null && p.from_list_price_cents !== null && p.from_price_cents < p.from_list_price_cents);
  const list = (products.data || []).filter((p) => !onlyMember || hasMember(p));
  const price = (p: ProductSummary) => p.from_price_cents ?? Number.MAX_SAFE_INTEGER;
  const sorted = sort === 'relevance' ? list : [...list].sort((a, b) => {
    if (sort === 'price-asc') return price(a) - price(b);
    if (sort === 'price-desc') return price(b) - price(a);
    return Number(hasMember(b)) - Number(hasMember(a));
  });

  const title = q ? `Resultados para “${q}”` : food ? 'Ração recorrente' : sub?.name || department?.name || 'Todos os produtos';
  const go = (next: Record<string, string>) => setParams(next, { replace: true });
  const openDept = department?.slug ?? (food ? 'alimentos' : null);

  return (
    <div className="wrap shop">
      <nav className="shop__crumbs small muted" aria-label="Trilha">
        <Link to="/">Início</Link> / <Link to="/loja">Loja</Link>
        {department && <> / {sub ? <Link to={`/loja?section=${department.slug}`}>{department.name}</Link> : <span>{department.name}</span>}</>}
        {sub && <> / <span>{sub.name}</span></>}
        {food && <> / <Link to="/loja?section=alimentos">Alimentos</Link> / <span>Ração recorrente</span></>}
      </nav>
      <header className="shop__head">
        <h1>{title}</h1>
        {food && <p className="muted">Escolha a ração e a frequência. A recorrência mantém SKU e quantidade, com calendário próprio. Nunca trocamos marca ou fórmula automaticamente.</p>}
      </header>

      {department && !sub && department.children.length > 0 && (
        <div className="shop__subs" role="group" aria-label={`Subcategorias de ${department.name}`}>
          {department.children.map((c) => (
            <button key={c.slug} type="button" onClick={() => go({ section: c.slug })}>{c.name}</button>
          ))}
        </div>
      )}

      {!user?.is_member && (
        <Link to="/planos" className="shop__club">
          <span><strong>Preço de membro:</strong> quem assina o Club paga menos nos produtos marcados.</span>
          <span className="shop__club-cta">Conhecer o Club</span>
        </Link>
      )}

      <div className="shop__layout">
        <aside className="shop__side" aria-label="Filtros">
          <p className="shop__side-title">Categorias</p>
          <ul className="shop__tree">
            <li><button type="button" className={!section && !food ? 'is-on' : ''} onClick={() => go(q ? { q } : {})}>Todos os produtos</button></li>
            {departments.data?.map((d) => (
              <li key={d.slug}>
                <button type="button" className={`shop__dept ${section === d.slug ? 'is-on' : ''}`} onClick={() => go({ section: d.slug })}>{d.name}</button>
                {openDept === d.slug && (d.children.length > 0 || d.slug === 'alimentos') && (
                  <ul className="shop__subtree">
                    {d.children.map((c) => (
                      <li key={c.slug}><button type="button" className={section === c.slug ? 'is-on' : ''} onClick={() => go({ section: c.slug })}>{c.name}</button></li>
                    ))}
                    {d.slug === 'alimentos' && <li><button type="button" className={food ? 'is-on' : ''} onClick={() => go({ food: '1' })}>Ração recorrente</button></li>}
                  </ul>
                )}
              </li>
            ))}
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
          {products.data && sorted.length === 0 && <Empty title="Nada por aqui ainda">Estamos escolhendo os produtos desta categoria. Volte em breve.</Empty>}
          {sorted.length > 0 && <div className="shop__grid">{sorted.map((p) => <ProductCard key={p.slug} product={p} />)}</div>}
        </section>
      </div>
    </div>
  );
}
