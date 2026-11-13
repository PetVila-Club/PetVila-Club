import { Link } from 'react-router-dom';
import type { Plan, Quote } from '../api/types';
import { useAuth } from '../lib/auth';
import { money } from '../lib/format';
import { useApi } from '../lib/useApi';
import { BoxArt } from './Brand';
import './club.css';

const BENEFITS = [
  { title: 'Um kit por mês, para cada cão', copy: 'Montado a partir do perfil e das restrições que você cadastra.' },
  { title: 'Preço de membro na loja', copy: 'Produto a produto, enquanto a assinatura estiver ativa.' },
  { title: 'PetVila Originals', copy: 'No Vila Care, acesso antecipado e prioridade nos lançamentos.' },
];

/** Faixa de benefícios do Club, usada entre as linhas de produtos. */
export function ClubBand() {
  const { user } = useAuth();
  const plans = useApi<Plan[]>('/plans/');
  if (user?.is_member) return null;

  return (
    <section className="club-band dark" aria-labelledby="club-band-title">
      <div className="club-band__text">
        <h2 id="club-band-title">Faça parte do Club e pague preço de membro.</h2>
        <ul className="club-band__list">
          {BENEFITS.map((b) => (
            <li key={b.title}><strong>{b.title}</strong><span>{b.copy}</span></li>
          ))}
        </ul>
        <Link to="/planos" className="btn btn--brand">Conhecer os planos</Link>
      </div>
      <div className="club-band__plans">
        {plans.data?.map((p) => (
          <Link key={p.code} to="/planos" className={`club-plan ${p.highlight ? 'club-plan--core' : ''}`}>
            <span className="club-plan__name">{p.name}</span>
            <span className="club-plan__tag">{p.tagline}</span>
            <span className="club-plan__price">{p.offer ? <>{money(p.offer.price_cents)}<small> por mês</small></> : 'Preço em breve'}</span>
          </Link>
        ))}
        <div className="club-band__art" aria-hidden="true"><BoxArt /></div>
      </div>
    </section>
  );
}

/** Caixa compacta na página de produto: quanto o membro paga e como virar membro. */
export function ClubNote({ listCents, memberCents }: { listCents: number | null; memberCents: number | null }) {
  const { user } = useAuth();
  if (user?.is_member) {
    return memberCents ? <p className="club-note club-note--on">Você é membro: o preço de membro já está aplicado.</p> : null;
  }
  if (!memberCents || listCents === null || memberCents >= listCents) {
    return (
      <div className="club-note">
        <p><strong>Membros do Club</strong> pagam preço de membro em produtos selecionados da loja.</p>
        <Link to="/planos">Conhecer o Club</Link>
      </div>
    );
  }
  return (
    <div className="club-note">
      <p className="club-note__price"><b>{money(memberCents)}</b> para membros do Club</p>
      <p className="small">Assine o Vila Essential ou o Vila Care e pague o preço de membro neste e em outros produtos.</p>
      <Link to="/planos">Conhecer o Club</Link>
    </div>
  );
}

/** Chamada ligada ao que está no carrinho, por departamento. Não promete composição do kit. */
const HOOK: Record<string, string> = {
  alimentos: 'Quem cuida do que o cão come merece preço de membro.',
  'higiene-e-cuidado': 'Cuidado com o seu cão, todo mês, com preço de membro.',
  mordedores: 'Para o cão que vive mordendo alguma coisa.',
  brinquedos: 'Brincadeira nova todo mês e preço de membro na loja.',
  acessorios: 'Passeio, rotina e um kit do Club todo mês.',
};

/**
 * Oferta do Club no carrinho e no checkout para quem ainda não é assinante: escolhe o plano pelo que está
 * no carrinho e mostra quanto este mesmo pedido custa com preço de membro.
 */
export function ClubCartOffer({ quote, compact = false }: { quote: Quote; compact?: boolean }) {
  const offer = quote.club_offer;
  if (quote.member_pricing || !offer) return null;
  const now = quote.subtotal_cents - quote.discount_cents;
  const savings = quote.club_savings_cents;
  const cheaper = quote.lines.filter((l) => l.member_unit_price_cents < l.unit_price_cents);
  const hook = (offer.department_slug && HOOK[offer.department_slug]) || 'Faça parte do Club e pague preço de membro.';

  return (
    <section className={`club-offer ${compact ? 'club-offer--compact' : ''}`} aria-labelledby="club-offer-title">
      <div className="club-offer__art" aria-hidden="true"><BoxArt /></div>
      <h2 id="club-offer-title">{hook}</h2>
      <p>
        Você está levando <strong>{offer.top_item}</strong>. Assinando o <strong>{offer.plan_name}</strong>, seu cão recebe um kit
        por mês montado pelo perfil dele e você paga preço de membro na loja, a partir deste pedido.
      </p>
      {savings > 0 && (
        <div className="club-offer__deal">
          <span>Este pedido com preço de membro</span>
          <span className="club-offer__prices"><s>{money(now)}</s> <b>{money(quote.member_merchandise_cents)}</b></span>
          <span className="club-offer__save">Você economiza {money(savings)} já nesta compra</span>
        </div>
      )}
      {!compact && cheaper.length > 0 && (
        <ul className="club-offer__items">
          {cheaper.slice(0, 4).map((l) => (
            <li key={l.sku_id}><span>{l.name}</span><span><s>{money(l.unit_price_cents)}</s> {money(l.member_unit_price_cents)}</span></li>
          ))}
        </ul>
      )}
      <div className="club-offer__cta">
        <Link to={`/assinar/${offer.plan_code}?carrinho=1`} className="btn btn--brand">
          {savings > 0 ? `Assinar e levar por ${money(quote.member_merchandise_cents)}` : `Assinar o ${offer.plan_name}`}
        </Link>
        <span className="small">{offer.plan_name}: {money(offer.price_cents)} por mês, por cão. <Link to="/planos">Comparar planos</Link></span>
      </div>
    </section>
  );
}
