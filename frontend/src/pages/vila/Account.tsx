import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { Address, Order, Payment, Ticket } from '../../api/types';
import { Alert, Empty, Field, Spinner, StatusBadge } from '../../components/common';
import { AddressForm } from '../../components/Forms';
import { PaymentBox } from '../../components/PaymentBox';
import { useAuth } from '../../lib/auth';
import { BILLING_LABEL, cepMask, cpfMask, date, dateTime, money } from '../../lib/format';
import { errorMessage, useApi } from '../../lib/useApi';

export function Orders() {
  const { data, loading } = useApi<Order[]>('/me/orders/');
  if (loading) return <Spinner />;
  return (
    <>
      <h2 style={{ fontSize: 'var(--step-1)' }}>Pedidos da loja</h2>
      {!data?.length && <Empty title="Nenhum pedido"><Link to="/loja" className="btn">Ir para a loja</Link></Empty>}
      {data?.map((o) => (
        <article className="card list__item" key={o.id}>
          <div>
            <strong>{o.number}</strong>
            <p className="small muted">{dateTime(o.created_at)} · {o.lines.length} item(ns) · {money(o.total_cents)}</p>
          </div>
          <div className="btn-row">
            <StatusBadge status={o.status} label={o.status_label} />
            <Link to={`/pedido/${o.id}`} className="btn btn--sm btn--ghost">Detalhes</Link>
          </div>
        </article>
      ))}
    </>
  );
}

export function Payments() {
  const { data, loading, reload } = useApi<Payment[]>('/me/payments/');
  const [open, setOpen] = useState<number | null>(null);
  if (loading) return <Spinner />;
  return (
    <>
      <h2 style={{ fontSize: 'var(--step-1)' }}>Pagamentos</h2>
      {!data?.length && <Empty title="Nenhuma cobrança ainda" />}
      {data?.map((p) => (
        <article className="card stack" key={p.id}>
          <div className="list__item">
            <div>
              <strong>{p.reference || p.external_id}</strong>
              <p className="small muted">{BILLING_LABEL[p.billing_type] || p.billing_type} · vencimento {date(p.due_date)} · {money(p.value_cents)}{p.refunded_cents ? ` · estornado ${money(p.refunded_cents)}` : ''}</p>
            </div>
            <div className="btn-row">
              <StatusBadge status={p.status} label={p.status_label} />
              {['PENDING', 'OVERDUE'].includes(p.status) && (
                <button type="button" className="btn btn--sm" onClick={() => setOpen(open === p.id ? null : p.id)}>Pagar</button>
              )}
            </div>
          </div>
          {open === p.id && <PaymentBox payment={p} onChange={() => reload()} />}
        </article>
      ))}
    </>
  );
}

