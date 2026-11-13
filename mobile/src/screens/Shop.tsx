import { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { api, ApiError, idempotencyKey, money } from '../api';
import type { RootStack } from '../navigation';
import { useAuth, useCart, useFetch } from '../state';
import { colors, fonts } from '../theme';
import type { Address, Order, Plan, Product, ProductSummary, Quote } from '../types';
import { Badge, Button, Card, Choice, DogArt, Loading, Logo, Notice, Row, Screen, Text } from '../ui';

export function HomeScreen({ navigation }: NativeStackScreenProps<RootStack, 'Tabs'> | any) {
  const { data: plans, loading } = useFetch<Plan[]>('/plans/');
  return (
    <Screen>
      <Logo height={34} />
      <Text variant="eyebrow">Clube de assinatura para cães</Text>
      <Text variant="title">Cuidado que faz parte da rotina.</Text>
      <Text style={{ color: colors.inkSoft }}>Todo mês, uma nova curadoria PetVila para o seu cão, com olhar humano e respeito às restrições de cada um.</Text>
      {loading && <Loading />}
      {plans?.map((plan) => (
        <Card key={plan.code} dark={plan.highlight}>
          <Text variant="h2" style={plan.highlight && { color: colors.chamego }}>{plan.name}</Text>
          <Text style={[{ fontFamily: fonts.bold }, plan.highlight && { color: colors.chamego }]}>{plan.tagline}</Text>
          {plan.composition?.lines.filter((l) => l.quantity > 0).map((l) => (
            <Text key={l.category} variant="small" style={plan.highlight && { color: colors.chamego }}>{l.quantity} × {l.category_name}</Text>
          ))}
          <Text variant="small" style={[{ fontFamily: fonts.bold }, plan.highlight && { color: colors.chamego }]}>{plan.composition?.total_items} itens por mês</Text>
          {plan.offer ? (
            <Text variant="price" style={plan.highlight && { color: colors.chamego }}>{money(plan.offer.price_cents)}<Text variant="small" style={plan.highlight && { color: colors.chamego }}> /mês</Text></Text>
          ) : (
            <Text variant="small" style={plan.highlight && { color: colors.chamego }}>Preço em aprovação. Em breve.</Text>
          )}
          <Button title={plan.available ? `Assinar o ${plan.name}` : 'Em breve'} variant={plan.available ? 'brand' : 'ghost'} disabled={!plan.available}
            onPress={() => navigation.navigate('Subscribe', { code: plan.code })} />
        </Card>
      ))}
      <View style={{ alignItems: 'center', marginTop: 12 }}><DogArt size={90} /></View>
    </Screen>
  );
}

export function StoreScreen({ navigation }: any) {
  const { data, loading, error } = useFetch<ProductSummary[]>('/catalog/products/');
  return (
    <Screen>
      <Text variant="eyebrow">PetVila Store</Text>
      <Text variant="title">Loja</Text>
      {loading && <Loading />}
      {error ? <Notice tone="error">{error}</Notice> : null}
      {data?.map((p) => (
        <Pressable key={p.slug} accessibilityRole="button" onPress={() => navigation.navigate('Product', { slug: p.slug })}>
          <Card>
            <Text variant="small" style={{ color: colors.inkSoft }}>{p.category.name}</Text>
            <Text style={{ fontFamily: fonts.bold }}>{p.name}</Text>
            <Row style={{ justifyContent: 'flex-start' }}>
              {p.from_list_price_cents !== null && p.from_price_cents !== null && p.from_price_cents < p.from_list_price_cents && (
                <Text variant="small" style={{ textDecorationLine: 'line-through', color: colors.inkSoft }}>{money(p.from_list_price_cents)}</Text>
              )}
              <Text variant="price">{money(p.from_price_cents)}</Text>
            </Row>
            {!p.sellable && <Badge label="Indisponível" status="pending" />}
          </Card>
        </Pressable>
      ))}
    </Screen>
  );
}

export function ProductScreen({ route, navigation }: NativeStackScreenProps<RootStack, 'Product'>) {
  const { data: product, loading } = useFetch<Product>(`/catalog/products/${route.params.slug}/`);
  const cart = useCart();
  const [added, setAdded] = useState(false);
  if (loading || !product) return <Screen><Loading /></Screen>;
  const sku = product.skus.find((s) => s.sellable) || product.skus[0];
  return (
    <Screen>
      <Text variant="eyebrow">{product.category.name}</Text>
      <Text variant="h2">{product.name}</Text>
      <Text variant="price">{money(sku?.price_cents)}</Text>
      {sku && sku.price_cents !== null && sku.list_price_cents !== null && sku.price_cents < sku.list_price_cents && <Badge label="Preço de membro" status="active" />}
      <Text>{product.description}</Text>
      {sku?.contains.length ? <Text variant="small"><Text variant="small" style={{ fontFamily: fonts.bold }}>Composição: </Text>{sku.contains.map((t) => t.name).join(', ')}</Text> : null}
      {product.conservation ? <Text variant="small">Conservação: {product.conservation}</Text> : null}
      {sku?.sellable ? (
        <Button title="Adicionar ao carrinho" variant="brand" onPress={() => { cart.add({ sku_id: sku.id, quantity: 1, name: product.name }); setAdded(true); }} />
      ) : <Notice tone="warn">Indisponível no momento.</Notice>}
      {added && <Notice tone="ok">Adicionado ao carrinho.</Notice>}
      {added && <Button title="Ver carrinho" variant="ghost" onPress={() => navigation.navigate('Tabs', { screen: 'Carrinho' } as any)} />}
    </Screen>
  );
}

export function useAddresses() {
  const { user } = useAuth();
  return useFetch<Address[]>(user ? '/me/addresses/' : null);
}

// Recorrência (planos e ração) só cartão; loja avulsa, cartão ou Pix (regra de 13/11/2026).
const BILLING = [
  { key: 'CREDIT_CARD', label: 'Cartão (página segura do Asaas)' },
  { key: 'PIX', label: 'Pix' },
];

export function BillingChoice({ value, onChange, recurring = false }: { value: string; onChange: (v: string) => void; recurring?: boolean }) {
  const options = recurring ? BILLING.filter((b) => b.key === 'CREDIT_CARD') : BILLING;
  return (
    <View style={{ gap: 8 }}>
      <Text style={{ fontFamily: fonts.bold }}>Forma de pagamento</Text>
      {recurring && <Text variant="small">Assinaturas são pagas só com cartão de crédito.</Text>}
      {options.map((b) => <Choice key={b.key} label={b.label} selected={value === b.key} onPress={() => onChange(b.key)} />)}
    </View>
  );
}

export function AddressChoice({ value, onChange }: { value: number | null; onChange: (id: number) => void }) {
  const { data, loading } = useAddresses();
  useEffect(() => {
    if (value === null && data?.length) onChange((data.find((a) => a.is_default) || data[0]).id);
  }, [data, value, onChange]);
  if (loading) return <Loading />;
  if (!data?.length) return <Notice tone="warn">Cadastre um endereço em Minha Vila no site para concluir.</Notice>;
  return (
    <View style={{ gap: 8 }}>
      <Text style={{ fontFamily: fonts.bold }}>Endereço de entrega</Text>
      {data.map((a) => <Choice key={a.id} label={a.label} detail={`${a.street}, ${a.number} · ${a.city}/${a.state}`} selected={value === a.id} onPress={() => onChange(a.id)} />)}
    </View>
  );
}

export function CartScreen({ navigation }: any) {
  const cart = useCart();
  const { user } = useAuth();
  const [addressId, setAddressId] = useState<number | null>(null);
  const [billing, setBilling] = useState('PIX');
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const key = useRef(idempotencyKey());
  const addresses = useAddresses();
  const items = useMemo(() => cart.items.map(({ sku_id, quantity }) => ({ sku_id, quantity })), [cart.items]);
  const cep = addresses.data?.find((a) => a.id === addressId)?.cep;

  useEffect(() => {
    if (!items.length) return setQuote(null);
    api<Quote>('/checkout/quote/', { body: { items, cep } }).then(setQuote).catch((e) => setError(e.message));
  }, [items, cep]);

  if (!cart.items.length) return <Screen><Text variant="title">Carrinho</Text><Text>Seu carrinho está vazio.</Text></Screen>;

  const confirm = async () => {
    if (!quote || !addressId) return;
    setBusy(true);
    setError('');
    try {
      const order = await api<Order>('/checkout/store/', {
        body: { items, address_id: addressId, billing_type: billing, expected_total_cents: quote.total_cents, accept_terms: true },
        headers: { 'Idempotency-Key': key.current },
      });
      cart.clear();
      key.current = idempotencyKey();
      if (order.payment) navigation.navigate('Payment', { payment: order.payment, title: `Pedido ${order.number}` });
    } catch (e) {
      if (e instanceof ApiError && e.data.quote) setQuote(e.data.quote as Quote);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Text variant="title">Carrinho</Text>
      {cart.items.map((item) => {
        const line = quote?.lines.find((l) => l.sku_id === item.sku_id);
        return (
          <Card key={item.sku_id}>
            <Text style={{ fontFamily: fonts.bold }}>{item.name}</Text>
            <Row>
              <Text variant="small">{line ? `${money(line.unit_price_cents)} cada` : '—'}</Text>
              <Row>
                <Button title="−" variant="ghost" onPress={() => cart.setQuantity(item.sku_id, item.quantity - 1)} />
                <Text style={{ fontFamily: fonts.bold }}>{item.quantity}</Text>
                <Button title="+" variant="ghost" onPress={() => cart.setQuantity(item.sku_id, item.quantity + 1)} />
              </Row>
            </Row>
          </Card>
        );
      })}
      {!user ? (
        <Button title="Entrar para finalizar" onPress={() => navigation.navigate('Tabs', { screen: 'Minha Vila' })} />
      ) : (
        <>
          <AddressChoice value={addressId} onChange={setAddressId} />
          <BillingChoice value={billing} onChange={setBilling} />
          {quote && (
            <Card>
              <Row><Text>Produtos</Text><Text>{money(quote.subtotal_cents)}</Text></Row>
              {quote.discount_cents > 0 && <Row><Text>Preço de membro</Text><Text>− {money(quote.discount_cents)}</Text></Row>}
              <Row><Text>Frete</Text><Text>{money(quote.shipping_cents)}</Text></Row>
              <Row><Text variant="h2">Total</Text><Text variant="h2">{money(quote.total_cents)}</Text></Row>
              <Text variant="small" style={{ color: colors.inkSoft }}>Compra única. Ao confirmar, você aceita os termos de compra e a política de privacidade.</Text>
            </Card>
          )}
          {quote?.problems.map((p) => <Notice key={p} tone="warn">{p}</Notice>)}
          {!user.cpf && <Notice tone="warn">Informe seu CPF em Minha Vila no site para pagar.</Notice>}
          {error ? <Notice tone="error">{error}</Notice> : null}
          <Button title={`Confirmar e pagar ${quote ? money(quote.total_cents) : ''}`} variant="brand" busy={busy}
            disabled={!quote?.can_checkout || !addressId || !user.cpf} onPress={confirm} />
        </>
      )}
    </Screen>
  );
}
