import { Link } from 'react-router-dom';
import type { Plan, ProductSummary } from '../api/types';
import { money } from '../lib/format';
import { DogArt } from './Brand';
import './cards.css';

const CATEGORY_HUE: Record<string, string> = {
  brinquedo: 'var(--patinha)', 'snack-padrao': 'var(--terra)', 'snack-natural': '#7a5b2e', higiene: '#6f7f5a',
  'refeicao-natural': '#a8401a', racao: 'var(--terra)', biobone: '#8b5a2b', passeio: 'var(--fucinho)',
};

export function ProductPicture({ product, large = false }: { product: ProductSummary; large?: boolean }) {
  if (product.picture) {
    return <img className={`pic ${large ? 'pic--lg' : ''}`} src={product.picture} alt="" loading="lazy" />;
  }
  return (
    <div className={`pic pic--art ${large ? 'pic--lg' : ''}`} style={{ ['--hue' as string]: CATEGORY_HUE[product.category.slug] || 'var(--terra)' }} aria-hidden="true">
      <DogArt />
      <span>{product.category.name}</span>
    </div>
  );
}

export function ProductCard({ product }: { product: ProductSummary }) {
  const member = product.from_price_cents !== null && product.from_list_price_cents !== null && product.from_price_cents < product.from_list_price_cents;
  return (
    <article className="pcard">
      <Link to={`/loja/${product.slug}`} className="pcard__link">
        <ProductPicture product={product} />
        <div className="pcard__body">
          <p className="pcard__cat small muted">{product.category.name}</p>
          <h3 className="pcard__name">{product.name}</h3>
          <p className="pcard__price">
            {member && <span className="price--old">{money(product.from_list_price_cents)}</span>}
            <span className="price">{money(product.from_price_cents)}</span>
            {member && <span className="badge badge--brand">Preço de membro</span>}
          </p>
          {!product.sellable && <span className="badge badge--warn">Indisponível</span>}
          {product.is_recurring_food && <span className="badge">Também em recorrência</span>}
        </div>
      </Link>
    </article>
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
      {plan.composition && (
        <ul className="plan__items" aria-label={`Composição do ${plan.name}`}>
          {plan.composition.lines.filter((l) => l.quantity > 0).map((l) => (
            <li key={l.category}><b>{l.quantity}</b> {l.category_name}</li>
          ))}
          <li className="plan__total"><b>{plan.composition.total_items}</b> itens por mês</li>
        </ul>
      )}
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
