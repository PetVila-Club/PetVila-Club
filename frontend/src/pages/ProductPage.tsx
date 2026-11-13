import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { Product, ProductSummary } from '../api/types';
import { ProductPicture, ProductRow } from '../components/Cards';
import { ClubNote } from '../components/Club';
import { Alert, Spinner } from '../components/common';
import { useCart } from '../lib/cart';
import { money, SIZE_LABEL } from '../lib/format';
import { useApi } from '../lib/useApi';
import './product.css';

export default function ProductPage() {
  const { slug } = useParams();
  const { data: product, loading, error } = useApi<Product>(`/catalog/products/${slug}/`);
  const [skuId, setSkuId] = useState<number | null>(null);
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);
  const cart = useCart();
  const navigate = useNavigate();
  const related = useApi<ProductSummary[]>(product ? `/catalog/products/?category=${product.category.slug}` : null);

  useEffect(() => {
    if (product && skuId === null) setSkuId(product.skus.find((s) => s.sellable)?.id ?? product.skus[0]?.id ?? null);
  }, [product, skuId]);

  if (loading) return <Spinner />;
  if (error || !product) return <div className="wrap page"><Alert tone="error">{error?.message || 'Produto não encontrado.'}</Alert></div>;

  const sku = product.skus.find((s) => s.id === skuId) || product.skus[0];
  const member = sku && sku.price_cents !== null && sku.list_price_cents !== null && sku.price_cents < sku.list_price_cents;

  const add = () => {
    if (!sku) return;
    cart.add({ sku_id: sku.id, quantity: qty, name: `${product.name}${sku.variant_name ? ' · ' + sku.variant_name : ''}` });
    setAdded(true);
  };

  return (
    <div className="wrap pdp">
      <nav className="small muted pdp__crumbs" aria-label="Trilha"><Link to="/">Início</Link> / <Link to="/loja">Loja</Link> / <Link to={`/loja?category=${product.category.slug}`}>{product.category.name}</Link></nav>
      <div className="pdp__grid">
        <div className="pdp__media"><ProductPicture product={product} large /></div>
        <div className="pdp__info">
          <p className="pdp__cat">{product.category.name}</p>
          <h1 className="pdp__name">{product.name}</h1>
          {sku && (
            <p className="pdp__price">
              {member && <span className="price--old">{money(sku.list_price_cents)}</span>}
              <span className="price">{money(sku.price_cents)}</span>
              {member && <span className="badge badge--brand">Preço de membro</span>}
            </p>
          )}
          {sku && <ClubNote listCents={sku.list_price_cents} memberCents={sku.member_price_cents} />}
          {product.skus.length > 1 && (
            <fieldset>
              <legend>Variante</legend>
              <div className="choice-grid">
                {product.skus.map((s) => (
                  <label className="choice" key={s.id}>
                    <input type="radio" name="sku" checked={s.id === sku?.id} onChange={() => setSkuId(s.id)} disabled={!s.sellable} />
                    <strong>{s.variant_name || s.unit_description}</strong>
                    <span className="small">{money(s.price_cents)}{!s.sellable ? ' · indisponível' : ''}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          {sku && (
            <p className="small muted">
              Unidade: {sku.unit_description}{sku.variant_name ? ` · ${sku.variant_name}` : ''} · SKU {sku.code}
              {sku.net_weight_g ? ` · ${sku.net_weight_g} g` : ''}
            </p>
          )}
          {sku?.sellable ? (
            <div className="btn-row">
              <div className="qty" aria-label="Quantidade">
                <button type="button" onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="Diminuir">−</button>
                <span aria-live="polite">{qty}</span>
                <button type="button" onClick={() => setQty((q) => Math.min(sku.available, q + 1))} aria-label="Aumentar">+</button>
              </div>
              <button type="button" className="btn btn--brand pdp__add" onClick={add}>Adicionar ao carrinho</button>
            </div>
          ) : (
            <Alert tone="warn">Indisponível para venda no momento.</Alert>
          )}
          {added && (
            <Alert tone="ok">
              Adicionado ao carrinho. <button type="button" className="btn--link" onClick={() => navigate('/carrinho')}>Ver carrinho</button>
            </Alert>
          )}
          {product.is_recurring_food && sku && (
            <div className="card card--dark stack">
              <h3>Receba em recorrência</h3>
              <p>Mesma ração, mesma quantidade, na frequência que você escolher. Calendário independente do kit.</p>
              <Link to={`/assinar-racao/${product.slug}/${sku.id}`} className="btn btn--brand">Assinar esta ração</Link>
            </div>
          )}
          <div className="stack pdp__about">
            <h2>Sobre o produto</h2>
            <p>{product.description}</p>
            {sku && sku.contains.length > 0 && <p className="small"><strong>Composição/materiais:</strong> {sku.contains.map((t) => t.name).join(', ')}</p>}
            {sku && sku.suitable_sizes.length > 0 && <p className="small"><strong>Indicado para porte:</strong> {sku.suitable_sizes.map((s) => SIZE_LABEL[s] || s).join(', ')}</p>}
            {product.conservation && <p className="small"><strong>Conservação:</strong> {product.conservation}</p>}
            <p className="small muted">Informações de produto não substituem orientação veterinária.</p>
          </div>
        </div>
      </div>
      <div className="pdp__related">
        <ProductRow title="Você também pode gostar" link={`/loja?category=${product.category.slug}`}
          products={(related.data || []).filter((p) => p.slug !== product.slug).slice(0, 4)} />
      </div>
    </div>
  );
}
