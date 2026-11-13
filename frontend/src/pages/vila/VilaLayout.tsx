import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../../lib/auth';

const TABS = [
  { to: '/minha-vila', label: 'Visão geral', end: true },
  { to: '/minha-vila/caes', label: 'Meus cães' },
  { to: '/minha-vila/assinaturas', label: 'Assinaturas' },
  { to: '/minha-vila/entregas', label: 'Entregas e avaliações' },
  { to: '/minha-vila/pedidos', label: 'Pedidos da loja' },
  { to: '/minha-vila/pagamentos', label: 'Pagamentos' },
  { to: '/minha-vila/enderecos', label: 'Endereços' },
  { to: '/minha-vila/dados', label: 'Meus dados' },
  { to: '/minha-vila/atendimento', label: 'Atendimento' },
];

export default function VilaLayout() {
  const { user, logout } = useAuth();
  return (
    <div className="wrap page vila">
      <header className="page__head">
        <p className="eyebrow">Minha Vila</p>
        <h1>Oi, {user?.full_name.split(' ')[0]}.</h1>
        {user?.is_member && <p><span className="badge badge--brand">Membro do Club</span></p>}
      </header>
      <div className="vila__grid">
        <nav className="vila__nav" aria-label="Minha Vila">
          {TABS.map((t) => (
            <NavLink key={t.to} to={t.to} end={t.end}>{t.label}</NavLink>
          ))}
          {user?.is_staff_panel && <a href="/painel/">Painel da equipe ↗</a>}
          <button type="button" className="btn--link" onClick={logout}>Sair</button>
        </nav>
        <section className="vila__content"><Outlet /></section>
      </div>
      <style>{`
        .vila__grid { display: grid; gap: 1.5rem; }
        .vila__nav { display: flex; gap: 0.4rem; overflow-x: auto; padding-bottom: 0.5rem; scrollbar-width: thin; }
        .vila__nav a, .vila__nav button { white-space: nowrap; text-decoration: none; padding: 0.5rem 0.9rem; border-radius: 999px; border: 1.5px solid var(--line); font-weight: 600; font-size: var(--step--1); background: none; }
        .vila__nav a.active { background: var(--fucinho); color: var(--chamego); border-color: var(--fucinho); }
        .vila__content { min-width: 0; display: grid; gap: 1.25rem; align-content: start; }
        @media (min-width: 60rem) {
          .vila__grid { grid-template-columns: 15rem 1fr; align-items: start; }
          .vila__nav { flex-direction: column; position: sticky; top: 6rem; overflow: visible; }
          .vila__nav a, .vila__nav button { border-radius: 0.9rem; text-align: left; }
        }
      `}</style>
    </div>
  );
}
