import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, ApiError, newIdempotencyKey } from '../api/client';
import type { Address, Order, Quote } from '../api/types';
import { AddressPicker, BillingPicker, CpfGate } from '../components/CheckoutParts';
import { ClubCartOffer } from '../components/Club';
import { Alert, Empty, Spinner } from '../components/common';
import { useAuth } from '../lib/auth';
import { useCart } from '../lib/cart';
import { money } from '../lib/format';
import { errorMessage } from '../lib/useApi';

export default function Checkout() {
  const cart = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();
  const key = useRef(newIdempotencyKey());
  const [addressId, setAddressId] = useState<number | null>(null);
  const [address, setAddress] = useState<Address | null>(null);
  const [billing, setBilling] = useState('PIX');
  const [quote, setQuote] = useState<Quote | null>(null);
  const [accept, setAccept] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const items = cart.items.map(({ sku_id, quantity }) => ({ sku_id, quantity }));

  useEffect(() => {
    if (!address || !items.length) return;
    api<Quote>('/checkout/quote/', { body: { items, cep: address.cep } })
      .then((q) => { setQuote(q); setError(''); })
      .catch((err) => setError(errorMessage(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [address, cart.items]);

  if (!cart.items.length) return <div className="wrap page"><Empty title="Carrinho vazio"><Link className="btn" to="/loja">Ir para a loja</Link></Empty></div>;

  const confirm = async () => {
    if (!quote || !addressId) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const order = await api<Order>('/checkout/store/', {
        body: { items, address_id: addressId, billing_type: billing, expected_total_cents: quote.total_cents, accept_terms: accept },
        headers: { 'Idempotency-Key': key.current },
      });
      cart.clear();
      navigate(`/pedido/${order.id}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.data.quote) {
        // LOJ-02: valores mudaram (ex.: perdeu elegibilidade de membro). Exige nova ciência.
        setQuote(err.data.quote as Quote);
        setAccept(false);
        setNotice(err.message);
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wrap page">
      <header className="page__head">
        <h1>Checkout</h1>
        <p>Compra avulsa da loja. Confira produtos, frete, prazo e total antes de confirmar.</p>
      </header>
      <div className="grid grid--2" style={{ alignItems: 'start' }}>
        <div className="stack" style={{ ['--stack' as string]: '1.75rem' }}>
          {quote && <ClubCartOffer quote={quote} compact />}
          <CpfGate />
          <AddressPicker value={addressId} onChange={(id, a) => { setAddressId(id); setAddress(a); }} />
          <BillingPicker value={billing} onChange={setBilling} />
        </div>
        <aside className="card card--strong stack" aria-labelledby="resumo">
          <h2 id="resumo" style={{ fontSize: 'var(--step-1)' }}>Resumo do pedido</h2>
          {!quote && <Spinner />}
          {quote && (
            <>
              <ul className="list">
                {quote.lines.map((l) => (
                  <li className="list__item small" key={l.sku_id}>
                    <span>{l.quantity} × {l.name}</span>
                    <span>{money(l.total_cents)}</span>
                  </li>
                ))}
              </ul>
              <div className="summary">
                <div className="summary__row"><span>Produtos</span><span>{money(quote.subtotal_cents)}</span></div>
                {quote.discount_cents > 0 && <div className="summary__row"><span>Preço de membro</span><span>− {money(quote.discount_cents)}</span></div>}
                <div className="summary__row"><span>Frete{quote.zone ? ` (${quote.zone})` : ''}</span><span>{money(quote.shipping_cents)}</span></div>
                {quote.eta_days && <div className="summary__row small muted"><span>Prazo estimado</span><span>{quote.eta_days} dias úteis após a confirmação</span></div>}
                <div className="summary__row summary__row--total"><span>Total</span><span>{money(quote.total_cents)}</span></div>
                <p className="small muted">Compra única, sem cobrança recorrente.</p>
              </div>
              {quote.problems.map((p) => <Alert tone="warn" key={p}>{p}</Alert>)}
              {notice && <Alert tone="warn">{notice}</Alert>}
              <label className="check">
                <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} />
                <span>Li e aceito os <Link to="/termos" target="_blank">termos de compra</Link> e a <Link to="/privacidade" target="_blank">política de privacidade</Link>.</span>
              </label>
              {error && <Alert tone="error">{error}</Alert>}
              <button type="button" className="btn btn--brand btn--block" onClick={confirm}
                disabled={busy || !accept || !quote.can_checkout || !user?.cpf}>
                {busy ? 'Gerando cobrança…' : `Confirmar e pagar ${money(quote.total_cents)}`}
              </button>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
