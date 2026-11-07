import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { statusTone } from '../lib/format';
import { DogArt } from './Brand';

export function Spinner({ label = 'Carregando' }: { label?: string }) {
  return <div className="spinner" role="status" aria-label={label} />;
}

export function Alert({ tone = 'info', children }: { tone?: 'info' | 'error' | 'ok' | 'warn'; children: ReactNode }) {
  if (!children) return null;
  return (
    <div className={`alert alert--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  );
}

export function StatusBadge({ status, label }: { status: string; label: string }) {
  const tone = statusTone(status);
  return <span className={`badge ${tone ? `badge--${tone}` : ''}`}>{label}</span>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty card">
      <DogArt />
      <h3>{title}</h3>
      {children}
    </div>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to={`/entrar?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return <>{children}</>;
}

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small className="field__hint">{hint}</small>}
      {error && <small className="field__error">{error}</small>}
    </label>
  );
}
