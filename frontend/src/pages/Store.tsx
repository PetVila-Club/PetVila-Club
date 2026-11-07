import { useSearchParams } from 'react-router-dom';
import type { Category, ProductSummary } from '../api/types';
import { ProductCard } from '../components/Cards';
import { Alert, Empty, Spinner } from '../components/common';
import { useAuth } from '../lib/auth';
import { useApi } from '../lib/useApi';

export default function Store() {
  const [params, setParams] = useSearchParams();
  const category = params.get('category') || '';
  const food = params.get('food') === '1';
  const q = params.get('q') || '';
  const { user } = useAuth();
  const query = new URLSearchParams();
  if (category) query.set('category', category);
  if (food) query.set('food', '1');
  if (q) query.set('q', q);
  const products = useApi<ProductSummary[]>(`/catalog/products/?${query.toString()}`);
  const categories = useApi<Category[]>('/catalog/categories/');

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (key === 'category') next.delete('food');
    setParams(next, { replace: true });
  };

  return (
    <div className="wrap page">
      <header className="page__head">
        <p className="eyebrow">PetVila Store</p>
        <h1>{food ? 'Ração recorrente' : 'Loja'}</h1>
        <p>{food
          ? 'Escolha a ração e a frequência. A recorrência preserva SKU e quantidade, com calendário independente do kit. Nunca trocamos marca ou fórmula automaticamente.'
          : 'Aberta para todos. Membros do Club com assinatura ativa veem o preço de membro em produtos selecionados.'}</p>
        {user?.is_member && <Alert tone="ok">Você é membro: o preço de membro já aparece nos produtos elegíveis.</Alert>}
      </header>

      <div className="store-filters">
        <label className="field">
          <span>Buscar</span>
          <input type="search" defaultValue={q} placeholder="Ex.: snack, shampoo" onKeyDown={(e) => { if (e.key === 'Enter') update('q', (e.target as HTMLInputElement).value); }} />
        </label>
        <div className="chips" role="group" aria-label="Categorias">
          <label className="chip"><input type="radio" name="cat" checked={!category && !food} onChange={() => { setParams({}, { replace: true }); }} />Tudo</label>
          <label className="chip"><input type="radio" name="cat" checked={food} onChange={() => setParams({ food: '1' }, { replace: true })} />Ração recorrente</label>
          {categories.data?.map((c) => (
            <label className="chip" key={c.slug}><input type="radio" name="cat" checked={category === c.slug} onChange={() => update('category', c.slug)} />{c.name}</label>
          ))}
        </div>
      </div>

      {products.loading && <Spinner />}
      {products.error && <Alert tone="error">{products.error.message}</Alert>}
      {products.data && products.data.length === 0 && <Empty title="Nada por aqui ainda">Tente outra categoria ou busca.</Empty>}
      {products.data && products.data.length > 0 && (
        <div className="grid grid--4">{products.data.map((p) => <ProductCard key={p.slug} product={p} />)}</div>
      )}
      <style>{`.store-filters{display:grid;gap:1rem;margin-bottom:2rem}.store-filters .field{max-width:24rem}`}</style>
    </div>
  );
}
