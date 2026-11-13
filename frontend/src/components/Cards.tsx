import { Link } from 'react-router-dom';
import type { Plan, ProductSummary } from '../api/types';
import { useAuth } from '../lib/auth';
import { money } from '../lib/format';
import { DogArt } from './Brand';
import './cards.css';

const CATEGORY_HUE: Record<string, string> = {
  brinquedo: 'var(--patinha)', 'snack-padrao': 'var(--terra)', 'snack-natural': '#7a5b2e', higiene: '#6f7f5a',
  'refeicao-natural': '#a8401a', racao: 'var(--terra)', biobone: '#8b5a2b', passeio: 'var(--fucinho)',
};

export function categoryHue(slug: string) {
  return CATEGORY_HUE[slug] || 'var(--terra)';
}

export function ProductPicture({ product, large = false }: { product: ProductSummary; large?: boolean }) {
  if (product.picture) {
    return <img className={`pic ${large ? 'pic--lg' : ''}`} src={product.picture} alt="" loading="lazy" />;
  }
  return (
    <div className={`pic pic--art ${large ? 'pic--lg' : ''}`} style={{ ['--hue' as string]: categoryHue(product.category.slug) }} aria-hidden="true">
      <DogArt />
    </div>
  );
}

/** Preço da vitrine: quem é membro vê o preço de membro aplicado; quem não é vê quanto pagaria no Club. */
export function ProductCard({ product }: { product: ProductSummary }) {
  const { user } = useAuth();
  const memberApplied = product.from_price_cents !== null && product.from_list_price_cents !== null
    && product.from_price_cents < product.from_list_price_cents;
  const memberOffer = !memberApplied && !user?.is_member && product.from_member_price_cents !== null;

  return (
    <article className="pcard">
      <Link to={`/loja/${product.slug}`} className="pcard__link">
        <div className="pcard__media">
          <ProductPicture product={product} />
          <div className="pcard__flags">
            {product.is_recurring_food && <span className="flag">Recorrência</span>}
            {!product.sellable && <span className="flag flag--off">Esgotado</span>}
          </div>
        </div>
        <div className="pcard__body">
          <p className="pcard__cat">{product.category.name}</p>
          <h3 className="pcard__name">{product.name}</h3>
          <div className="pcard__price">
            {memberApplied && <span className="price--old">{money(product.from_list_price_cents)}</span>}
            <span className="price">{money(product.from_price_cents)}</span>
          </div>
          {memberApplied && <p className="pcard__club">Seu preço de membro</p>}
          {memberOffer && (
            <p className="pcard__club"><b>{money(product.from_member_price_cents)}</b> para membros do Club</p>
          )}
        </div>
      </Link>
    </article>
  );
}

/** Linha de produtos com título e link "Ver tudo"; no celular vira carrossel horizontal. */
export function ProductRow({ title, link, products }: { title: string; link?: string; products: ProductSummary[] }) {
  if (!products.length) return null;
  return (
    <section className="prow" aria-label={title}>
      <div className="prow__head">
        <h2>{title}</h2>
        {link && <Link to={link} className="prow__all">Ver tudo</Link>}
      </div>
      <div className="prow__list">{products.map((p) => <ProductCard key={p.slug} product={p} />)}</div>
    </section>
  );
}

export function PlanCard({ plan, cta = true }: { plan: Plan; cta?: boolean }) {
  return (
    <article className={`plan ${plan.highlight ? 'plan--core' : ''}`} aria-labelledby={`plan-${plan.code}`}>
      <div className="plan__blob" aria-hidden="true" />
      {plan.highlight && <span className="badge badge--brand plan__flag">Experiência completa</span>}
      <h3 id={`plan-${plan.code}`} className="plan__name">{plan.name}</h3>
      <p className="plan__tagline">{plan.tagline}</p>
      <p className="plan__copy">{plan.description}</p>
      {plan.extras.map((extra) => (
        <div className="plan__originals" key={extra.title}>
          <p className="plan__originals-title">★ {extra.title}</p>
          <p className="small">{extra.copy}</p>
        </div>
      ))}
      <div className="plan__foot">
        {plan.offer ? (
          <p><span className="price">{money(plan.offer.price_cents)}</span><span className="price__note"> por mês</span></p>
        ) : (
          <p className="price__note">Preço em aprovação. Em breve disponível para assinatura.</p>
        )}
        {cta && (plan.available ? (
          <Link to={`/assinar/${plan.code}`} className="btn btn--brand btn--block">Assinar o {plan.name}</Link>
        ) : (
          <span className="btn btn--ghost btn--block" aria-disabled="true">Em breve</span>
        ))}
      </div>
    </article>
  );
}
