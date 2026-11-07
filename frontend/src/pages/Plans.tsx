import type { Plan } from '../api/types';
import { PlanCard } from '../components/Cards';
import { Alert, Spinner } from '../components/common';
import { useApi } from '../lib/useApi';

export default function Plans() {
  const { data, loading, error } = useApi<Plan[]>('/plans/');
  const categories = Array.from(
    new Map((data || []).flatMap((p) => p.composition?.lines || []).map((l) => [l.category, l.category_name])).entries(),
  );

  return (
    <div className="wrap page">
      <header className="page__head">
        <p className="eyebrow">Planos</p>
        <h1>Escolha sua Vila</h1>
        <p>Assinatura mensal com cobrança recorrente. Cada cão cadastrado recebe o próprio kit, com lista identificada por cão. As quantidades são unidades comerciais de produtos no kit.</p>
      </header>
      {loading && <Spinner />}
      {error && <Alert tone="error">{error.message}</Alert>}
      {data && (
        <>
          <div className="grid grid--2">{data.map((p) => <PlanCard key={p.code} plan={p} />)}</div>

          <section className="card" style={{ marginTop: '2.5rem', overflowX: 'auto' }} aria-labelledby="comparar">
            <h2 id="comparar" style={{ fontSize: 'var(--step-1)', marginBottom: '1rem' }}>Compare as composições</h2>
            <table className="compare">
              <thead>
                <tr><th scope="col">Categoria</th>{data.map((p) => <th scope="col" key={p.code}>{p.name}</th>)}</tr>
              </thead>
              <tbody>
                {categories.map(([slug, name]) => (
                  <tr key={slug}>
                    <th scope="row">{name}</th>
                    {data.map((p) => <td key={p.code}>{p.composition?.lines.find((l) => l.category === slug)?.quantity ?? 0}</td>)}
                  </tr>
                ))}
                <tr className="compare__total">
                  <th scope="row">Total de itens</th>
                  {data.map((p) => <td key={p.code}>{p.composition?.total_items ?? '—'}</td>)}
                </tr>
              </tbody>
            </table>
            <p className="small muted" style={{ marginTop: '1rem' }}>Refeição Natural: o cadastro de cada item informa peso, embalagem e conservação. A curadoria respeita as restrições declaradas, mas não substitui orientação veterinária.</p>
          </section>
        </>
      )}
      <style>{`
        .compare { width: 100%; border-collapse: collapse; min-width: 28rem; }
        .compare th, .compare td { text-align: left; padding: 0.6rem 0.5rem; border-bottom: 1px solid var(--line); }
        .compare td { font-weight: 700; text-align: center; }
        .compare thead th:not(:first-child) { text-align: center; }
        .compare__total th, .compare__total td { font-weight: 800; border-bottom: 0; }
      `}</style>
    </div>
  );
}
