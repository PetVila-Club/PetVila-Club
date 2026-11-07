import { Link, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Payment } from '../api/types';
import { Alert, Spinner } from '../components/common';
import { PaymentBox } from '../components/PaymentBox';
import { useAuth } from '../lib/auth';

const FAQ = [
  { q: 'Como funciona a assinatura?', a: 'Você escolhe o plano, cadastra seus cães e autoriza a cobrança mensal. A cada ciclo pago, a curadoria monta o kit de cada cão a partir do perfil, revisa e envia. Tudo aparece na Minha Vila.' },
  { q: 'Tenho dois cães. Eles dividem o kit?', a: 'Não. Cada cão tem a própria assinatura e o próprio kit, com a lista identificada por cão na separação e na entrega.' },
  { q: 'E se meu cão tiver restrições?', a: 'Restrições declaradas funcionam como bloqueio: itens com aqueles ingredientes ou materiais não entram no kit. Itens sem informação suficiente vão para revisão humana. A PetVila não faz diagnóstico nem recomendação clínica.' },
  { q: 'Posso cancelar?', a: 'Sim, pela Minha Vila. Antes da data de corte, nenhuma nova cobrança é feita. Depois do corte, o ciclo que já foi processado é entregue e o cancelamento vale em seguida. A tela informa a data de efeito.' },
  { q: 'Quais formas de pagamento?', a: 'Pix, boleto e cartão de crédito, processados pelo Asaas. Os dados de cartão são informados na página segura do Asaas; a PetVila não recebe nem armazena o número do cartão.' },
  { q: 'Como peço troca, devolução ou meus dados (LGPD)?', a: 'Abra uma solicitação em Minha Vila > Atendimento. Ela gera um protocolo e você acompanha cada etapa até a resposta.' },
];

export function Help() {
  const { user } = useAuth();
  return (
    <div className="wrap page">
      <header className="page__head">
        <p className="eyebrow">Ajuda</p>
        <h1>Como podemos ajudar?</h1>
        <p>Dúvidas frequentes e canais de atendimento. Solicitações de troca, cancelamento e privacidade geram protocolo rastreável.</p>
      </header>
      <div className="grid grid--2" style={{ alignItems: 'start' }}>
        <div className="stack">
          {FAQ.map((f) => (
            <details className="card" key={f.q}>
              <summary style={{ fontWeight: 700, cursor: 'pointer' }}>{f.q}</summary>
              <p style={{ marginTop: '0.75rem' }}>{f.a}</p>
            </details>
          ))}
        </div>
        <aside className="card card--dark stack">
          <h2 style={{ fontSize: 'var(--step-1)' }}>Fale com a Vila</h2>
          <p>E-mail: contato@petvilaclub.com</p>
          <p>Instagram: @petvilaclub</p>
          <Link to={user ? '/minha-vila/atendimento' : '/entrar?next=/minha-vila/atendimento'} className="btn btn--brand">Abrir solicitação com protocolo</Link>
        </aside>
      </div>
    </div>
  );
}

export function Privacy() {
  return (
    <div className="wrap page stack" style={{ maxWidth: '52rem' }}>
      <p className="eyebrow">Documentos</p>
      <h1>Política de privacidade</h1>
      <Alert tone="warn">Texto-base para validação jurídica (PRV-01/02). Finalidades, bases legais e prazos de retenção devem ser aprovados pela assessoria antes do lançamento.</Alert>
      <h2>Quais dados tratamos</h2>
      <p>Identificação e contato do tutor, endereço de entrega, CPF para cobrança, perfil dos cães (porte, peso, idade, preferências e restrições declaradas), histórico de pedidos, entregas e avaliações. Dados de cartão são tratados exclusivamente pelo provedor de pagamento (Asaas).</p>
      <h2>Para que usamos</h2>
      <p>Executar a assinatura e as compras, montar a curadoria de cada cão, emitir cobranças e documentos fiscais, entregar, prestar atendimento e cumprir obrigações legais. Comunicações de marketing só com o seu consentimento, que pode ser alterado a qualquer momento em Minha Vila &gt; Meus dados, sem afetar o serviço.</p>
      <h2>Com quem compartilhamos</h2>
      <p>Provedor de pagamento, transportadoras, emissor fiscal e serviços de hospedagem, apenas no necessário para cada finalidade.</p>
      <h2>Seus direitos</h2>
      <p>Acesso, correção, portabilidade, exclusão e revogação de consentimento, solicitados em Minha Vila &gt; Atendimento, com protocolo e resposta rastreável. Registros sujeitos a retenção legal (por exemplo, fiscais) são preservados pelo prazo exigido, e a resposta explica o tratamento aplicado.</p>
      <p className="small muted">Pet Vila Club LTDA · CNPJ 69.194.320/0001-26 · contato@petvilaclub.com</p>
    </div>
  );
}

