import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Quote } from '../api/types';
import { ClubCartOffer } from '../components/Club';
import { Alert, Empty, Spinner } from '../components/common';
import { useCart } from '../lib/cart';
import { money } from '../lib/format';
import { errorMessage } from '../lib/useApi';

export default function Cart() {
  const cart = useCart();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!cart.items.length) {
      setQuote(null);
      return;
    }
    api<Quote>('/checkout/quote/', { body: { items: cart.items.map(({ sku_id, quantity }) => ({ sku_id, quantity })) } })
      .then((q) => { setQuote(q); setError(''); })
      .catch((err) => setError(errorMessage(err)));
  }, [cart.items]);

  if (!cart.items.length) {
    return <div className="wrap page"><Empty title="Seu carrinho está vazio"><Link to="/loja" className="btn">Ir para a loja</Link></Empty></div>;
  }

  return (
    <div className="wrap page">
      <header className="page__head">
        <h1>Carrinho</h1>
        <p>Itens avulsos da loja. Assinaturas de kit e ração têm contratação própria, com condições e cobranças separadas.</p>
      </header>
      {error && <Alert tone="error">{error}</Alert>}
      {!quote && !error && <Spinner />}
      {quote && (
        <div className="grid grid--2" style={{ alignItems: 'start' }}>
          <ul className="list card">
            {cart.items.map((item) => {
              const line = quote.lines.find((l) => l.sku_id === item.sku_id);
              return (
                <li className="list__item" key={item.sku_id}>
                  <div>
                    <strong>{line?.name || item.name}</strong>
                    <p className="small muted">
                      {line ? `${money(line.unit_price_cents)} cada` : 'Indisponível'}
                      {line && line.unit_price_cents < line.list_price_cents ? ' · preço de membro' : ''}
                    </p>
                  </div>
                  <div className="btn-row">
                    <div className="qty" aria-label={`Quantidade de ${item.name}`}>
                      <button type="button" aria-label="Diminuir" onClick={() => cart.setQuantity(item.sku_id, item.quantity - 1)}>−</button>
                      <span>{item.quantity}</span>
                      <button type="button" aria-label="Aumentar" onClick={() => cart.setQuantity(item.sku_id, item.quantity + 1)}>+</button>
                    </div>
                    <button type="button" className="btn--link small" onClick={() => cart.remove(item.sku_id)}>Remover</button>
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="stack">
          <aside className="card card--strong stack">
            <h2 style={{ fontSize: 'var(--step-1)' }}>Resumo</h2>
            <div className="summary">
              <div className="summary__row"><span>Subtotal</span><span>{money(quote.subtotal_cents)}</span></div>
              {quote.discount_cents > 0 && <div className="summary__row"><span>Preço de membro</span><span>− {money(quote.discount_cents)}</span></div>}
              <div className="summary__row"><span>Frete</span><span className="muted">calculado no checkout</span></div>
            </div>
            {quote.problems.map((p) => <Alert tone="warn" key={p}>{p}</Alert>)}
            <Link to="/checkout" className="btn btn--brand btn--block" aria-disabled={quote.problems.length > 0}
              onClick={(e) => { if (quote.problems.length) e.preventDefault(); }}>Continuar para o checkout</Link>
          </aside>
          <ClubCartOffer quote={quote} />
          </div>
        </div>
      )}
    </div>
  );
}
