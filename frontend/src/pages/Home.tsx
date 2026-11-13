import { Link } from 'react-router-dom';
import type { Category, ProductSummary } from '../api/types';
import { BoxArt, DogArt } from '../components/Brand';
import { categoryHue, ProductRow } from '../components/Cards';
import { ClubBand } from '../components/Club';
import { Spinner } from '../components/common';
import { useApi } from '../lib/useApi';
import './home.css';

export default function Home() {
  const products = useApi<ProductSummary[]>('/catalog/products/');
  const categories = useApi<Category[]>('/catalog/categories/');
  const all = products.data || [];

  // Destaques: um produto de cada categoria por rodada, priorizando quem tem preço de membro.
  const pool = [...all].filter((p) => p.sellable)
    .sort((a, b) => Number(b.from_member_price_cents !== null) - Number(a.from_member_price_cents !== null));
  const groups = new Map<string, ProductSummary[]>();
  pool.forEach((p) => groups.set(p.category.slug, [...(groups.get(p.category.slug) || []), p]));
  const highlights: ProductSummary[] = [];
  for (let round = 0; highlights.length < 8 && round < 4; round += 1) {
    groups.forEach((items) => { if (items[round] && highlights.length < 8) highlights.push(items[round]); });
  }
  const byCategory = (slug: string) => all.filter((p) => p.category.slug === slug).slice(0, 4);
  const rows = (categories.data || []).filter((c) => byCategory(c.slug).length >= 4).slice(0, 3);

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

      {categories.data && categories.data.length > 0 && (
        <nav className="wrap cat-tiles" aria-label="Compre por categoria">
          {categories.data.map((c) => (
            <Link key={c.slug} to={`/loja?category=${c.slug}`} className="cat-tile" style={{ ['--hue' as string]: categoryHue(c.slug) }}>
              <span className="cat-tile__art" aria-hidden="true"><DogArt /></span>
              <span className="cat-tile__name">{c.name}</span>
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
        {rows.map((c) => (
          <ProductRow key={c.slug} title={c.name} link={`/loja?category=${c.slug}`} products={byCategory(c.slug)} />
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
