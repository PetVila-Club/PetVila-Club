import { useEffect, useRef, useState } from 'react';
import { Pressable, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import * as WebBrowser from 'expo-web-browser';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { api, date, health, idempotencyKey, money } from '../api';
import type { RootStack } from '../navigation';
import { useAuth, useFetch } from '../state';
import { colors, fonts } from '../theme';
import type { Delivery, Dog, Order, Payment, Plan, Subscription } from '../types';
import { Badge, Button, Card, Choice, DogArt, Field, Loading, Notice, Row, Screen, Text } from '../ui';
import { AddressChoice, BillingChoice } from './Shop';

export function LoginScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [form, setForm] = useState({ email: '', password: '', full_name: '', cpf: '' });
  const [accept, setAccept] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      if (mode === 'login') await login(form.email.trim(), form.password);
      else await register({ ...form, email: form.email.trim(), accept_terms: accept });
    } catch (e: any) {
      setError(e.message === 'No active account found with the given credentials' ? 'E-mail ou senha incorretos.' : e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen>
      <View style={{ alignItems: 'center' }}><DogArt size={110} /></View>
      <Text variant="eyebrow">Minha Vila</Text>
      <Text variant="title">{mode === 'login' ? 'Entrar' : 'Criar conta'}</Text>
      {mode === 'register' && <Field label="Nome completo" value={form.full_name} onChangeText={(v) => setForm({ ...form, full_name: v })} autoComplete="name" />}
      <Field label="E-mail" value={form.email} onChangeText={(v) => setForm({ ...form, email: v })} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
      {mode === 'register' && <Field label="CPF" value={form.cpf} onChangeText={(v) => setForm({ ...form, cpf: v })} keyboardType="number-pad" />}
      <Field label="Senha" value={form.password} onChangeText={(v) => setForm({ ...form, password: v })} secureTextEntry autoComplete="password" />
      {mode === 'register' && <Choice label="Aceito os termos de uso e a política de privacidade" selected={accept} onPress={() => setAccept(!accept)} />}
      {error ? <Notice tone="error">{error}</Notice> : null}
      <Button title={mode === 'login' ? 'Entrar' : 'Criar conta'} variant="brand" busy={busy} onPress={submit} />
      <Button title={mode === 'login' ? 'Ainda não tenho conta' : 'Já tenho conta'} variant="ghost" onPress={() => setMode(mode === 'login' ? 'register' : 'login')} />
    </Screen>
  );
}

