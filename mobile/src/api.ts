/**
 * Cliente da mesma API REST usada pelo site. Tokens JWT ficam no SecureStore
 * (Keychain/Keystore), nunca em armazenamento aberto.
 */
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

export const API_URL = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const ACCESS = 'pv_access';
const REFRESH = 'pv_refresh';
let memory: { access: string | null; refresh: string | null } = { access: null, refresh: null };

async function getItem(key: string) {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(key) ?? null;
  return SecureStore.getItemAsync(key);
}
async function setItem(key: string, value: string | null) {
  if (Platform.OS === 'web') {
    if (value === null) globalThis.localStorage?.removeItem(key); else globalThis.localStorage?.setItem(key, value);
    return;
  }
  if (value === null) await SecureStore.deleteItemAsync(key); else await SecureStore.setItemAsync(key, value);
}

export const tokens = {
  async load() {
    memory = { access: await getItem(ACCESS), refresh: await getItem(REFRESH) };
    return memory;
  },
  async set(access: string, refresh?: string) {
    memory.access = access;
    await setItem(ACCESS, access);
    if (refresh) {
      memory.refresh = refresh;
      await setItem(REFRESH, refresh);
    }
  },
  async clear() {
    memory = { access: null, refresh: null };
    await setItem(ACCESS, null);
    await setItem(REFRESH, null);
  },
  get access() { return memory.access; },
  get refresh() { return memory.refresh; },
};

export class ApiError extends Error {
  status: number;
  code?: string;
  data: Record<string, any>;
  constructor(status: number, message: string, data: Record<string, any> = {}) {
    super(message);
    this.status = status;
    this.data = data;
    this.code = typeof data.code === 'string' ? data.code : undefined;
  }
}

function messageFrom(data: Record<string, any>, status: number) {
  if (typeof data.detail === 'string') return data.detail;
  const parts = Object.values(data).map((v) => (Array.isArray(v) ? v.join(' ') : typeof v === 'string' ? v : '')).filter(Boolean);
  if (parts.length) return parts.join(' ');
  return status >= 500 ? 'Algo deu errado do nosso lado. Tente de novo.' : 'Não foi possível concluir.';
}

async function refreshAccess() {
  if (!memory.refresh) return false;
  const res = await fetch(`${API_URL}/api/v1/auth/refresh/`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh: memory.refresh }),
  }).catch(() => null);
  if (!res || !res.ok) {
    await tokens.clear();
    return false;
  }
  const data = await res.json();
  await tokens.set(data.access, data.refresh);
  return true;
}

export async function api<T>(path: string, opts: { method?: string; body?: unknown; headers?: Record<string, string>; auth?: boolean } = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...(opts.headers || {}) };
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (opts.auth !== false && memory.access) headers.Authorization = `Bearer ${memory.access}`;
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, {
      method: opts.method || (opts.body !== undefined ? 'POST' : 'GET'),
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'Sem conexão com o servidor.');
  }
  if (res.status === 401 && retry && opts.auth !== false && memory.refresh && (await refreshAccess())) {
    return api<T>(path, opts, false);
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, messageFrom(data, res.status), data);
  return data as T;
}

export async function health(): Promise<{ payments_fake_mode: boolean }> {
  const res = await fetch(`${API_URL}/api/health/`);
  return res.json();
}

export function idempotencyKey() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

export const money = (cents: number | null | undefined) =>
  cents === null || cents === undefined ? '—' : `R$ ${(cents / 100).toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.')}`;

export const date = (value: string | null | undefined) => {
  if (!value) return '—';
  const [y, m, d] = value.slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
};
