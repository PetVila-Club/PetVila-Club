import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { useCart } from '../lib/cart';
import { Logo } from './Brand';
import './layout.css';

export function Layout() {
  const { user } = useAuth();
  const { count } = useCart();
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <>
      <a href="#conteudo" className="skip-link">Pular para o conteúdo</a>
      <header className="hdr">
        <div className="hdr__in wrap">
          <Link to="/" className="hdr__home" aria-label="PetVila Club, início"><Logo height="2.2rem" /></Link>
          <button type="button" className="hdr__menu" aria-expanded={open} aria-controls="menu-principal" onClick={() => setOpen((v) => !v)}>
            <span className="visually-hidden">Menu</span>
            <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          </button>
          <nav id="menu-principal" className={`hdr__nav ${open ? 'is-open' : ''}`} aria-label="Principal">
            <NavLink to="/planos">Planos</NavLink>
            <NavLink to="/loja">Loja</NavLink>
            <NavLink to="/loja?food=1">Ração recorrente</NavLink>
            <NavLink to="/ajuda">Ajuda</NavLink>
            <NavLink to={user ? '/minha-vila' : '/entrar'} className="hdr__account">
              {user ? `Minha Vila` : 'Entrar'}
            </NavLink>
            <NavLink to="/carrinho" className="hdr__cart" aria-label={`Carrinho, ${count} ${count === 1 ? 'item' : 'itens'}`}>
              <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M4 5h2l2.2 10.2a2 2 0 0 0 2 1.6h6.6a2 2 0 0 0 2-1.5L20 9H7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /><circle cx="10" cy="20" r="1.4" fill="currentColor" /><circle cx="17" cy="20" r="1.4" fill="currentColor" /></svg>
              <span className="hdr__badge" aria-hidden="true">{count}</span>
            </NavLink>
          </nav>
        </div>
      </header>
      <main id="conteudo" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="ftr dark">
        <div className="wrap ftr__in">
          <div className="ftr__brand">
            <Logo tone="light" height="2.4rem" />
            <p>Cuidado que faz parte da rotina.</p>
          </div>
          <nav aria-label="Rodapé" className="ftr__nav">
            <Link to="/planos">Planos</Link>
            <Link to="/loja">Loja</Link>
            <Link to="/minha-vila">Minha Vila</Link>
            <Link to="/ajuda">Ajuda e atendimento</Link>
            <Link to="/privacidade">Privacidade</Link>
            <Link to="/termos">Termos de contratação</Link>
          </nav>
          <p className="ftr__legal small">Pet Vila Club LTDA · CNPJ 69.194.320/0001-26 · contato@petvilaclub.com</p>
        </div>
      </footer>
    </>
  );
}
