import { useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError, newIdempotencyKey } from '../api/client';
import type { Dog, Product, Subscription } from '../api/types';
import { AddressPicker, BillingPicker, CpfGate } from '../components/CheckoutParts';
import { Alert, Spinner } from '../components/common';
import { useAuth } from '../lib/auth';
import { money } from '../lib/format';
import { errorMessage, useApi } from '../lib/useApi';

const FREQUENCIES = [
  { days: 30, label: 'A cada 30 dias' },
  { days: 60, label: 'A cada 60 dias' },
];

export default function SubscribeFood() {
  const { slug, skuId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const product = useApi<Product>(`/catalog/products/${slug}/`);
  const dogs = useApi<Dog[]>('/me/dogs/');
  const key = useRef(newIdempotencyKey());
  const [quantity, setQuantity] = useState(1);
  const [frequency, setFrequency] = useState(30);
  const [dogId, setDogId] = useState<number | ''>('');
  const [addressId, setAddressId] = useState<number | null>(null);
  const [billing, setBilling] = useState('CREDIT_CARD');
  const [accept, setAccept] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (product.loading) return <Spinner />;
  const sku = product.data?.skus.find((s) => String(s.id) === skuId);
  if (!product.data || !sku || !product.data.is_recurring_food) {
    return <div className="wrap page"><Alert tone="error">Esta ração não está disponível para recorrência.</Alert></div>;
  }
  // Preço exibido já vem com o preço de membro para quem assina o Club; o servidor confere de novo.
  const unit = sku.price_cents ?? 0;
  const memberDeal = sku.list_price_cents !== null && unit < sku.list_price_cents;
  const price = unit * quantity;

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await api<{ subscriptions: Subscription[] }>('/checkout/food/', {
        body: { sku_id: sku.id, quantity, frequency_days: frequency, address_id: addressId, billing_type: billing, dog_id: dogId || null, expected_price_cents: price, accept_terms: accept },
        headers: { 'Idempotency-Key': key.current },
      });
      navigate(`/assinatura/confirmada?ids=${res.subscriptions.map((s) => s.id).join(',')}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.code === 'total_changed') product.reload();
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wrap page">
      <header className="page__head">
        <h1>{product.data.name}{sku.variant_name ? ` · ${sku.variant_name}` : ''}</h1>
        <p>Recorrência independente do kit: pausar ou cancelar a ração não muda a sua assinatura do Club. Se faltar estoque, avisamos e registramos a decisão com você; nunca enviamos outra marca ou fórmula por padrão.</p>
      </header>
      <div className="grid grid--2" style={{ alignItems: 'start' }}>
        <div className="stack" style={{ ['--stack' as string]: '1.75rem' }}>
          <fieldset>
            <legend>Frequência</legend>
            <div className="choice-grid">
              {FREQUENCIES.map((f) => (
                <label className="choice" key={f.days}>
                  <input type="radio" name="freq" checked={frequency === f.days} onChange={() => setFrequency(f.days)} />
                  <strong>{f.label}</strong>
                </label>
              ))}
            </div>
            <p className="field__hint" style={{ marginTop: '0.5rem' }}>A estimativa de consumo é só uma orientação; ajuste com seu veterinário.</p>
          </fieldset>
          <div className="btn-row">
            <span><strong>Quantidade por entrega</strong></span>
            <div className="qty">
              <button type="button" aria-label="Diminuir" onClick={() => setQuantity((q) => Math.max(1, q - 1))}>−</button>
              <span>{quantity}</span>
              <button type="button" aria-label="Aumentar" onClick={() => setQuantity((q) => Math.min(10, q + 1))}>+</button>
            </div>
          </div>
          {dogs.data && dogs.data.length > 0 && (
            <label className="field">
              <span>Para qual cão? (opcional)</span>
              <select value={dogId} onChange={(e) => setDogId(e.target.value ? Number(e.target.value) : '')}>
                <option value="">Não vincular</option>
                {dogs.data.filter((d) => d.is_active).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </label>
          )}
          {user && <CpfGate />}
          <AddressPicker value={addressId} onChange={(id) => setAddressId(id)} />
          <BillingPicker value={billing} onChange={setBilling} recurring />
        </div>
        <aside className="card card--strong stack">
          <h2 style={{ fontSize: 'var(--step-1)' }}>Resumo</h2>
          <div className="summary">
            <div className="summary__row"><span>{quantity} × {money(unit)}{memberDeal ? ' · preço de assinante' : ''}</span><span>{money(price)}</span></div>
            <div className="summary__row small muted"><span>Frete</span><span>conforme a região do endereço</span></div>
            <div className="summary__row summary__row--total"><span>Por entrega</span><span>{money(price)} + frete</span></div>
          </div>
          <p className="small"><strong>Cobrança automática no cartão de crédito</strong> {frequency === 30 ? 'a cada 30 dias' : 'a cada 60 dias'}. A primeira cobrança é gerada agora.</p>
          <label className="check">
            <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} />
            <span>Li e aceito as <Link to="/termos" target="_blank">condições da recorrência</Link> e autorizo a cobrança automática.</span>
          </label>
          {error && <Alert tone="error">{error}</Alert>}
          <button type="button" className="btn btn--brand btn--block" disabled={busy || !accept || !addressId || !user?.cpf} onClick={submit}>
            {busy ? 'Gerando cobrança…' : 'Confirmar recorrência'}
          </button>
        </aside>
      </div>
    </div>
  );
}
