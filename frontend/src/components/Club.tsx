import { Link } from 'react-router-dom';
import type { Plan } from '../api/types';
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
