import { Link, useSearchParams } from 'react-router-dom';
import type { Subscription } from '../api/types';
import { Alert, Spinner, StatusBadge } from '../components/common';
import { PaymentBox } from '../components/PaymentBox';
import { money } from '../lib/format';
import { useApi } from '../lib/useApi';

export default function SubscriptionConfirmation() {
  const [params] = useSearchParams();
  const ids = (params.get('ids') || '').split(',').filter(Boolean);
  const { data, loading, reload } = useApi<Subscription[]>('/me/subscriptions/');

  if (loading && !data) return <Spinner />;
  const subs = (data || []).filter((s) => ids.includes(String(s.id)));
  if (!subs.length) return <div className="wrap page"><Alert tone="error">Não encontramos esta contratação. Veja em Minha Vila.</Alert></div>;

  return (
    <div className="wrap page">
      <header className="page__head">
        <p className="eyebrow">Contratação registrada</p>
        <h1>Bem-vindos à Vila.</h1>
        <p>Cada assinatura tem número próprio e cobrança própria. O estado abaixo é o real: a curadoria só começa depois que o pagamento é confirmado.</p>
      </header>
      <div className="grid grid--2">
        {subs.map((s) => (
          <section className="card stack" key={s.id}>
            <div className="summary__row">
              <h2 style={{ fontSize: 'var(--step-1)' }}>{s.plan_name || s.sku_name}{s.dog_name ? ` · ${s.dog_name}` : ''}</h2>
              <StatusBadge status={s.status} label={s.status_label} />
            </div>
            <p className="small muted">Assinatura {s.number} · {money(s.total_per_cycle_cents)} por ciclo</p>
            {s.pending_payment ? <PaymentBox payment={s.pending_payment} onChange={() => reload()} /> : (
              s.status === 'active' ? <Alert tone="ok">Pagamento confirmado. A curadoria do primeiro kit já começou.</Alert>
                : <Alert tone="info">A cobrança está sendo gerada pelo provedor. Atualize em instantes.</Alert>
            )}
          </section>
        ))}
      </div>
      <div className="btn-row" style={{ marginTop: '2rem' }}>
        <Link to="/minha-vila/assinaturas" className="btn">Ir para Minha Vila</Link>
      </div>
    </div>
  );
}
