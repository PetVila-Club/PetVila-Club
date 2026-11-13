import { useEffect, useState, type FormEvent } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import type { Category } from '../api/types';
import { useAuth } from '../lib/auth';
import { useCart } from '../lib/cart';
import { useApi } from '../lib/useApi';
import { Logo } from './Brand';
import './layout.css';

function SearchBox({ id }: { id: string }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const location = useLocation();
  const current = location.pathname === '/loja' ? params.get('q') || '' : '';
  const [value, setValue] = useState(current);
  useEffect(() => setValue(current), [current]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    navigate(q ? `/loja?q=${encodeURIComponent(q)}` : '/loja');
  };

  return (
    <form className="search" role="search" onSubmit={submit}>
      <label htmlFor={id} className="visually-hidden">Buscar produtos</label>
      <input id={id} type="search" value={value} onChange={(e) => setValue(e.target.value)} placeholder="O que o seu cão precisa hoje?" />
      <button type="submit" aria-label="Buscar">
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="2" /><path d="m16 16 4.5 4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
      </button>
    </form>
  );
}

export function Layout() {
  const { user } = useAuth();
  const { count } = useCart();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const [params] = useSearchParams();
  const categories = useApi<Category[]>('/catalog/categories/');
  const activeCategory = location.pathname === '/loja' ? params.get('category') : null;
  const foodActive = location.pathname === '/loja' && params.get('food') === '1';

  useEffect(() => {
    setOpen(false);
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <>
      <a href="#conteudo" className="skip-link">Pular para o conteúdo</a>
      <div className="topbar">
        <div className="wrap topbar__in">
          {user?.is_member ? (
            <p>Você é membro do Club: o preço de membro já aparece nos produtos.</p>
          ) : (
            <p>Membros do Club pagam <strong>preço de membro</strong> em produtos da loja. <Link to="/planos">Conheça o Club</Link></p>
          )}
        </div>
      </div>
      <header className="hdr">
        <div className="hdr__in wrap">
          <button type="button" className="hdr__icon hdr__menu" aria-expanded={open} aria-controls="menu-categorias" onClick={() => setOpen((v) => !v)}>
            <span className="visually-hidden">Categorias</span>
            <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          </button>
          <Link to="/" className="hdr__home" aria-label="PetVila Club, início"><Logo height="2.1rem" /></Link>
          <div className="hdr__search"><SearchBox id="busca-topo" /></div>
          <div className="hdr__actions">
            <Link to="/planos" className="hdr__club">Club PetVila</Link>
            <NavLink to={user ? '/minha-vila' : '/entrar'} className="hdr__icon" aria-label={user ? 'Minha Vila' : 'Entrar'}>
              <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><circle cx="12" cy="8.5" r="3.8" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M4.5 20c1.2-3.6 4-5.4 7.5-5.4s6.3 1.8 7.5 5.4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
              <span className="hdr__icon-label">{user ? 'Minha Vila' : 'Entrar'}</span>
            </NavLink>
            <NavLink to="/carrinho" className="hdr__icon hdr__cart" aria-label={`Carrinho, ${count} ${count === 1 ? 'item' : 'itens'}`}>
              <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M4 5h2l2.2 10.2a2 2 0 0 0 2 1.6h6.6a2 2 0 0 0 2-1.5L20 9H7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /><circle cx="10" cy="20" r="1.4" fill="currentColor" /><circle cx="17" cy="20" r="1.4" fill="currentColor" /></svg>
              {count > 0 && <span className="hdr__badge" aria-hidden="true">{count}</span>}
            </NavLink>
          </div>
        </div>
        <div className="wrap hdr__search-mobile"><SearchBox id="busca-celular" /></div>
        <nav id="menu-categorias" className={`cats ${open ? 'is-open' : ''}`} aria-label="Categorias da loja">
          <div className="wrap cats__in">
            <Link to="/loja" className={location.pathname === '/loja' && !activeCategory && !foodActive ? 'active' : ''}>Todos os produtos</Link>
            {categories.data?.map((c) => (
              <Link key={c.slug} to={`/loja?category=${c.slug}`} className={activeCategory === c.slug ? 'active' : ''}>{c.name}</Link>
            ))}
            <Link to="/loja?food=1" className={foodActive ? 'active' : ''}>Ração recorrente</Link>
            <NavLink to="/planos" className="cats__club">Club PetVila</NavLink>
          </div>
        </nav>
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
          <nav aria-label="Loja" className="ftr__col">
            <p className="ftr__title">Loja</p>
            <Link to="/loja">Todos os produtos</Link>
            {categories.data?.slice(0, 5).map((c) => <Link key={c.slug} to={`/loja?category=${c.slug}`}>{c.name}</Link>)}
            <Link to="/loja?food=1">Ração recorrente</Link>
          </nav>
          <nav aria-label="Club" className="ftr__col">
            <p className="ftr__title">Club</p>
            <Link to="/planos">Planos</Link>
            <Link to="/minha-vila">Minha Vila</Link>
          </nav>
          <nav aria-label="Ajuda" className="ftr__col">
            <p className="ftr__title">Ajuda</p>
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
