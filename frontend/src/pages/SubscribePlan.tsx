import { useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, newIdempotencyKey } from '../api/client';
import type { Dog, Plan, Subscription } from '../api/types';
import { AddressPicker, BillingPicker, CpfGate } from '../components/CheckoutParts';
import { Alert, Spinner } from '../components/common';
import { DogForm } from '../components/Forms';
import { useAuth } from '../lib/auth';
import { money, SIZE_LABEL } from '../lib/format';
import { errorMessage, useApi } from '../lib/useApi';

export default function SubscribePlan() {
  const { code } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const plan = useApi<Plan>(`/plans/${code}/`);
  const dogs = useApi<Dog[]>('/me/dogs/');
  const key = useRef(newIdempotencyKey());
  const [selected, setSelected] = useState<number[]>([]);
  const [commitment, setCommitment] = useState<number | null>(null);
  const [addressId, setAddressId] = useState<number | null>(null);
  const [billing, setBilling] = useState('PIX');
  const [accept, setAccept] = useState(false);
  const [addingDog, setAddingDog] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

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

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await api<{ subscriptions: Subscription[] }>('/checkout/subscription/', {
        body: { plan: p.code, dog_ids: selected, address_id: addressId, billing_type: billing, commitment_months: commitmentValue, offer_id: offer.id, accept_terms: accept },
        headers: { 'Idempotency-Key': key.current },
      });
      navigate(`/assinatura/confirmada?ids=${res.subscriptions.map((s) => s.id).join(',')}`, { replace: true });
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
        <p className="eyebrow">Assinatura</p>
        <h1>{p.name}</h1>
        <p>{p.tagline} {p.composition?.total_items} itens por mês para cada cão, com lista própria e curadoria humana.</p>
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
          {user && <CpfGate />}
          <AddressPicker value={addressId} onChange={(id) => setAddressId(id)} />
          <BillingPicker value={billing} onChange={setBilling} recurring />
        </div>

        <aside className="card card--strong stack" aria-labelledby="resumo-assinatura">
          <h2 id="resumo-assinatura" style={{ fontSize: 'var(--step-1)' }}>Resumo da contratação</h2>
          <div className="summary">
            <div className="summary__row"><span>{p.name} (por cão)</span><span>{money(offer.price_cents)}/mês</span></div>
            <div className="summary__row"><span>Frete por entrega</span><span>{offer.shipping_cents ? money(offer.shipping_cents) : 'Incluso'}</span></div>
            <div className="summary__row"><span>Cães selecionados</span><span>{selected.length}</span></div>
            <div className="summary__row summary__row--total"><span>Total mensal</span><span>{money(perDog * selected.length)}</span></div>
          </div>
          <p className="small">
            <strong>Cobrança recorrente automática</strong> todo mês, uma por cão, no meio de pagamento escolhido.
            {commitmentValue ? ` Ciclo mínimo de ${commitmentValue} meses.` : ''} A primeira cobrança é gerada agora; a curadoria começa após a confirmação do pagamento.
          </p>
          {offer.terms && <p className="small muted">{offer.terms}</p>}
          <label className="check">
            <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} />
            <span>Li e aceito as <Link to="/termos" target="_blank">condições da assinatura</Link> (versão {offer.version} da oferta) e autorizo a cobrança recorrente.</span>
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