export function Addresses() {
  const { data, loading, reload } = useApi<Address[]>('/me/addresses/');
  const [editing, setEditing] = useState<number | 'new' | null>(null);
  const [error, setError] = useState('');
  if (loading) return <Spinner />;
  const remove = async (a: Address) => {
    if (!window.confirm('Remover este endereço?')) return;
    try {
      await api(`/me/addresses/${a.id}/`, { method: 'DELETE' });
      reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  return (
    <>
      <div className="list__item">
        <h2 style={{ fontSize: 'var(--step-1)' }}>Endereços</h2>
        {editing !== 'new' && <button type="button" className="btn btn--sm" onClick={() => setEditing('new')}>Novo endereço</button>}
      </div>
      <p className="small muted">Mudanças de endereço em assinaturas ativas respeitam a data de corte; fale com o atendimento para alterar uma assinatura.</p>
      {error && <Alert tone="error">{error}</Alert>}
      {editing === 'new' && <div className="card"><AddressForm onSaved={() => { setEditing(null); reload(); }} onCancel={() => setEditing(null)} /></div>}
      {data?.map((a) => (
        <article className="card" key={a.id}>
          {editing === a.id ? (
            <AddressForm initial={a} onSaved={() => { setEditing(null); reload(); }} onCancel={() => setEditing(null)} />
          ) : (
            <div className="list__item">
              <div>
                <strong>{a.label}</strong> {a.is_default && <span className="badge">Principal</span>}
                <p className="small">{a.recipient} · {a.street}, {a.number}{a.complement ? ` · ${a.complement}` : ''} · {a.district} · {a.city}/{a.state} · {cepMask(a.cep)}</p>
              </div>
              <div className="btn-row">
                <button type="button" className="btn btn--sm btn--ghost" onClick={() => setEditing(a.id)}>Editar</button>
                <button type="button" className="btn--link small" onClick={() => remove(a)}>Remover</button>
              </div>
            </div>
          )}
        </article>
      ))}
    </>
  );
}

export function Profile() {
  const { user, refreshUser } = useAuth();
  const [form, setForm] = useState({ full_name: user?.full_name || '', cpf: user?.cpf || '', phone: user?.phone || '' });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    try {
      await api('/me/', { method: 'PATCH', body: form });
      await refreshUser();
      setMessage('Dados atualizados.');
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  const toggleMarketing = async (value: boolean) => {
    try {
      await api('/me/', { method: 'PATCH', body: { marketing_opt_in: value } });
      await refreshUser();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  if (!user) return null;
  return (
    <>
      <h2 style={{ fontSize: 'var(--step-1)' }}>Meus dados</h2>
      <form className="card form" onSubmit={save}>
        <Field label="E-mail" hint="Para trocar o e-mail, fale com o atendimento."><input value={user.email} disabled /></Field>
        <Field label="Nome completo"><input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required /></Field>
        <div className="form form--2">
          <Field label="CPF"><input value={cpfMask(form.cpf)} onChange={(e) => setForm({ ...form, cpf: e.target.value })} inputMode="numeric" /></Field>
          <Field label="Celular"><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} inputMode="tel" /></Field>
        </div>
        {message && <Alert tone="ok">{message}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
        <button className="btn">Salvar</button>
      </form>
      <div className="card stack">
        <h3>Comunicações</h3>
        <label className="check">
          <input type="checkbox" checked={user.marketing_opt_in} onChange={(e) => toggleMarketing(e.target.checked)} />
          <span>Quero receber novidades e ofertas por e-mail.</span>
        </label>
        <p className="small muted">Avisos sobre cobranças, entregas e assinaturas continuam chegando, pois são necessários para o serviço. Última alteração: {dateTime(user.marketing_opt_in_updated_at)}.</p>
      </div>
      <div className="card stack">
        <h3>Privacidade (LGPD)</h3>
        <p className="small">Você pode pedir acesso, correção ou exclusão dos seus dados. A solicitação gera protocolo e explicamos o tratamento de registros com retenção obrigatória.</p>
        <Link to="/minha-vila/atendimento?tipo=privacy_access" className="btn btn--sm btn--ghost">Fazer solicitação de privacidade</Link>
      </div>
    </>
  );
}

const KINDS = [
  ['exchange', 'Troca'], ['cancellation', 'Cancelamento'], ['delivery', 'Entrega'], ['payment', 'Pagamento'],
  ['privacy_access', 'LGPD · acesso aos dados'], ['privacy_correction', 'LGPD · correção'], ['privacy_deletion', 'LGPD · exclusão'],
  ['other', 'Outro assunto'],
];

export function Support() {
  const { data, loading, reload } = useApi<Ticket[]>('/me/tickets/');
  const initialKind = new URLSearchParams(window.location.search).get('tipo') || 'other';
  const [form, setForm] = useState({ kind: initialKind, subject: '', description: '', reference: '' });
  const [created, setCreated] = useState<Ticket | null>(null);
  const [error, setError] = useState('');
  const [reply, setReply] = useState<Record<number, string>>({});

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const ticket = await api<Ticket>('/me/tickets/', { body: form });
      setCreated(ticket);
      setForm({ kind: 'other', subject: '', description: '', reference: '' });
      reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  const sendReply = async (ticket: Ticket) => {
    try {
      await api(`/me/tickets/${ticket.id}/reply/`, { body: { body: reply[ticket.id] || '' } });
      setReply({ ...reply, [ticket.id]: '' });
      reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <>
      <h2 style={{ fontSize: 'var(--step-1)' }}>Atendimento</h2>
      <form className="card form" onSubmit={submit}>
        <h3>Nova solicitação</h3>
        <div className="form form--2">
          <Field label="Assunto">
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Pedido ou assinatura (opcional)" hint="Ex.: PV-000012 ou AS-000003"><input value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></Field>
        </div>
        <Field label="Título"><input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} required maxLength={160} /></Field>
        <Field label="Descreva"><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required /></Field>
        {created && <Alert tone="ok">Solicitação recebida. Protocolo {created.protocol}. Primeiro retorno até {dateTime(created.due_at)}. Avisaremos quando houver resposta; nada é dado como concluído antes da execução.</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
        <button className="btn">Enviar</button>
      </form>
      {loading ? <Spinner /> : data?.map((t) => (
        <article className="card stack" key={t.id}>
          <div className="list__item">
            <div>
              <strong>{t.subject}</strong>
              <p className="small muted">Protocolo {t.protocol} · {t.kind_label} · aberto em {dateTime(t.created_at)}</p>
            </div>
            <StatusBadge status={t.status} label={t.status_label} />
          </div>
          <p className="small">{t.description}</p>
          {t.messages.map((m) => (
            <p key={m.id} className="small" style={{ borderLeft: `3px solid ${m.from_team ? 'var(--patinha)' : 'var(--line)'}`, paddingLeft: '0.75rem' }}>
              <strong>{m.from_team ? 'PetVila' : 'Você'}:</strong> {m.body}
            </p>
          ))}
          {t.resolution && <Alert tone="ok">Resposta final: {t.resolution}</Alert>}
          {!['closed', 'resolved'].includes(t.status) && (
            <div className="btn-row">
              <input aria-label="Responder" className="field" style={{ flex: 1, minHeight: '2.6rem', borderRadius: '0.8rem', border: '1.5px solid var(--line)', padding: '0.4rem 0.8rem' }}
                value={reply[t.id] || ''} onChange={(e) => setReply({ ...reply, [t.id]: e.target.value })} placeholder="Escreva uma mensagem" />
              <button type="button" className="btn btn--sm" onClick={() => sendReply(t)} disabled={!reply[t.id]}>Enviar</button>
            </div>
          )}
        </article>
      ))}
    </>
  );
}
