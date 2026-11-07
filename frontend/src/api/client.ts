/**
 * Cliente HTTP da API Django. Tokens JWT ficam no localStorage (sessão do navegador);
 * o access token é renovado automaticamente com o refresh token quando expira.
 */

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '';
const ACCESS = 'pv.access';
const REFRESH = 'pv.refresh';

export class ApiError extends Error {
  status: number;
  code?: string;
  data: Record<string, unknown>;
  constructor(status: number, message: string, data: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = typeof data.code === 'string' ? data.code : undefined;
    this.data = data;
  }
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export const tokens = {
  get access() { return read(ACCESS); },
  get refresh() { return read(REFRESH); },
  set(access: string, refresh?: string) {
    try {
      localStorage.setItem(ACCESS, access);
      if (refresh) localStorage.setItem(REFRESH, refresh);
    } catch { /* navegação privada */ }
  },
  clear() {
    try {
      localStorage.removeItem(ACCESS);
      localStorage.removeItem(REFRESH);
    } catch { /* ignore */ }
  },
};

function messageFrom(data: Record<string, unknown>, status: number): string {
  if (typeof data.detail === 'string') return data.detail;
  const parts: string[] = [];
  for (const [field, value] of Object.entries(data)) {
    const text = Array.isArray(value) ? value.join(' ') : typeof value === 'string' ? value : '';
    if (text) parts.push(field === 'non_field_errors' ? text : `${labelFor(field)}: ${text}`);
  }
  if (parts.length) return parts.join(' ');
  if (status >= 500) return 'Algo deu errado do nosso lado. Tente novamente em instantes.';
  return 'Não foi possível concluir. Confira os dados e tente novamente.';
}

const LABELS: Record<string, string> = {
  email: 'E-mail', password: 'Senha', full_name: 'Nome', cpf: 'CPF', cep: 'CEP', accept_terms: 'Termos',
  name: 'Nome', weight_kg: 'Peso', estimated_age_years: 'Idade', state: 'UF', number: 'Número',
};
const labelFor = (field: string) => LABELS[field] || field;

let refreshing: Promise<boolean> | null = null;

async function refreshAccess(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return false;
  refreshing ??= fetch(`${BASE}/api/v1/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })
    .then(async (res) => {
      if (!res.ok) {
        tokens.clear();
        return false;
      }
      const data = await res.json();
      tokens.set(data.access, data.refresh);
      return true;
    })
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  auth?: boolean;
}

export async function api<T>(path: string, opts: RequestOptions = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...(opts.headers || {}) };
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (opts.auth !== false && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1${path}`, {
      method: opts.method || (opts.body !== undefined ? 'POST' : 'GET'),
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'Sem conexão com o servidor. Verifique sua internet e tente de novo.');
  }
  if (res.status === 401 && retry && opts.auth !== false && tokens.refresh) {
    if (await refreshAccess()) return api<T>(path, opts, false);
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, messageFrom(data, res.status), data);
  return data as T;
}

export async function health(): Promise<{ status: string; payments_fake_mode: boolean }> {
  const res = await fetch(`${BASE}/api/health/`);
  return res.json();
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
