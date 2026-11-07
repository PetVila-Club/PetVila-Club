import { Link } from 'react-router-dom';
import type { Plan, ProductSummary } from '../api/types';
import { BoxArt, DogArt } from '../components/Brand';
import { PlanCard, ProductCard } from '../components/Cards';
import { Spinner } from '../components/common';
import { useApi } from '../lib/useApi';
import './home.css';

const STEPS = [
  { n: '01', title: 'Escolha sua Vila', copy: 'Dois planos, o mesmo cuidado na escolha de cada produto.' },
  { n: '02', title: 'Conte sobre seu cão', copy: 'Porte, preferências e restrições. Cada cão tem o próprio perfil e o próprio kit.' },
  { n: '03', title: 'Receba todos os meses', copy: 'A curadoria monta, revisa e envia. Você acompanha tudo na Minha Vila.' },
  { n: '04', title: 'Avalie e faça parte', copy: 'Sua avaliação de cada item entregue orienta as próximas curadorias.' },
];

export default function Home() {
  const plans = useApi<Plan[]>('/plans/');
  const products = useApi<ProductSummary[]>('/catalog/products/');

  return (
    <>
      <section className="hero">
        <div className="wrap hero__in">
          <div className="hero__text">
            <p className="eyebrow">Clube de assinatura para cães</p>
            <h1 className="hero__title">Cuidado que faz parte da rotina.</h1>
            <p className="hero__lead">Todo mês, uma nova curadoria PetVila pensada para o seu cão. Brinquedos, snacks, higiene e Refeição Natural, escolhidos com olhar humano e respeito às restrições de cada um.</p>
            <div className="btn-row">
              <Link to="/planos" className="btn btn--brand">Conhecer os planos</Link>
              <Link to="/loja" className="btn btn--ghost">Ir para a loja</Link>
            </div>
          </div>
          <div className="hero__art" aria-hidden="true"><BoxArt /></div>
        </div>
      </section>

      <section className="wrap section">
        <div className="page__head">
          <p className="eyebrow">Como funciona</p>
          <h2>Menos coisas. Mais coisas certas.</h2>
        </div>
        <ol className="steps-grid">
          {STEPS.map((s) => (
            <li key={s.n} className="card">
              <span className="steps-grid__n">{s.n}</span>
              <h3>{s.title}</h3>
              <p className="muted">{s.copy}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="wrap section" aria-labelledby="planos-home">
        <div className="page__head">
          <p className="eyebrow">O Club</p>
          <h2 id="planos-home">Existe um jeito PetVila de cuidar.</h2>
          <p>Assinatura mensal. Cada cão tem o seu kit, montado a partir do perfil que você cadastra.</p>
        </div>
        {plans.loading ? <Spinner /> : (
          <div className="grid grid--2">{plans.data?.map((p) => <PlanCard key={p.code} plan={p} />)}</div>
        )}
      </section>

      <section className="wrap section" aria-labelledby="loja-home">
        <div className="page__head">
          <p className="eyebrow">PetVila Store</p>
          <h2 id="loja-home">A loja é para todos.</h2>
          <p>Produtos escolhidos pelo mesmo olhar da curadoria. Quem é membro do Club vê o preço de membro em itens selecionados.</p>
        </div>
        {products.loading ? <Spinner /> : (
          <div className="grid grid--4">{products.data?.slice(0, 8).map((p) => <ProductCard key={p.slug} product={p} />)}</div>
        )}
        <div className="btn-row" style={{ marginTop: '1.5rem' }}><Link to="/loja" className="btn">Ver toda a loja</Link></div>
      </section>

      <section className="manifesto dark">
        <div className="wrap manifesto__in">
          <div className="manifesto__art" aria-hidden="true"><DogArt /></div>
          <p className="manifesto__text">Cães não são parte da nossa rotina.<br />Eles fazem parte da nossa vida.</p>
          <p>Por isso criamos uma Vila inteira pensando neles.</p>
        </div>
      </section>
    </>
  );
}
