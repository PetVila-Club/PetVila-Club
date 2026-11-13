import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../api/client';
import type { Address, Dog, Tag } from '../api/types';
import { cepMask } from '../lib/format';
import { errorMessage } from '../lib/useApi';
import { Alert, Field } from './common';

const UFS = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'];

const emptyAddress = { label: 'Casa', recipient: '', cep: '', street: '', number: '', complement: '', district: '', city: '', state: 'SP', is_default: false };

export function AddressForm({ initial, onSaved, onCancel }: { initial?: Address; onSaved: (a: Address) => void; onCancel?: () => void }) {
  const [form, setForm] = useState({ ...emptyAddress, ...(initial || {}) });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (key: string, value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const saved = initial
        ? await api<Address>(`/me/addresses/${initial.id}/`, { method: 'PATCH', body: form })
        : await api<Address>('/me/addresses/', { body: form });
      onSaved(saved);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="form form--2">
        <Field label="Identificação"><input value={form.label} onChange={(e) => set('label', e.target.value)} required /></Field>
        <Field label="Quem recebe"><input value={form.recipient} onChange={(e) => set('recipient', e.target.value)} required autoComplete="name" /></Field>
        <Field label="CEP"><input value={cepMask(form.cep)} onChange={(e) => set('cep', e.target.value)} required inputMode="numeric" autoComplete="postal-code" /></Field>
        <Field label="Rua"><input value={form.street} onChange={(e) => set('street', e.target.value)} required autoComplete="address-line1" /></Field>
        <Field label="Número"><input value={form.number} onChange={(e) => set('number', e.target.value)} required /></Field>
        <Field label="Complemento"><input value={form.complement} onChange={(e) => set('complement', e.target.value)} autoComplete="address-line2" /></Field>
        <Field label="Bairro"><input value={form.district} onChange={(e) => set('district', e.target.value)} required /></Field>
        <Field label="Cidade"><input value={form.city} onChange={(e) => set('city', e.target.value)} required autoComplete="address-level2" /></Field>
        <Field label="UF">
          <select value={form.state} onChange={(e) => set('state', e.target.value)}>{UFS.map((uf) => <option key={uf}>{uf}</option>)}</select>
        </Field>
      </div>
      <label className="check"><input type="checkbox" checked={form.is_default} onChange={(e) => set('is_default', e.target.checked)} /> Endereço principal</label>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="btn-row">
        <button className="btn" disabled={busy}>{busy ? 'Salvando…' : 'Salvar endereço'}</button>
        {onCancel && <button type="button" className="btn btn--ghost" onClick={onCancel}>Cancelar</button>}
      </div>
    </form>
  );
}

let tagCache: Tag[] | null = null;
export function useTags() {
  const [tags, setTags] = useState<Tag[]>(tagCache || []);
  useEffect(() => {
    if (tagCache) return;
    api<Tag[]>('/catalog/tags/', { auth: false }).then((t) => { tagCache = t; setTags(t); }).catch(() => setTags([]));
  }, []);
  return tags;
}

function TagPicker({ legend, hint, tags, value, onChange, name }: { legend: string; hint: string; tags: Tag[]; value: string[]; onChange: (v: string[]) => void; name: string }) {
  const toggle = (code: string) => onChange(value.includes(code) ? value.filter((c) => c !== code) : [...value, code]);
  return (
    <fieldset>
      <legend>{legend}</legend>
      <p className="field__hint" style={{ marginBottom: '0.6rem' }}>{hint}</p>
      <div className="chips">
        {tags.map((t) => (
          <label className="chip" key={t.code}>
            <input type="checkbox" name={name} checked={value.includes(t.code)} onChange={() => toggle(t.code)} />
            {t.name}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function DogForm({ initial, onSaved, onCancel }: { initial?: Dog; onSaved: (d: Dog) => void; onCancel?: () => void }) {
  const tags = useTags();
  const [form, setForm] = useState({
    name: initial?.name || '',
    birth_date: initial?.birth_date || '',
    estimated_age_years: initial?.estimated_age_years?.toString() || '',
    size: initial?.size || '',
    weight_kg: initial?.weight_kg || '',
    breed: initial?.breed || '',
    preferences: initial?.preferences || [],
    restrictions: initial?.restrictions || [],
    notes: initial?.notes || '',
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (key: string, value: unknown) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    const body = {
      ...form,
      birth_date: form.birth_date || null,
      estimated_age_years: form.estimated_age_years ? Number(form.estimated_age_years) : null,
      weight_kg: form.weight_kg || null,
    };
    try {
      const saved = initial
        ? await api<Dog>(`/me/dogs/${initial.id}/`, { method: 'PATCH', body })
        : await api<Dog>('/me/dogs/', { body });
      onSaved(saved);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="form form--2">
        <Field label="Nome do cão"><input value={form.name} onChange={(e) => set('name', e.target.value)} required /></Field>
        <Field label="Porte">
          <select value={form.size} onChange={(e) => set('size', e.target.value)} required>
            <option value="">Selecione</option>
            <option value="pequeno">Pequeno (até 10 kg)</option>
            <option value="medio">Médio (10 a 25 kg)</option>
            <option value="grande">Grande (acima de 25 kg)</option>
          </select>
        </Field>
        <Field label="Peso (kg)"><input type="number" step="0.1" min="0.5" max="120" value={form.weight_kg} onChange={(e) => set('weight_kg', e.target.value)} required /></Field>
        <Field label="Data de nascimento" hint="Ou informe a idade estimada ao lado."><input type="date" value={form.birth_date} onChange={(e) => set('birth_date', e.target.value)} /></Field>
        <Field label="Idade estimada (anos)"><input type="number" min="0" max="30" value={form.estimated_age_years} onChange={(e) => set('estimated_age_years', e.target.value)} /></Field>
        <Field label="Raça (opcional)"><input value={form.breed} onChange={(e) => set('breed', e.target.value)} /></Field>
      </div>
      <TagPicker legend="Restrições declaradas" name="restrictions" hint="O que o seu cão não pode receber. Itens com estes ingredientes ou materiais nunca entram no kit. Isto não é diagnóstico veterinário."
        tags={tags.filter((t) => t.kind !== 'feature')} value={form.restrictions} onChange={(v) => set('restrictions', v)} />
      <TagPicker legend="Preferências" name="preferences" hint="Ajuda a curadoria a escolher. Não garante exclusividade."
        tags={tags} value={form.preferences} onChange={(v) => set('preferences', v)} />
      <Field label="Observações para a curadoria"><textarea value={form.notes} onChange={(e) => set('notes', e.target.value)} /></Field>
      {initial && <p className="small muted">Alterações valem para os próximos ciclos. Kits já fechados mantêm o perfil usado na curadoria.</p>}
      {error && <Alert tone="error">{error}</Alert>}
      <div className="btn-row">
        <button className="btn" disabled={busy}>{busy ? 'Salvando…' : 'Salvar cão'}</button>
        {onCancel && <button type="button" className="btn btn--ghost" onClick={onCancel}>Cancelar</button>}
      </div>
    </form>
  );
}
