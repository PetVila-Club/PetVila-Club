import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, tokens } from './api';
import type { User } from './types';

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: Record<string, unknown>) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const refreshUser = useCallback(async () => {
    if (!tokens.access && !tokens.refresh) return setUser(null);
    try {
      setUser(await api<User>('/me/'));
    } catch {
      await tokens.clear();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    tokens.load().then(refreshUser).finally(() => setReady(true));
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<{ access: string; refresh: string }>('/auth/login/', { body: { email, password }, auth: false });
    await tokens.set(data.access, data.refresh);
    await refreshUser();
  }, [refreshUser]);

  const register = useCallback(async (data: Record<string, unknown>) => {
    await api('/auth/register/', { body: data, auth: false });
    await login(String(data.email), String(data.password));
  }, [login]);

  const logout = useCallback(async () => {
    await tokens.clear();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, ready, login, register, logout, refreshUser }), [user, ready, login, register, logout, refreshUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth fora do provider');
  return ctx;
}

export interface CartItem { sku_id: number; quantity: number; name: string }
interface CartState {
  items: CartItem[];
  add: (i: CartItem) => void;
  setQuantity: (skuId: number, q: number) => void;
  clear: () => void;
}
const CartContext = createContext<CartState | null>(null);

/** Carrinho em memória: só SKU e quantidade. Preços sempre vêm do servidor. */
export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);
  const add = useCallback((item: CartItem) => setItems((prev) => {
    const found = prev.find((i) => i.sku_id === item.sku_id);
    return found ? prev.map((i) => (i.sku_id === item.sku_id ? { ...i, quantity: i.quantity + item.quantity } : i)) : [...prev, item];
  }), []);
  const setQuantity = useCallback((skuId: number, q: number) => setItems((prev) => (q <= 0 ? prev.filter((i) => i.sku_id !== skuId) : prev.map((i) => (i.sku_id === skuId ? { ...i, quantity: q } : i)))), []);
  const clear = useCallback(() => setItems([]), []);
  const value = useMemo(() => ({ items, add, setQuantity, clear }), [items, add, setQuantity, clear]);
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart fora do provider');
  return ctx;
}

/** Busca simples com recarga ao voltar para a tela. */
export function useFetch<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(Boolean(path));
  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      setData(await api<T>(path));
      setError('');
    } catch (e: any) {
      setError(e?.message || 'Erro ao carregar.');
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => { reload(); }, [reload]);
  return { data, error, loading, reload };
}
