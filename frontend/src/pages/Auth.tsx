import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { DogArt } from '../components/Brand';
import { Alert, Field } from '../components/common';
import { useAuth } from '../lib/auth';
import { cpfMask } from '../lib/format';
import { errorMessage } from '../lib/useApi';

function useNext() {
  const [params] = useSearchParams();
  const next = params.get('next') || '/minha-vila';
  return next.startsWith('/') && !next.startsWith('//') ? next : '/minha-vila';
}

function AuthShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="wrap page">
      <div className="grid grid--2" style={{ alignItems: 'center' }}>
        <div className="stack">
          <p className="eyebrow">Minha Vila</p>
          <h1>{title}</h1>
          <p className="muted">Seus cães, assinaturas, pedidos, entregas e pagamentos em um só lugar.</p>
          <div style={{ width: '9rem', color: 'var(--terra)' }} aria-hidden="true"><DogArt /></div>
        </div>
        <div className="card card--strong">{children}</div>
      </div>
    </div>
  );
}

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const next = useNext();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email, password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(errorMessage(err) === 'No active account found with the given credentials' ? 'E-mail ou senha incorretos.' : errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Entrar">
      <form className="form" onSubmit={submit}>
        <Field label="E-mail"><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></Field>
        <Field label="Senha"><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" /></Field>
        {error && <Alert tone="error">{error}</Alert>}
        <button className="btn btn--brand btn--block" disabled={busy}>{busy ? 'Entrando…' : 'Entrar'}</button>
        <p className="small">Ainda não tem conta? <Link to={`/cadastro?next=${encodeURIComponent(next)}`}>Criar conta</Link></p>
        <p className="small muted">Esqueceu a senha? Fale com o <Link to="/ajuda">atendimento</Link>.</p>
      </form>
    </AuthShell>
  );
}

export function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const next = useNext();
  const [form, setForm] = useState({ full_name: '', email: '', cpf: '', phone: '', password: '', marketing_opt_in: false, accept_terms: false });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (key: string, value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await register(form);
      navigate(next, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Criar conta">
      <form className="form" onSubmit={submit}>
        <Field label="Nome completo"><input value={form.full_name} onChange={(e) => set('full_name', e.target.value)} required autoComplete="name" /></Field>
        <Field label="E-mail"><input type="email" value={form.email} onChange={(e) => set('email', e.target.value)} required autoComplete="email" /></Field>
        <div className="form form--2">
          <Field label="CPF" hint="Usado para emitir as cobranças."><input value={cpfMask(form.cpf)} onChange={(e) => set('cpf', e.target.value)} inputMode="numeric" /></Field>
          <Field label="Celular"><input value={form.phone} onChange={(e) => set('phone', e.target.value)} inputMode="tel" autoComplete="tel" /></Field>
        </div>
        <Field label="Senha" hint="Mínimo de 8 caracteres, sem ser só números."><input type="password" value={form.password} onChange={(e) => set('password', e.target.value)} required minLength={8} autoComplete="new-password" /></Field>
        <label className="check">
          <input type="checkbox" checked={form.accept_terms} onChange={(e) => set('accept_terms', e.target.checked)} required />
          <span>Li e aceito os <Link to="/termos" target="_blank">termos de uso</Link> e a <Link to="/privacidade" target="_blank">política de privacidade</Link>.</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={form.marketing_opt_in} onChange={(e) => set('marketing_opt_in', e.target.checked)} />
          <span>Quero receber novidades e ofertas da PetVila por e-mail (opcional; avisos sobre pedidos e assinaturas chegam de qualquer forma).</span>
        </label>
        {error && <Alert tone="error">{error}</Alert>}
        <button className="btn btn--brand btn--block" disabled={busy}>{busy ? 'Criando…' : 'Criar conta'}</button>
        <p className="small">Já tem conta? <Link to={`/entrar?next=${encodeURIComponent(next)}`}>Entrar</Link></p>
      </form>
    </AuthShell>
  );
}
