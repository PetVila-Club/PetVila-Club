import { useEffect, useState } from 'react';
import { api, health } from '../api/client';
import type { Payment } from '../api/types';
import { date, money } from '../lib/format';
import { errorMessage } from '../lib/useApi';
import { Alert } from './common';

/**
 * Mostra como pagar uma cobrança do Asaas: Pix copia e cola/QR, boleto ou fatura hospedada (cartão).
 * Dados de cartão nunca passam pela PetVila: o pagamento com cartão acontece na página do Asaas.
 */
export function PaymentBox({ payment, onChange }: { payment: Payment; onChange?: (p: Payment) => void }) {
  const [copied, setCopied] = useState(false);
  const [sandbox, setSandbox] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    health().then((h) => setSandbox(Boolean(h.payments_fake_mode))).catch(() => setSandbox(false));
  }, []);

  if (payment.is_paid) {
    return <Alert tone="ok">Pagamento confirmado em {date(payment.confirmed_at)}. Obrigado!</Alert>;
  }
  if (payment.status === 'DELETED' || payment.status === 'REFUNDED') {
    return <Alert tone="warn">Cobrança {payment.status_label.toLowerCase()}.</Alert>;
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(payment.pix_payload);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  };

  const simulate = async (outcome: 'paid' | 'overdue') => {
    setBusy(true);
    setError('');
    try {
      const res = await api<{ payment: Payment }>('/payments/simulate/', { body: { external_id: payment.external_id, outcome } });
      onChange?.(res.payment);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card card--strong stack" aria-live="polite">
      <div className="summary__row">
        <strong>{payment.status_label}</strong>
        <span className="price">{money(payment.value_cents)}</span>
      </div>
      {payment.due_date && <p className="small muted">Vencimento: {date(payment.due_date)}</p>}

      {payment.billing_type === 'PIX' && payment.pix_payload && (
        <div className="stack">
          {payment.pix_qr_image && (
            <img src={`data:image/png;base64,${payment.pix_qr_image}`} alt="QR Code Pix para pagamento" width={220} height={220} style={{ margin: '0 auto' }} />
          )}
          <p className="small">Pix copia e cola:</p>
          <div className="code-box">{payment.pix_payload}</div>
          <button type="button" className="btn btn--brand btn--block" onClick={copy}>{copied ? 'Código copiado!' : 'Copiar código Pix'}</button>
        </div>
      )}
      {payment.billing_type === 'BOLETO' && payment.bank_slip_url && (
        <a className="btn btn--brand btn--block" href={payment.bank_slip_url} target="_blank" rel="noreferrer">Abrir boleto</a>
      )}
      {payment.invoice_url && (
        <a className="btn btn--ghost btn--block" href={payment.invoice_url} target="_blank" rel="noreferrer">
          {payment.billing_type === 'CREDIT_CARD' ? 'Pagar com cartão na página segura do Asaas' : 'Ver fatura completa'}
        </a>
      )}
      <p className="small muted">A confirmação chega automaticamente. Você pode acompanhar em Minha Vila &gt; Pagamentos.</p>

      {sandbox && (
        <div className="alert alert--warn stack" style={{ ['--stack' as string]: '0.6rem' }}>
          <p><strong>Ambiente de teste:</strong> nenhum valor real é cobrado. Simule o retorno do provedor:</p>
          <div className="btn-row">
            <button type="button" className="btn btn--sm" disabled={busy} onClick={() => simulate('paid')}>Simular pagamento aprovado</button>
            <button type="button" className="btn btn--sm btn--ghost" disabled={busy} onClick={() => simulate('overdue')}>Simular vencimento</button>
          </div>
          {error && <p className="field__error">{error}</p>}
        </div>
      )}
    </div>
  );
}
