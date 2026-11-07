import { Link, useParams } from 'react-router-dom';
import type { Order } from '../api/types';
import { Alert, Spinner, StatusBadge } from '../components/common';
import { PaymentBox } from '../components/PaymentBox';
import { money } from '../lib/format';
import { useApi } from '../lib/useApi';

export default function OrderConfirmation() {
  const { id } = useParams();
  const { data: order, loading, error, reload } = useApi<Order>(`/me/orders/${id}/`);

  if (loading && !order) return <Spinner />;
  if (error || !order) return <div className="wrap page"><Alert tone="error">{error?.message || 'Pedido não encontrado.'}</Alert></div>;

  return (
    <div className="wrap page">
      <header className="page__head">
        <p className="eyebrow">Pedido {order.number}</p>
        <h1>{order.payment?.is_paid ? 'Pagamento confirmado!' : 'Pedido recebido'}</h1>
        <p>
          Situação real do pedido: <StatusBadge status={order.status} label={order.status_label} />{' '}
          {!order.payment?.is_paid && 'A separação começa assim que o pagamento for confirmado pelo provedor.'}
        </p>
      </header>
      <div className="grid grid--2" style={{ alignItems: 'start' }}>
        {order.payment && <PaymentBox payment={order.payment} onChange={() => reload()} />}
        <section className="card stack">
          <h2 style={{ fontSize: 'var(--step-1)' }}>Itens</h2>
          <ul className="list">
            {order.lines.map((l) => (
              <li className="list__item small" key={l.id}><span>{l.quantity} × {l.product_name} <span className="muted">({l.sku_code})</span></span><span>{money(l.total_cents)}</span></li>
            ))}
          </ul>
          <div className="summary">
            <div className="summary__row"><span>Frete</span><span>{money(order.shipping_cents)}</span></div>
            {order.discount_cents > 0 && <div className="summary__row"><span>Preço de membro</span><span>− {money(order.discount_cents)}</span></div>}
            <div className="summary__row summary__row--total"><span>Total</span><span>{money(order.total_cents)}</span></div>
          </div>
          <Link to="/minha-vila/pedidos" className="btn btn--ghost">Acompanhar em Minha Vila</Link>
        </section>
      </div>
    </div>
  );
}
