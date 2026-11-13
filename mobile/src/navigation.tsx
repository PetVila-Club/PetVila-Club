import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { DefaultTheme, NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useCart } from './state';
import { colors, fonts } from './theme';
import type { Delivery, Payment, Subscription } from './types';
import { DeliveryDetailScreen, PaymentScreen, SubscribeScreen, SubscriptionDetailScreen, VilaScreen } from './screens/Account';
import { CartScreen, HomeScreen, ProductScreen, StoreScreen } from './screens/Shop';

export type RootStack = {
  Tabs: undefined;
  Product: { slug: string };
  Subscribe: { code: string };
  Payment: { payment: Payment; title: string };
  SubscriptionDetail: { sub: Subscription };
  DeliveryDetail: { delivery: Delivery };
};

const Stack = createNativeStackNavigator<RootStack>();
const Tab = createBottomTabNavigator();

function Tabs() {
  const { items } = useCart();
  const count = items.reduce((n, i) => n + i.quantity, 0);
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.patinha,
        tabBarInactiveTintColor: colors.fucinho,
        tabBarStyle: { backgroundColor: colors.chamego, borderTopColor: colors.line },
        tabBarLabelStyle: { fontFamily: fonts.bold, fontSize: 12 },
        tabBarIcon: () => null,
        tabBarIconStyle: { display: 'none' },
      }}
    >
      <Tab.Screen name="Início" component={HomeScreen} />
      <Tab.Screen name="Loja" component={StoreScreen} />
      <Tab.Screen name="Carrinho" component={CartScreen} options={{ tabBarBadge: count || undefined }} />
      <Tab.Screen name="Minha Vila" component={VilaScreen} />
    </Tab.Navigator>
  );
}

const theme = { ...DefaultTheme, colors: { ...DefaultTheme.colors, background: colors.chamego, card: colors.chamego, text: colors.fucinho, primary: colors.patinha } };

export function AppNavigation() {
  return (
    <NavigationContainer theme={theme}>
      <Stack.Navigator screenOptions={{ headerTitleStyle: { fontFamily: fonts.bold }, headerTintColor: colors.fucinho, headerBackTitle: 'Voltar' }}>
        <Stack.Screen name="Tabs" component={Tabs} options={{ headerShown: false }} />
        <Stack.Screen name="Product" component={ProductScreen} options={{ title: 'Produto' }} />
        <Stack.Screen name="Subscribe" component={SubscribeScreen} options={{ title: 'Assinar' }} />
        <Stack.Screen name="Payment" component={PaymentScreen} options={{ title: 'Pagamento' }} />
        <Stack.Screen name="SubscriptionDetail" component={SubscriptionDetailScreen} options={{ title: 'Assinatura' }} />
        <Stack.Screen name="DeliveryDetail" component={DeliveryDetailScreen} options={{ title: 'Entrega' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
