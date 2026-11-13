import { Link } from 'react-router-dom';
import type { Department, ProductSummary } from '../api/types';
import { BoxArt, DogArt } from '../components/Brand';
import { ProductRow } from '../components/Cards';
import { ClubBand } from '../components/Club';
import { Spinner } from '../components/common';
import { departmentOf, hueFor } from '../lib/departments';
import { useApi } from '../lib/useApi';
import './home.css';

export default function Home() {
  const products = useApi<ProductSummary[]>('/catalog/products/');
  const departments = useApi<Department[]>('/catalog/departments/');
  const all = products.data || [];

  // Destaques: um produto de cada departamento por rodada, priorizando quem tem preço de membro.
  const pool = [...all].filter((p) => p.sellable && departmentOf(p))
    .sort((a, b) => Number(b.from_member_price_cents !== null) - Number(a.from_member_price_cents !== null));
  const groups = new Map<string, ProductSummary[]>();
  pool.forEach((p) => { const d = departmentOf(p)!; groups.set(d, [...(groups.get(d) || []), p]); });
  const highlights: ProductSummary[] = [];
  for (let round = 0; highlights.length < 8 && round < 4; round += 1) {
    groups.forEach((items) => { if (items[round] && highlights.length < 8) highlights.push(items[round]); });
  }
  const byDepartment = (slug: string) => all.filter((p) => departmentOf(p) === slug && p.sellable).slice(0, 4);
  const rows = (departments.data || []).filter((d) => byDepartment(d.slug).length >= 4);

  return (
    <>
      <section className="hero-shop">
        <div className="wrap hero-shop__grid">
          <Link to="/loja" className="banner banner--main">
            <div className="banner__text">
              <h1>Tudo o que o seu cão ama, escolhido com cuidado.</h1>
              <p>Brinquedos, snacks, higiene, Refeição Natural e ração, com o mesmo olhar da curadoria PetVila.</p>
              <span className="btn btn--brand">Ver produtos</span>
            </div>
            <div className="banner__art" aria-hidden="true"><BoxArt /></div>
          </Link>
          <Link to="/planos" className="banner banner--club">
            <div className="banner__text">
              <h2>Club PetVila</h2>
              <p>Kit mensal para cada cão e preço de membro na loja.</p>
              <span className="btn btn--ghost">Conhecer os planos</span>
            </div>
            <div className="banner__dog" aria-hidden="true"><DogArt /></div>
          </Link>
        </div>
      </section>

      {departments.data && departments.data.length > 0 && (
        <nav className="wrap cat-tiles" aria-label="Compre por categoria">
          {departments.data.map((d) => (
            <Link key={d.slug} to={`/loja?section=${d.slug}`} className="cat-tile" style={{ ['--hue' as string]: hueFor(d.slug) }}>
              <span className="cat-tile__art" aria-hidden="true"><DogArt /></span>
              <span className="cat-tile__name">{d.name}</span>
              {d.children.length > 0 && <span className="cat-tile__subs">{d.children.slice(0, 3).map((c) => c.name).join(' · ')}</span>}
            </Link>
          ))}
          <Link to="/loja?food=1" className="cat-tile" style={{ ['--hue' as string]: 'var(--terra)' }}>
            <span className="cat-tile__art" aria-hidden="true"><DogArt /></span>
            <span className="cat-tile__name">Ração recorrente</span>
          </Link>
        </nav>
      )}

      <div className="wrap home-stack">
        {products.loading ? <Spinner /> : <ProductRow title="Destaques da Vila" link="/loja" products={highlights} />}
        <ClubBand />
        {rows.map((d) => (
          <ProductRow key={d.slug} title={d.name} link={`/loja?section=${d.slug}`} products={byDepartment(d.slug)} />
        ))}
        <ul className="assurances" aria-label="Por que comprar na PetVila">
          <li><strong>Curadoria com olhar humano</strong><span>Cada produto passa pela mesma escolha dos kits do Club.</span></li>
          <li><strong>Pix, boleto ou cartão</strong><span>Pagamento seguro; o cartão é pago no ambiente do Asaas.</span></li>
          <li><strong>Tudo na Minha Vila</strong><span>Pedidos, entregas e atendimento com protocolo em um só lugar.</span></li>
        </ul>
      </div>
    </>
  );
}
