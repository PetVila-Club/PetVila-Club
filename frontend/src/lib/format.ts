const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export function money(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return '—';
  return brl.format(cents / 100);
}

const dateFmt = new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', year: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat('pt-BR', {
  timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
});

export function date(value: string | null | undefined): string {
  if (!value) return '—';
  // Datas sem horário (AAAA-MM-DD) não devem sofrer deslocamento de fuso.
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split('-');
    return `${d}/${m}/${y}`;
  }
  return dateFmt.format(new Date(value));
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return '—';
  return dateTimeFmt.format(new Date(value));
}

export const SIZE_LABEL: Record<string, string> = { pequeno: 'Pequeno', medio: 'Médio', grande: 'Grande' };
export const BILLING_LABEL: Record<string, string> = { PIX: 'Pix', BOLETO: 'Boleto', CREDIT_CARD: 'Cartão de crédito' };

export function cepMask(value: string): string {
  const d = value.replace(/\D/g, '').slice(0, 8);
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
}

export function cpfMask(value: string): string {
  const d = value.replace(/\D/g, '').slice(0, 11);
  return d
    .replace(/^(\d{3})(\d)/, '$1.$2')
    .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1-$2');
}

export function statusTone(status: string): 'ok' | 'warn' | 'danger' | '' {
  if (['active', 'paid', 'delivered', 'shipped', 'resolved', 'CONFIRMED', 'RECEIVED'].includes(status)) return 'ok';
  if (['canceled', 'payment_failed', 'past_due', 'refunded', 'OVERDUE', 'DELETED', 'REFUNDED'].includes(status)) return 'danger';
  if (['pending', 'pending_payment', 'awaiting_payment', 'paused', 'PENDING', 'received', 'waiting_customer'].includes(status)) return 'warn';
  return '';
}