export function VilaScreen({ navigation }: any) {
  const { user, logout } = useAuth();
  const subs = useFetch<Subscription[]>('/me/subscriptions/');
  const deliveries = useFetch<Delivery[]>('/me/deliveries/');
  const orders = useFetch<Order[]>('/me/orders/');
  const dogs = useFetch<Dog[]>('/me/dogs/');

  useEffect(() => navigation.addListener('focus', () => { subs.reload(); deliveries.reload(); orders.reload(); dogs.reload(); }), [navigation]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!user) return <LoginScreen />;
  return (
    <Screen>
      <Text variant="eyebrow">Minha Vila</Text>
      <Text variant="title">Oi, {user.full_name.split(' ')[0]}.</Text>
      {user.is_member && <Badge label="Membro do Club" status="active" />}

      <Text variant="h2">Meus cães</Text>
      {dogs.data?.filter((d) => d.is_active).map((d) => (
        <Card key={d.id}>
          <Text style={{ fontFamily: fonts.bold }}>{d.name}</Text>
          <Text variant="small">{d.size || 'porte não informado'}{d.weight_kg ? ` · ${d.weight_kg} kg` : ''}</Text>
          <Text variant="small">Restrições: {d.restrictions_detail.map((t) => t.name).join(', ') || 'nenhuma'}</Text>
          {d.missing_fields.length > 0 && <Notice tone="warn">Complete: {d.missing_fields.join(', ')}</Notice>}
        </Card>
      ))}

      <Text variant="h2">Assinaturas</Text>
      {subs.loading && <Loading />}
      {subs.data?.length === 0 && <Text variant="small">Nenhuma assinatura ainda.</Text>}
      {subs.data?.map((s) => (
        <Pressable key={s.id} onPress={() => navigation.navigate('SubscriptionDetail', { sub: s })} accessibilityRole="button">
          <Card>
            <Row><Text style={{ fontFamily: fonts.bold, flex: 1 }}>{s.plan_name || s.sku_name}{s.dog_name ? ` · ${s.dog_name}` : ''}</Text><Badge label={s.status_label} status={s.status} /></Row>
            <Text variant="small">{s.number} · {money(s.total_per_cycle_cents)}/ciclo · próxima cobrança {date(s.next_billing_date)}</Text>
            {s.pending_payment && <Notice tone="warn">Cobrança aguardando pagamento. Toque para pagar.</Notice>}
          </Card>
        </Pressable>
      ))}

      <Text variant="h2">Entregas</Text>
      {deliveries.data?.length === 0 && <Text variant="small">Nenhuma entrega ainda.</Text>}
      {deliveries.data?.map((d) => (
        <Pressable key={d.id} onPress={() => navigation.navigate('DeliveryDetail', { delivery: d })} accessibilityRole="button">
          <Card>
            <Row><Text style={{ fontFamily: fonts.bold, flex: 1 }}>{d.kind_label} · {d.reference}</Text><Badge label={d.status_label} status={d.status} /></Row>
            <Text variant="small">{d.content_status === 'confirmado' ? 'Conteúdo confirmado' : 'Conteúdo previsto'}{d.tracking_code ? ` · rastreio ${d.tracking_code}` : ''}</Text>
          </Card>
        </Pressable>
      ))}

      <Text variant="h2">Pedidos da loja</Text>
      {orders.data?.length === 0 && <Text variant="small">Nenhum pedido.</Text>}
      {orders.data?.map((o) => (
        <Pressable key={o.id} onPress={() => o.payment && navigation.navigate('Payment', { payment: o.payment, title: `Pedido ${o.number}` })} accessibilityRole="button">
          <Card>
            <Row><Text style={{ fontFamily: fonts.bold }}>{o.number}</Text><Badge label={o.status_label} status={o.status} /></Row>
            <Text variant="small">{money(o.total_cents)}</Text>
          </Card>
        </Pressable>
      ))}
      <Button title="Sair" variant="ghost" onPress={logout} />
    </Screen>
  );
}

export function PaymentScreen({ route }: NativeStackScreenProps<RootStack, 'Payment'>) {
  const [payment, setPayment] = useState<Payment>(route.params.payment);
  const [sandbox, setSandbox] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { health().then((h) => setSandbox(h.payments_fake_mode)).catch(() => undefined); }, []);

  const simulate = async () => {
    try {
      const res = await api<{ payment: Payment }>('/payments/simulate/', { body: { external_id: payment.external_id, outcome: 'paid' } });
      setPayment(res.payment);
    } catch (e: any) {
      setError(e.message);
    }
  };
  return (
    <Screen>
      <Text variant="eyebrow">{route.params.title}</Text>
      <Text variant="title">{payment.is_paid ? 'Pagamento confirmado!' : 'Pagamento'}</Text>
      <Card>
        <Row><Text style={{ fontFamily: fonts.bold }}>{payment.status_label}</Text><Text variant="price">{money(payment.value_cents)}</Text></Row>
        {payment.due_date && <Text variant="small">Vencimento: {date(payment.due_date)}</Text>}
      </Card>
      {!payment.is_paid && payment.pix_payload ? (
        <>
          <Text variant="small">Pix copia e cola:</Text>
          <Card><Text variant="small" selectable>{payment.pix_payload}</Text></Card>
          <Button title={copied ? 'Código copiado!' : 'Copiar código Pix'} variant="brand" onPress={async () => { await Clipboard.setStringAsync(payment.pix_payload); setCopied(true); }} />
        </>
      ) : null}
      {!payment.is_paid && payment.invoice_url ? (
        <Button title={payment.billing_type === 'CREDIT_CARD' ? 'Pagar com cartão (Asaas)' : 'Abrir fatura'} variant="ghost"
          onPress={() => WebBrowser.openBrowserAsync(payment.bank_slip_url || payment.invoice_url)} />
      ) : null}
      <Text variant="small" style={{ color: colors.inkSoft }}>Dados de cartão são informados somente na página segura do Asaas. A confirmação chega automaticamente.</Text>
      {sandbox && !payment.is_paid && (
        <Card>
          <Text variant="small">Ambiente de teste: nenhum valor real é cobrado.</Text>
          <Button title="Simular pagamento aprovado" onPress={simulate} />
        </Card>
      )}
      {error ? <Notice tone="error">{error}</Notice> : null}
    </Screen>
  );
}

