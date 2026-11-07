import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { Subscription } from '../../api/types';
import { Alert, Empty, Spinner, StatusBadge } from '../../components/common';
import { PaymentBox } from '../../components/PaymentBox';
import { BILLING_LABEL, date, money } from '../../lib/format';
import { errorMessage, useApi } from '../../lib/useApi';

function SubscriptionCard({ sub, onChange }: { sub: Subscription; onChange: () => void }) {
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const act = async (action: 'cancel' | 'pause' | 'resume') => {
    setBusy(true);
    setError('');
    try {
      const res = await api<{ message: string }>(`/me/subscriptions/${sub.id}/${action}/`, { body: {} });
      setMessage(res.message);
      setConfirming(false);
      onChange();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const open = !['canceled', 'ended'].includes(sub.status);
  return (
    <article className="card stack">
      <div className="list__item">
        <div>
          <h3>{sub.plan_name || sub.sku_name}{sub.dog_name ? ` · ${sub.dog_name}` : ''}</h3>
          <p className="small muted">{sub.kind_label} · {sub.number}</p>
        </div>
        <StatusBadge status={sub.status} label={sub.status_label} />
      </div>
      <div className="summary small">
        <div className="summary__row"><span>Valor por ciclo</span><strong>{money(sub.total_per_cycle_cents)}</strong></div>
        {sub.kind === 'food' && <div className="summary__row"><span>Entrega</span><span>{sub.quantity} un. a cada {sub.frequency_days} dias</span></div>}
        {sub.commitment_months && <div className="summary__row"><span>Ciclo contratado</span><span>{sub.commitment_months} meses</span></div>}
        <div className="summary__row"><span>Pagamento</span><span>{BILLING_LABEL[sub.billing_type]}</span></div>
        <div className="summary__row"><span>Próxima cobrança</span><span>{date(sub.next_billing_date)}</span></div>
        {sub.next_cutoff_date && open && <div className="summary__row"><span>Data de corte para mudanças</span><span>{date(sub.next_cutoff_date)}</span></div>}
        {sub.cancel_effective_date && <div className="summary__row"><span>Cancelamento efetivo em</span><strong>{date(sub.cancel_effective_date)}</strong></div>}
      </div>
      {sub.pending_payment && <PaymentBox payment={sub.pending_payment} onChange={onChange} />}
      {sub.cycles.length > 0 && (
        <details>
          <summary className="small" style={{ cursor: 'pointer', fontWeight: 600 }}>Histórico de ciclos ({sub.cycles.length})</summary>
          <ul className="list small" style={{ marginTop: '0.75rem' }}>
            {sub.cycles.map((c) => (
              <li className="list__item" key={c.id}>
                <span>{c.code} · cobrança {date(c.billing_date)}</span>
                <StatusBadge status={c.status} label={c.status_label} />
              </li>
            ))}
          </ul>
        </details>
      )}
      {message && <Alert tone="ok">{message}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      {open && !sub.cancel_effective_date && (
        <div className="btn-row">
          {sub.status === 'active' && <button type="button" className="btn btn--sm btn--ghost" disabled={busy} onClick={() => act('pause')}>Pausar</button>}
          {sub.status === 'paused' && <button type="button" className="btn btn--sm" disabled={busy} onClick={() => act('resume')}>Retomar</button>}
          {!confirming ? (
            <button type="button" className="btn--link small" onClick={() => setConfirming(true)}>Cancelar assinatura</button>
          ) : (
            <div className="alert alert--warn stack" style={{ width: '100%' }}>
              <p>Confirma o cancelamento? Antes da data de corte ({date(sub.next_cutoff_date)}) nenhuma nova cobrança é feita. Depois dela, o ciclo já processado é entregue e o cancelamento vale em seguida. Ciclos pagos são sempre entregues.</p>
              <div className="btn-row">
                <button type="button" className="btn btn--sm" disabled={busy} onClick={() => act('cancel')}>Confirmar cancelamento</button>
                <button type="button" className="btn btn--sm btn--ghost" onClick={() => setConfirming(false)}>Manter assinatura</button>
              </div>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export default function Subscriptions() {
  const { data, loading, reload } = useApi<Subscription[]>('/me/subscriptions/');
  if (loading) return <Spinner />;
  return (
    <>
      <h2 style={{ fontSize: 'var(--step-1)' }}>Assinaturas</h2>
      {!data?.length && <Empty title="Nenhuma assinatura"><Link to="/planos" className="btn">Ver planos</Link></Empty>}
      {data?.map((s) => <SubscriptionCard key={s.id} sub={s} onChange={reload} />)}
    </>
  );
}
