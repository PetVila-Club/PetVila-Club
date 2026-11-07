import { useState } from 'react';
import { api } from '../../api/client';
import type { Delivery, DeliveryLine } from '../../api/types';
import { Alert, Empty, Spinner, StatusBadge } from '../../components/common';
import { dateTime } from '../../lib/format';
import { errorMessage, useApi } from '../../lib/useApi';

const REACTIONS = [
  { value: 'loved', label: 'Amou' },
  { value: 'liked', label: 'Gostou' },
  { value: 'indifferent', label: 'Indiferente' },
  { value: 'disliked', label: 'Não gostou' },
  { value: 'adverse', label: 'Teve reação adversa' },
];

function ReviewForm({ line, onSaved }: { line: DeliveryLine; onSaved: () => void }) {
  const [rating, setRating] = useState(line.review?.rating || 0);
  const [reaction, setReaction] = useState(line.review?.dog_reaction || '');
  const [comment, setComment] = useState(line.review?.comment || '');
  const [allowPublic, setAllowPublic] = useState(line.review?.allow_public || false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      await api('/me/reviews/', { body: { shipment_line: line.id, rating, dog_reaction: reaction, comment, allow_public: allowPublic } });
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack" style={{ ['--stack' as string]: '0.6rem', paddingTop: '0.5rem' }}>
      <fieldset>
        <legend className="small">Nota para {line.product_name}{line.dog_name ? ` (${line.dog_name})` : ''}</legend>
        <div className="chips" role="radiogroup">
          {[1, 2, 3, 4, 5].map((n) => (
            <label className="chip" key={n}>
              <input type="radio" name={`rating-${line.id}`} checked={rating === n} onChange={() => setRating(n)} />
              {'★'.repeat(n)}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="field">
        <span>Reação do cão</span>
        <select value={reaction} onChange={(e) => setReaction(e.target.value)}>
          <option value="">Prefiro não informar</option>
          {REACTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </label>
      <label className="field"><span>Comentário (opcional)</span><textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} /></label>
      <label className="check"><input type="checkbox" checked={allowPublic} onChange={(e) => setAllowPublic(e.target.checked)} /> Autorizo publicar esta avaliação no site.</label>
      {reaction === 'adverse' && <Alert tone="warn">Sentimos muito. Vamos abrir um atendimento para acompanhar. Em caso de sintomas, procure um veterinário.</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      {saved && <Alert tone="ok">Avaliação registrada. Obrigado!</Alert>}
      <button type="button" className="btn btn--sm" disabled={busy || !rating} onClick={submit}>{line.review ? 'Atualizar avaliação' : 'Enviar avaliação'}</button>
    </div>
  );
}

function DeliveryCard({ delivery, onChange }: { delivery: Delivery; onChange: () => void }) {
  const [open, setOpen] = useState<number | null>(null);
  const byDog = delivery.lines.reduce<Record<string, DeliveryLine[]>>((acc, l) => {
    const key = l.dog_name || 'Pedido';
    (acc[key] ||= []).push(l);
    return acc;
  }, {});

  return (
    <article className="card stack">
      <div className="list__item">
        <div>
          <h3>{delivery.kind_label} · {delivery.reference}</h3>
          <p className="small muted">Expedição {delivery.number}{delivery.tracking_code ? ` · rastreio ${delivery.tracking_code}` : ''}{delivery.carrier ? ` (${delivery.carrier})` : ''}</p>
        </div>
        <StatusBadge status={delivery.status} label={delivery.status_label} />
      </div>
      <p className="small">
        {delivery.content_status === 'confirmado'
          ? <><span className="badge badge--ok">Conteúdo confirmado</span> Estes são os produtos realmente expedidos.</>
          : <><span className="badge">Previsão</span> Conteúdo previsto; pode mudar até a expedição.</>}
      </p>
      {delivery.tracking_url && <a href={delivery.tracking_url} target="_blank" rel="noreferrer" className="small">Acompanhar no site da transportadora</a>}
      {Object.entries(byDog).map(([dog, lines]) => (
        <div key={dog} className="stack" style={{ ['--stack' as string]: '0.5rem' }}>
          {delivery.kind !== 'store' && <p className="eyebrow">{dog}</p>}
          <ul className="list">
            {lines.map((line) => (
              <li key={line.id} style={{ borderTop: '1px solid var(--line)', paddingTop: '0.6rem' }}>
                <div className="list__item small">
                  <span>
                    <strong>{line.quantity} × {line.product_name}</strong> <span className="muted">{line.sku_code}</span>
                    {line.replaced_sku && <span className="muted"> · substituiu {line.replaced_sku.product_name}</span>}
                  </span>
                  {delivery.can_review && (
                    <button type="button" className="btn--link small" onClick={() => setOpen(open === line.id ? null : line.id)}>
                      {line.review ? `${'★'.repeat(line.review.rating)} editar` : 'Avaliar'}
                    </button>
                  )}
                </div>
                {open === line.id && <ReviewForm line={line} onSaved={onChange} />}
              </li>
            ))}
          </ul>
        </div>
      ))}
      <p className="small muted">{delivery.delivered_at ? `Entregue em ${dateTime(delivery.delivered_at)}` : delivery.shipped_at ? `Expedido em ${dateTime(delivery.shipped_at)}` : 'Em preparação'}</p>
    </article>
  );
}

export default function Deliveries() {
  const { data, loading, reload } = useApi<Delivery[]>('/me/deliveries/');
  if (loading) return <Spinner />;
  return (
    <>
      <h2 style={{ fontSize: 'var(--step-1)' }}>Entregas e avaliações</h2>
      <p className="small muted">A avaliação fica disponível para cada item depois da entrega confirmada.</p>
      {!data?.length && <Empty title="Nenhuma entrega ainda">Assim que um kit ou pedido for separado, ele aparece aqui.</Empty>}
      {data?.map((d) => <DeliveryCard key={d.id} delivery={d} onChange={reload} />)}
    </>
  );
}
