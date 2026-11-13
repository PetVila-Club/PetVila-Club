import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Address } from '../api/types';
import { useAuth } from '../lib/auth';
import { BILLING_LABEL, cepMask, cpfMask } from '../lib/format';
import { errorMessage, useApi } from '../lib/useApi';
import { Alert, Field, Spinner } from './common';
import { AddressForm } from './Forms';

export function AddressPicker({ value, onChange }: { value: number | null; onChange: (id: number, address: Address) => void }) {
  const { data, loading, reload } = useApi<Address[]>('/me/addresses/');
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (value === null && data && data.length) {
      const def = data.find((a) => a.is_default) || data[0];
      onChange(def.id, def);
    }
  }, [data, value, onChange]);

  if (loading) return <Spinner />;
  const list = data || [];
  return (
    <fieldset className="stack">
      <legend>Endereço de entrega</legend>
      {list.length > 0 && (
        <div className="choice-grid">
          {list.map((a) => (
            <label className="choice" key={a.id}>
              <input type="radio" name="address" checked={value === a.id} onChange={() => onChange(a.id, a)} />
              <strong>{a.label}</strong>
              <span className="small">{a.street}, {a.number}{a.complement ? ` · ${a.complement}` : ''}</span>
              <span className="small muted">{a.district} · {a.city}/{a.state} · {cepMask(a.cep)}</span>
            </label>
          ))}
        </div>
      )}
      {adding || list.length === 0 ? (
        <div className="card">
          <AddressForm onSaved={async (a) => { setAdding(false); await reload(); onChange(a.id, a); }} onCancel={list.length ? () => setAdding(false) : undefined} />
        </div>
      ) : (
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => setAdding(true)}>Adicionar outro endereço</button>
      )}
    </fieldset>
  );
}

/** O Asaas exige CPF para emitir a cobrança. Pede só quando falta. */
export function CpfGate() {
  const { user, refreshUser } = useAuth();
  const [cpf, setCpf] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  if (!user || user.cpf) return null;
  const save = async () => {
    setBusy(true);
    setError('');
    try {
      await api('/me/', { method: 'PATCH', body: { cpf } });
      await refreshUser();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="card stack">
      <p><strong>Precisamos do seu CPF</strong> para emitir a cobrança no provedor de pagamento.</p>
      <div className="btn-row">
        <Field label="CPF"><input value={cpfMask(cpf)} onChange={(e) => setCpf(e.target.value)} inputMode="numeric" autoComplete="off" /></Field>
        <button type="button" className="btn" onClick={save} disabled={busy} style={{ alignSelf: 'end' }}>Salvar CPF</button>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  );
}

/**
 * Meios aceitos (regra de 13/11/2026): recorrência (planos e ração) só cartão de crédito;
 * compra avulsa da loja, cartão de crédito ou Pix. O servidor recusa qualquer outro.
 */
export const RECURRING_BILLING = ['CREDIT_CARD'];
export const STORE_BILLING = ['CREDIT_CARD', 'PIX'];

export function BillingPicker({ value, onChange, recurring = false }: { value: string; onChange: (v: string) => void; recurring?: boolean }) {
  const hints: Record<string, string> = {
    PIX: 'Aprovação em instantes.',
    CREDIT_CARD: recurring
      ? 'Cobrança automática todo mês no cartão. Você informa o cartão na página segura do Asaas; a PetVila não recebe nem guarda dados de cartão.'
      : 'Você informa o cartão na página segura do Asaas. A PetVila não recebe nem guarda dados de cartão.',
  };
  const keys = recurring ? RECURRING_BILLING : STORE_BILLING;
  return (
    <fieldset>
      <legend>Forma de pagamento</legend>
      {recurring && <p className="field__hint" style={{ marginBottom: '0.6rem' }}>Assinaturas e ração recorrente são pagas só com cartão de crédito.</p>}
      <div className="choice-grid">
        {keys.map((key) => [key, BILLING_LABEL[key]] as const).map(([key, label]) => (
          <label className="choice" key={key}>
            <input type="radio" name="billing" checked={value === key} onChange={() => onChange(key)} />
            <strong>{label}</strong>
            <span className="small muted">{hints[key]}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
