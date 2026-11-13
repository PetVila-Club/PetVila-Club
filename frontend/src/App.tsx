import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { RequireAuth } from './components/common';
import { AuthProvider } from './lib/auth';
import { CartProvider } from './lib/cart';
import { Login, Register } from './pages/Auth';
import Cart from './pages/Cart';
import Checkout from './pages/Checkout';
import Home from './pages/Home';
import OrderConfirmation from './pages/OrderConfirmation';
import Plans from './pages/Plans';
import ProductPage from './pages/ProductPage';
import { Help, NotFound, Privacy, SimulatedPayment, Terms } from './pages/Static';
import Store from './pages/Store';
import SubscribeFood from './pages/SubscribeFood';
import SubscribePlan from './pages/SubscribePlan';
import SubscriptionConfirmation from './pages/SubscriptionConfirmation';
import { Addresses, Orders, Payments, Profile, Support } from './pages/vila/Account';
import Deliveries from './pages/vila/Deliveries';
import Dogs from './pages/vila/Dogs';
import Overview from './pages/vila/Overview';
import Subscriptions from './pages/vila/Subscriptions';
import VilaLayout from './pages/vila/VilaLayout';

const guard = (el: React.ReactNode) => <RequireAuth>{el}</RequireAuth>;

export default function App() {
  return (
    <AuthProvider>
      <CartProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Home />} />
              <Route path="planos" element={<Plans />} />
              <Route path="loja" element={<Store />} />
              <Route path="loja/:slug" element={<ProductPage />} />
              <Route path="carrinho" element={<Cart />} />
              <Route path="checkout" element={guard(<Checkout />)} />
              <Route path="pedido/:id" element={guard(<OrderConfirmation />)} />
              <Route path="assinar/:code" element={guard(<SubscribePlan />)} />
              <Route path="assinar-racao/:slug/:skuId" element={guard(<SubscribeFood />)} />
              <Route path="assinatura/confirmada" element={guard(<SubscriptionConfirmation />)} />
              <Route path="pagamento-simulado/:id" element={<SimulatedPayment />} />
              <Route path="entrar" element={<Login />} />
              <Route path="cadastro" element={<Register />} />
              <Route path="ajuda" element={<Help />} />
              <Route path="privacidade" element={<Privacy />} />
              <Route path="termos" element={<Terms />} />
              <Route path="minha-vila" element={guard(<VilaLayout />)}>
                <Route index element={<Overview />} />
                <Route path="caes" element={<Dogs />} />
                <Route path="assinaturas" element={<Subscriptions />} />
                <Route path="entregas" element={<Deliveries />} />
                <Route path="pedidos" element={<Orders />} />
                <Route path="pagamentos" element={<Payments />} />
                <Route path="enderecos" element={<Addresses />} />
                <Route path="dados" element={<Profile />} />
                <Route path="atendimento" element={<Support />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </CartProvider>
    </AuthProvider>
  );
}