export function SubscriptionDetailScreen({ route, navigation }: NativeStackScreenProps<RootStack, 'SubscriptionDetail'>) {
  const [sub, setSub] = useState(route.params.sub);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const act = async (action: 'cancel' | 'pause' | 'resume') => {
    setError('');
    try {
      const res = await api<{ message: string; subscription: Subscription }>(`/me/subscriptions/${sub.id}/${action}/`, { body: {} });
      setSub(res.subscription);
      setMessage(res.message);
    } catch (e: any) {
      setError(e.message);
    }
  };
  const open = !['canceled', 'ended'].includes(sub.status) && !sub.cancel_effective_date;
  return (
    <Screen>
      <Text variant="eyebrow">{sub.number}</Text>
      <Text variant="h2">{sub.plan_name || sub.sku_name}{sub.dog_name ? ` · ${sub.dog_name}` : ''}</Text>
      <Badge label={sub.status_label} status={sub.status} />
      <Card>
        <Row><Text>Valor por ciclo</Text><Text style={{ fontFamily: fonts.bold }}>{money(sub.total_per_cycle_cents)}</Text></Row>
        <Row><Text>Próxima cobrança</Text><Text>{date(sub.next_billing_date)}</Text></Row>
        {sub.next_cutoff_date && <Row><Text>Data de corte</Text><Text>{date(sub.next_cutoff_date)}</Text></Row>}
        {sub.cancel_effective_date && <Row><Text>Cancelamento efetivo</Text><Text>{date(sub.cancel_effective_date)}</Text></Row>}
      </Card>
      {sub.pending_payment && <Button title="Pagar cobrança pendente" variant="brand" onPress={() => navigation.navigate('Payment', { payment: sub.pending_payment!, title: sub.number })} />}
      {message ? <Notice tone="ok">{message}</Notice> : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
      {open && sub.status === 'active' && <Button title="Pausar" variant="ghost" onPress={() => act('pause')} />}
      {open && sub.status === 'paused' && <Button title="Retomar" onPress={() => act('resume')} />}
      {open && (
        <>
          <Text variant="small" style={{ color: colors.inkSoft }}>Antes da data de corte, cancelar impede novas cobranças. Depois dela, o ciclo já processado é entregue e o cancelamento vale em seguida.</Text>
          <Button title="Cancelar assinatura" variant="ghost" onPress={() => act('cancel')} />
        </>
      )}
    </Screen>
  );
}

export function DeliveryDetailScreen({ route }: NativeStackScreenProps<RootStack, 'DeliveryDetail'>) {
  const { delivery } = route.params;
  const [ratings, setRatings] = useState<Record<number, number>>(
    Object.fromEntries(delivery.lines.filter((l) => l.review).map((l) => [l.id, l.review!.rating])),
  );
  const [error, setError] = useState('');
  const rate = async (lineId: number, rating: number) => {
    setError('');
    try {
      await api('/me/reviews/', { body: { shipment_line: lineId, rating } });
      setRatings({ ...ratings, [lineId]: rating });
    } catch (e: any) {
      setError(e.message);
    }
  };
  return (
    <Screen>
      <Text variant="eyebrow">{delivery.number}</Text>
      <Text variant="h2">{delivery.kind_label} · {delivery.reference}</Text>
      <Badge label={delivery.status_label} status={delivery.status} />
      <Text variant="small">{delivery.content_status === 'confirmado' ? 'Estes são os produtos realmente expedidos.' : 'Conteúdo previsto; pode mudar até a expedição.'}</Text>
      {delivery.lines.map((l) => (
        <Card key={l.id}>
          <Text style={{ fontFamily: fonts.bold }}>{l.quantity} × {l.product_name}</Text>
          {l.dog_name && <Text variant="small">Para {l.dog_name}</Text>}
          {delivery.can_review && (
            <Row style={{ justifyContent: 'flex-start' }}>
              {[1, 2, 3, 4, 5].map((n) => (
                <Pressable key={n} onPress={() => rate(l.id, n)} accessibilityRole="button" accessibilityLabel={`Nota ${n}`} hitSlop={8}>
                  <Text style={{ fontSize: 26, color: (ratings[l.id] || 0) >= n ? colors.patinha : colors.line }}>★</Text>
                </Pressable>
              ))}
            </Row>
          )}
        </Card>
      ))}
      {error ? <Notice tone="error">{error}</Notice> : null}
    </Screen>
  );
}

export function SubscribeScreen({ route, navigation }: NativeStackScreenProps<RootStack, 'Subscribe'>) {
  const { user } = useAuth();
  const plan = useFetch<Plan>(`/plans/${route.params.code}/`);
  const dogs = useFetch<Dog[]>(user ? '/me/dogs/' : null);
  const [selected, setSelected] = useState<number[]>([]);
  const [commitment, setCommitment] = useState<number | null>(null);
  const [addressId, setAddressId] = useState<number | null>(null);
  const [billing, setBilling] = useState('PIX');
  const [accept, setAccept] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const key = useRef(idempotencyKey());

  if (!user) return <LoginScreen />;
  if (plan.loading || !plan.data) return <Screen><Loading /></Screen>;
  const p = plan.data;
  if (!p.offer || !p.available) return <Screen><Text variant="h2">{p.name}</Text><Notice>Preço em aprovação. Em breve disponível.</Notice></Screen>;
  const offer = p.offer;
  const months = commitment ?? offer.commitment_options[0] ?? null;

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await api<{ subscriptions: Subscription[] }>('/checkout/subscription/', {
        body: { plan: p.code, dog_ids: selected, address_id: addressId, billing_type: billing, commitment_months: months, offer_id: offer.id, accept_terms: accept },
        headers: { 'Idempotency-Key': key.current },
      });
      const first = res.subscriptions.find((s) => s.pending_payment);
      if (first?.pending_payment) navigation.replace('Payment', { payment: first.pending_payment, title: `${p.name} · ${first.dog_name}` });
      else navigation.goBack();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Text variant="eyebrow">Assinatura</Text>
      <Text variant="title">{p.name}</Text>
      <Text>{money(offer.price_cents)} por mês, por cão. {p.composition?.total_items} itens com curadoria humana.</Text>
      <Text style={{ fontFamily: fonts.bold }}>Para quais cães?</Text>
      {dogs.data?.filter((d) => d.is_active).map((d) => (
        <Choice key={d.id} label={d.name} detail={d.missing_fields.length ? `Complete: ${d.missing_fields.join(', ')}` : `${d.size} · restrições: ${d.restrictions_detail.map((t) => t.name).join(', ') || 'nenhuma'}`}
          selected={selected.includes(d.id)} onPress={() => setSelected((s) => (s.includes(d.id) ? s.filter((x) => x !== d.id) : [...s, d.id]))} />
      ))}
      {!dogs.data?.length && <Notice tone="warn">Cadastre seu cão em Minha Vila no site para assinar.</Notice>}
      {offer.commitment_options.length > 0 && (
        <View style={{ gap: 8 }}>
          <Text style={{ fontFamily: fonts.bold }}>Ciclo (entrega sempre mensal)</Text>
          {offer.commitment_options.map((m) => <Choice key={m} label={`${m} meses`} selected={months === m} onPress={() => setCommitment(m)} />)}
        </View>
      )}
      <AddressChoice value={addressId} onChange={setAddressId} />
      <BillingChoice value={billing} onChange={setBilling} />
      <Card>
        <Row><Text>Total mensal</Text><Text variant="price">{money((offer.price_cents + offer.shipping_cents) * selected.length)}</Text></Row>
        <Text variant="small">Cobrança recorrente automática, uma por cão. A curadoria começa após a confirmação do pagamento.</Text>
      </Card>
      <Choice label={`Aceito as condições da assinatura (oferta v${offer.version}) e autorizo a cobrança recorrente`} selected={accept} onPress={() => setAccept(!accept)} />
      {error ? <Notice tone="error">{error}</Notice> : null}
      <Button title="Confirmar assinatura" variant="brand" busy={busy} disabled={!accept || !selected.length || !addressId || !user.cpf} onPress={submit} />
    </Screen>
  );
}
