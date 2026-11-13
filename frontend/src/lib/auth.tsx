import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, tokens } from '../api/client';
import type { User } from '../api/types';

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: Record<string, unknown>) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    if (!tokens.access && !tokens.refresh) {
      setUser(null);
      return;
    }
    try {
      setUser(await api<User>('/me/'));
    } catch {
      tokens.clear();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refreshUser().finally(() => setLoading(false));
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<{ access: string; refresh: string }>('/auth/login/', { body: { email, password }, auth: false });
    tokens.set(data.access, data.refresh);
    await refreshUser();
  }, [refreshUser]);

  const register = useCallback(async (data: Record<string, unknown>) => {
    await api('/auth/register/', { body: data, auth: false });
    await login(String(data.email), String(data.password));
  }, [login]);

  const logout = useCallback(() => {
    tokens.clear();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout, refreshUser }), [user, loading, login, register, logout, refreshUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth fora do AuthProvider');
  return ctx;
}
