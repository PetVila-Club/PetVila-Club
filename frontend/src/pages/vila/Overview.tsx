import { Link } from 'react-router-dom';
import type { Delivery, Dog, Payment, Subscription } from '../../api/types';
import { Alert, Spinner, StatusBadge } from '../../components/common';
import { date, money } from '../../lib/format';
import { useApi } from '../../lib/useApi';

export default function Overview() {
  const subs = useApi<Subscription[]>('/me/subscriptions/');
  const dogs = useApi<Dog[]>('/me/dogs/');
  const deliveries = useApi<Delivery[]>('/me/deliveries/');
  const payments = useApi<Payment[]>('/me/payments/');

  if (subs.loading || dogs.loading) return <Spinner />;
  const pending = (payments.data || []).filter((p) => ['PENDING', 'OVERDUE'].includes(p.status));
  const incomplete = (dogs.data || []).filter((d) => d.is_active && d.missing_fields.length);
  const nextDelivery = (deliveries.data || []).find((d) => !['delivered', 'canceled'].includes(d.status));

  return (
    <>
      {pending.length > 0 && (
        <Alert tone="warn">
          Você tem {pending.length} cobrança(s) aguardando pagamento. <Link to="/minha-vila/pagamentos">Ver pagamentos</Link>
        </Alert>
      )}
      {incomplete.map((d) => (
        <Alert tone="warn" key={d.id}>
          O perfil de {d.name} está incompleto ({d.missing_fields.join(', ')}). Sem isso a curadoria não pode ser liberada. <Link to="/minha-vila/caes">Completar</Link>
        </Alert>
      ))}
      <div className="grid grid--3">
        <div className="card stack">
          <p className="eyebrow">Assinaturas</p>
          <p className="price">{(subs.data || []).filter((s) => s.status === 'active').length} ativa(s)</p>
          <Link to="/minha-vila/assinaturas">Gerenciar</Link>
        </div>
        <div className="card stack">
          <p className="eyebrow">Cães</p>
          <p className="price">{(dogs.data || []).filter((d) => d.is_active).length}</p>
          <Link to="/minha-vila/caes">Ver perfis</Link>
        </div>
        <div className="card stack">
          <p className="eyebrow">Próxima entrega</p>
          {nextDelivery ? (
            <>
              <p><strong>{nextDelivery.reference}</strong></p>
              <StatusBadge status={nextDelivery.status} label={nextDelivery.status_label} />
            </>
          ) : <p className="muted">Nenhuma entrega em andamento.</p>}
          <Link to="/minha-vila/entregas">Acompanhar</Link>
        </div>
      </div>
      {(subs.data || []).filter((s) => s.status !== 'canceled').map((s) => (
        <div className="card list__item" key={s.id}>
          <div>
            <strong>{s.plan_name || s.sku_name}{s.dog_name ? ` · ${s.dog_name}` : ''}</strong>
            <p className="small muted">{s.number} · {money(s.total_per_cycle_cents)}/ciclo · próxima cobrança {date(s.next_billing_date)}</p>
          </div>
          <StatusBadge status={s.status} label={s.status_label} />
        </div>
      ))}
      {!subs.data?.length && (
        <div className="card card--dark stack">
          <h2 style={{ fontSize: 'var(--step-1)' }}>Ainda sem assinatura</h2>
          <p>Conheça os planos e receba uma curadoria por mês para cada cão.</p>
          <Link to="/planos" className="btn btn--brand">Ver planos</Link>
        </div>
      )}
    </>
  );
}
