import type { Plan } from '../api/types';
import { PlanCard } from '../components/Cards';
import { Alert, Spinner } from '../components/common';
import { useApi } from '../lib/useApi';

export default function Plans() {
  const { data, loading, error } = useApi<Plan[]>('/plans/');

  return (
    <div className="wrap page">
      <header className="page__head">
        <h1>Escolha sua Vila</h1>
        <p>Assinatura mensal com cobrança recorrente. Cada cão cadastrado recebe o próprio kit, montado a partir do perfil dele. Enquanto a assinatura estiver ativa, você paga preço de membro nos produtos marcados da loja.</p>
      </header>
      {loading && <Spinner />}
      {error && <Alert tone="error">{error.message}</Alert>}
      {data && <div className="grid grid--2">{data.map((p) => <PlanCard key={p.code} plan={p} />)}</div>}
      <p className="small muted" style={{ marginTop: '1.5rem' }}>A curadoria respeita as restrições declaradas de cada cão, mas não substitui orientação veterinária.</p>
    </div>
  );
}
