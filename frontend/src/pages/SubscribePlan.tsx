import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, newIdempotencyKey } from '../api/client';
import type { Address, Dog, Order, Plan, Product, ProductSummary, Quote, SKU, Subscription } from '../api/types';
import { AddressPicker, BillingPicker, CpfGate } from '../components/CheckoutParts';
import { Alert, Spinner } from '../components/common';
import { DogForm } from '../components/Forms';
import { useAuth } from '../lib/auth';
import { useCart } from '../lib/cart';
import { money, SIZE_LABEL } from '../lib/format';
import { errorMessage, useApi } from '../lib/useApi';
import './subscribe.css';

interface FoodOption { product: Product; sku: SKU; list: number; member: number }

/** Preço de assinante da ração: o servidor aplica o menor entre preço de membro e preço cheio. */
function foodOptions(products: Product[]): FoodOption[] {
  return products.flatMap((product) => product.skus.filter((s) => s.sellable && s.list_price_cents !== null).map((sku) => {
    const list = sku.list_price_cents as number;
    const member = sku.member_price_cents && sku.member_price_cents < list ? sku.member_price_cents : list;
    return { product, sku, list, member };
  }));
}

export default function SubscribePlan() {
  const { code } = useParams();
  const [params] = useSearchParams();
  const { user } = useAuth();
  const cart = useCart();
  const navigate = useNavigate();
  const plan = useApi<Plan>(`/plans/${code}/`);
  const dogs = useApi<Dog[]>('/me/dogs/');
  const foods = useApi<ProductSummary[]>('/catalog/products/?food=1');
  const key = useRef(newIdempotencyKey());
  const orderKey = useRef(newIdempotencyKey());
  const [selected, setSelected] = useState<number[]>([]);
  const [commitment, setCommitment] = useState<number | null>(null);
  const [addressId, setAddressId] = useState<number | null>(null);
  const [address, setAddress] = useState<Address | null>(null);
  const [billing, setBilling] = useState('CREDIT_CARD');
  const [accept, setAccept] = useState(false);
  const [addingDog, setAddingDog] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [foodDetails, setFoodDetails] = useState<Product[]>([]);
  const [foodSku, setFoodSku] = useState<number | null>(null);
  const [foodQty, setFoodQty] = useState(1);
  const [takeCart, setTakeCart] = useState(params.get('carrinho') === '1');
  const [cartQuote, setCartQuote] = useState<Quote | null>(null);

  const cartItems = cart.items.map(({ sku_id, quantity }) => ({ sku_id, quantity }));

  useEffect(() => {
    const list = (foods.data || []).filter((p) => p.sellable);
    if (!list.length) return;
    Promise.all(list.map((p) => api<Product>(`/catalog/products/${p.slug}/`)))
      .then(setFoodDetails)
      .catch(() => setFoodDetails([]));
  }, [foods.data]);

  useEffect(() => {
    if (!cartItems.length || !address) { setCartQuote(null); return; }
    api<Quote>('/checkout/quote/', { body: { items: cartItems, cep: address.cep } })
      .then(setCartQuote)
      .catch(() => setCartQuote(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [address, cart.items]);

  if (plan.loading || dogs.loading) return <Spinner />;
  const p = plan.data;
  if (!p) return <div className="wrap page"><Alert tone="error">Plano não encontrado.</Alert></div>;
  if (!p.available || !p.offer) {
    return (
      <div className="wrap page stack">
        <h1>{p.name}</h1>
        <Alert tone="info">Este plano ainda não está disponível para contratação: o preço está em aprovação. Avisaremos quando abrir.</Alert>
        <Link to="/planos" className="btn btn--ghost">Ver planos</Link>
      </div>
    );
  }
  const offer = p.offer;
  const activeDogs = (dogs.data || []).filter((d) => d.is_active);
  const commitmentValue = commitment ?? offer.commitment_options[0] ?? null;
  const perDog = offer.price_cents + offer.shipping_cents;
  const toggle = (id: number) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const options = foodOptions(foodDetails);
  const food = options.find((o) => o.sku.id === foodSku) || null;
  const foodTotal = food ? food.member * foodQty : 0;

  // Itens do carrinho levados junto, já com preço de membro (o servidor confere na hora de fechar).
  const cartReady = Boolean(cartQuote && cartQuote.can_checkout && !cartQuote.member_pricing);
  const withCart = takeCart && cartReady && cartQuote !== null;
  const cartTotal = cartQuote ? cartQuote.member_merchandise_cents + cartQuote.shipping_cents : 0;
  const monthly = perDog * selected.length + foodTotal;

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await api<{ subscriptions: Subscription[] }>('/checkout/subscription/', {
        body: {
          plan: p.code, dog_ids: selected, address_id: addressId, billing_type: billing, commitment_months: commitmentValue,
          offer_id: offer.id, accept_terms: accept,
          food: food ? { sku_id: food.sku.id, quantity: foodQty, expected_price_cents: foodTotal } : null,
        },
        headers: { 'Idempotency-Key': key.current },
      });
      const next = new URLSearchParams({ ids: res.subscriptions.map((s) => s.id).join(',') });
      if (withCart) {
        try {
          const body = { items: cartItems, cep: address?.cep, subscription_key: key.current };
          const q = await api<Quote>('/checkout/quote/', { body });
          if (q.member_pricing && q.total_cents === cartTotal) {
            const order = await api<Order>('/checkout/store/', {
              body: { items: cartItems, address_id: addressId, billing_type: billing, expected_total_cents: q.total_cents, accept_terms: accept, subscription_key: key.current },
              headers: { 'Idempotency-Key': orderKey.current },
            });
            cart.clear();
            next.set('pedido', String(order.id));
          } else {
            next.set('carrinho', 'revisar');
          }
        } catch {
          next.set('carrinho', 'revisar');
        }
      }
      navigate(`/assinatura/confirmada?${next.toString()}`, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      plan.reload();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wrap page">
      <header className="page__head">
        <h1>{p.name}</h1>
        <p>{p.tagline} Um kit por mês para cada cão, com curadoria humana a partir do perfil dele.</p>
      </header>
      <div className="grid grid--2" style={{ alignItems: 'start' }}>
        <div className="stack" style={{ ['--stack' as string]: '1.75rem' }}>
          <fieldset className="stack">
            <legend>Para quais cães?</legend>
            <p className="field__hint">Cada cão recebe o próprio kit e tem a própria assinatura. Não dividimos um kit entre cães.</p>
            {activeDogs.length > 0 && (
              <div className="choice-grid">
                {activeDogs.map((d) => (
                  <label className="choice" key={d.id}>
                    <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} />
                    <strong>{d.name}</strong>
                    <span className="small">{SIZE_LABEL[d.size] || 'Porte não informado'}{d.weight_kg ? ` · ${d.weight_kg} kg` : ''}</span>
                    {d.restrictions_detail.length > 0 && <span className="small muted">Restrições: {d.restrictions_detail.map((t) => t.name).join(', ')}</span>}
                    {d.missing_fields.length > 0 && <span className="small field__error">Complete: {d.missing_fields.join(', ')}</span>}
                  </label>
                ))}
              </div>
            )}
            {addingDog || activeDogs.length === 0 ? (
              <div className="card">
                <h3 style={{ marginBottom: '1rem' }}>Cadastrar cão</h3>
                <DogForm onSaved={async (d) => { setAddingDog(false); await dogs.reload(); setSelected((s) => [...s, d.id]); }}
                  onCancel={activeDogs.length ? () => setAddingDog(false) : undefined} />
              </div>
            ) : (
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setAddingDog(true)}>Cadastrar outro cão</button>
            )}
          </fieldset>

          {offer.commitment_options.length > 0 && (
            <fieldset>
              <legend>Ciclo de assinatura</legend>
              <p className="field__hint" style={{ marginBottom: '0.6rem' }}>A entrega é sempre mensal; o ciclo é a duração mínima do compromisso.</p>
              <div className="choice-grid">
                {offer.commitment_options.map((m) => (
                  <label className="choice" key={m}>
                    <input type="radio" name="commitment" checked={commitmentValue === m} onChange={() => setCommitment(m)} />
                    <strong>{m} meses</strong>
                    <span className="small muted">{m} curadorias, uma por mês</span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          {options.length > 0 && (
            <fieldset className="sub-food">
              <legend>Quer incluir ração na assinatura?</legend>
              <p className="field__hint">
                A ração chega todo mês junto com o Club, com <strong>preço exclusivo de assinante</strong>. Mantemos marca, fórmula e
                quantidade escolhidas; nunca trocamos sem falar com você. Dá para pausar a ração sem mexer no kit.
              </p>
              <div className="choice-grid">
                <label className="choice">
                  <input type="radio" name="food" checked={foodSku === null} onChange={() => setFoodSku(null)} />
                  <strong>Sem ração por enquanto</strong>
                  <span className="small muted">Você pode incluir depois em Minha Vila.</span>
                </label>
                {options.map((o) => (
                  <label className="choice" key={o.sku.id}>
                    <input type="radio" name="food" checked={foodSku === o.sku.id} onChange={() => setFoodSku(o.sku.id)} />
                    <strong>{o.product.name}{o.sku.variant_name && !o.product.name.includes(o.sku.variant_name) ? ` · ${o.sku.variant_name}` : ''}</strong>
                    <span className="sub-food__price">
                      {o.member < o.list && <s>{money(o.list)}</s>} <b>{money(o.member)}</b> <span className="small">por mês para assinantes</span>
                    </span>
                  </label>
                ))}
              </div>
              {food && (
                <div className="btn-row">
                  <span><strong>Pacotes por mês</strong></span>
                  <div className="qty">
                    <button type="button" aria-label="Diminuir" onClick={() => setFoodQty((q) => Math.max(1, q - 1))}>−</button>
                    <span>{foodQty}</span>
                    <button type="button" aria-label="Aumentar" onClick={() => setFoodQty((q) => Math.min(10, q + 1))}>+</button>
                  </div>
                </div>
              )}
            </fieldset>
          )}

          {cart.items.length > 0 && cartQuote && !cartQuote.member_pricing && (
            <fieldset className="sub-cart">
              <legend>Itens do seu carrinho</legend>
              <label className="check">
                <input type="checkbox" checked={takeCart} disabled={!cartReady} onChange={(e) => setTakeCart(e.target.checked)} />
                <span>Levar junto, já com preço de membro{cartQuote.club_savings_cents > 0 ? ` (economia de ${money(cartQuote.club_savings_cents)})` : ''}</span>
              </label>
              <ul className="list">
                {cartQuote.lines.map((l) => (
                  <li className="list__item small" key={l.sku_id}>
                    <span>{l.quantity} × {l.name}</span>
                    <span>
                      {l.member_unit_price_cents < l.unit_price_cents && <s className="muted">{money(l.total_cents)}</s>}{' '}
                      <strong>{money(l.member_unit_price_cents * l.quantity)}</strong>
                    </span>
                  </li>
                ))}
              </ul>
              {cartQuote.problems.map((msg) => <Alert tone="warn" key={msg}>{msg}</Alert>)}
              <p className="field__hint">Compra única no cartão, com cobrança própria. Entrega no mesmo endereço, frete de {money(cartQuote.shipping_cents)}.</p>
            </fieldset>
          )}

          {user && <CpfGate />}
          <AddressPicker value={addressId} onChange={(id, a) => { setAddressId(id); setAddress(a); }} />
          <BillingPicker value={billing} onChange={setBilling} recurring />
        </div>

        <aside className="card card--strong stack" aria-labelledby="resumo-assinatura">
          <h2 id="resumo-assinatura" style={{ fontSize: 'var(--step-1)' }}>Resumo da contratação</h2>
          <div className="summary">
            <div className="summary__row"><span>{p.name} (por cão)</span><span>{money(offer.price_cents)}/mês</span></div>
            <div className="summary__row"><span>Frete por entrega</span><span>{offer.shipping_cents ? money(offer.shipping_cents) : 'Incluso'}</span></div>
            <div className="summary__row"><span>Cães selecionados</span><span>{selected.length}</span></div>
            {food && <div className="summary__row"><span>Ração: {foodQty} × {food.product.name} <span className="muted">(preço de assinante)</span></span><span>{money(foodTotal)}/mês</span></div>}
            <div className="summary__row summary__row--total"><span>Total mensal</span><span>{money(monthly)}</span></div>
            {food && <p className="small muted">Frete da ração conforme a região do endereço.</p>}
            {withCart && cartQuote && (
              <>
                <div className="summary__row"><span>Itens do carrinho com preço de membro</span><span>{money(cartQuote.member_merchandise_cents)}</span></div>
                <div className="summary__row small"><span>Frete da compra</span><span>{money(cartQuote.shipping_cents)}</span></div>
                <div className="summary__row"><strong>Compra avulsa, paga uma vez</strong><strong>{money(cartTotal)}</strong></div>
              </>
            )}
          </div>
          <p className="small">
            <strong>Cobrança automática no cartão de crédito</strong> todo mês, uma por cão{food ? ' e uma da ração' : ''}.
            {commitmentValue ? ` Ciclo mínimo de ${commitmentValue} meses.` : ''} A primeira cobrança é gerada agora; a curadoria começa após a confirmação do pagamento.
            {withCart ? ' Os itens do carrinho são uma cobrança única no cartão, à parte.' : ''}
          </p>
          {offer.terms && <p className="small muted">{offer.terms}</p>}
          <label className="check">
            <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} />
            <span>
              Li e aceito as <Link to="/termos" target="_blank">condições da assinatura</Link> (versão {offer.version} da oferta)
              {food ? ', a recorrência da ração' : ''}{withCart ? ' e os termos de compra da loja' : ''} e autorizo a cobrança recorrente.
            </span>
          </label>
          {error && <Alert tone="error">{error}</Alert>}
          <button type="button" className="btn btn--brand btn--block" onClick={submit}
            disabled={busy || !accept || selected.length === 0 || !addressId || !user?.cpf}>
            {busy ? 'Gerando cobrança…' : 'Confirmar assinatura'}
          </button>
        </aside>
      </div>
    </div>
  );
}