export function Terms() {
  return (
    <div className="wrap page stack" style={{ maxWidth: '52rem' }}>
      <p className="eyebrow">Documentos</p>
      <h1>Termos de uso e contratação</h1>
      <Alert tone="warn">Texto-base. Periodicidade, fidelidade, reajuste, frete, trocas e cancelamento dependem das decisões P01–P10 do PDR e de validação jurídica.</Alert>
      <h2>Assinatura</h2>
      <p>A assinatura é mensal, com cobrança recorrente automática no meio escolhido. Cada cão atendido possui uma assinatura própria. O valor e as condições contratadas ficam registrados na versão da oferta aceita; mudanças futuras não alteram ciclos já fechados e só se aplicam conforme a política comunicada.</p>
      <h2>Curadoria</h2>
      <p>A composição do kit segue as quantidades publicadas para o plano. A seleção usa regras de compatibilidade e decisão humana; não há promessa de personalização ilimitada nem de adequação clínica. Substituições por falta de estoque respeitam categoria, quantidade e compatibilidade.</p>
      <h2>Cancelamento e pausa</h2>
      <p>Cancelamentos antes da data de corte impedem novas cobranças. Após o corte, o ciclo já processado é cobrado e entregue. A data de efeito é informada na tela e o histórico é preservado.</p>
      <h2>Compras avulsas</h2>
      <p>Produtos, quantidades, descontos, frete, prazo e total são exibidos antes da confirmação. Pedidos não pagos no prazo são cancelados e a reserva de estoque é liberada.</p>
    </div>
  );
}

export function NotFound() {
  return (
    <div className="wrap page stack">
      <h1>Essa casinha não existe.</h1>
      <p>A página que você procura não está na Vila.</p>
      <Link to="/" className="btn">Voltar ao início</Link>
    </div>
  );
}

/** Destino da fatura no provedor simulado (desenvolvimento local). */
export function SimulatedPayment() {
  const { id } = useParams();
  const { user, loading } = useAuth();
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) return;
    api<Payment[]>('/me/payments/')
      .then((list) => {
        const found = list.find((p) => p.external_id === id);
        if (found) setPayment(found); else setError('Cobrança não encontrada para esta conta.');
      })
      .catch(() => setError('Não foi possível carregar a cobrança.'));
  }, [id, user]);

  if (loading) return <Spinner />;
  if (!user) return <div className="wrap page"><Alert tone="info">Entre na sua conta para ver esta fatura. <Link to={`/entrar?next=/pagamento-simulado/${id}`}>Entrar</Link></Alert></div>;
  return (
    <div className="wrap page stack" style={{ maxWidth: '36rem' }}>
      <p className="eyebrow">Fatura de teste</p>
      <h1>Pagamento simulado</h1>
      <p className="muted">Esta página substitui a fatura do Asaas quando o backend roda sem chave de API.</p>
      {error && <Alert tone="error">{error}</Alert>}
      {payment && <PaymentBox payment={payment} onChange={setPayment} />}
    </div>
  );
}
