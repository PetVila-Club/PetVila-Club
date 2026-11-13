/**
 * Carrinho da loja avulsa. Guarda só SKU e quantidade no navegador; preço, desconto
 * de assinante, frete e disponibilidade são sempre recalculados pelo servidor.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export interface CartItem { sku_id: number; quantity: number; name: string }

interface CartState {
  items: CartItem[];
  count: number;
  add: (item: CartItem) => void;
  setQuantity: (skuId: number, quantity: number) => void;
  remove: (skuId: number) => void;
  clear: () => void;
}

const KEY = 'pv.cart';
const CartContext = createContext<CartState | null>(null);

function load(): CartItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((i) => Number.isInteger(i.sku_id) && i.quantity > 0) : [];
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(load);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(items));
    } catch { /* ignore */ }
  }, [items]);

  const add = useCallback((item: CartItem) => {
    setItems((prev) => {
      const found = prev.find((i) => i.sku_id === item.sku_id);
      if (found) return prev.map((i) => (i.sku_id === item.sku_id ? { ...i, quantity: Math.min(50, i.quantity + item.quantity) } : i));
      return [...prev, item];
    });
  }, []);
  const setQuantity = useCallback((skuId: number, quantity: number) => {
    setItems((prev) => (quantity <= 0 ? prev.filter((i) => i.sku_id !== skuId) : prev.map((i) => (i.sku_id === skuId ? { ...i, quantity: Math.min(50, quantity) } : i))));
  }, []);
  const remove = useCallback((skuId: number) => setItems((prev) => prev.filter((i) => i.sku_id !== skuId)), []);
  const clear = useCallback(() => setItems([]), []);

  const value = useMemo(
    () => ({ items, count: items.reduce((n, i) => n + i.quantity, 0), add, setQuantity, remove, clear }),
    [items, add, setQuantity, remove, clear],
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartState {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart fora do CartProvider');
  return ctx;
}
