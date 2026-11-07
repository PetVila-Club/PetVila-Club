import {
  BricolageGrotesque_400Regular,
  BricolageGrotesque_500Medium,
  BricolageGrotesque_700Bold,
  BricolageGrotesque_800ExtraBold,
  useFonts,
} from '@expo-google-fonts/bricolage-grotesque';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AppNavigation } from './src/navigation';
import { AuthProvider, CartProvider, useAuth } from './src/state';
import { colors } from './src/theme';

function Root() {
  const { ready } = useAuth();
  if (!ready) {
    return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.chamego }}><ActivityIndicator color={colors.patinha} /></View>;
  }
  return <AppNavigation />;
}

export default function App() {
  const [fontsLoaded] = useFonts({ BricolageGrotesque_400Regular, BricolageGrotesque_500Medium, BricolageGrotesque_700Bold, BricolageGrotesque_800ExtraBold });
  if (!fontsLoaded) return <View style={{ flex: 1, backgroundColor: colors.chamego }} />;
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <CartProvider>
          <StatusBar style="dark" />
          <Root />
        </CartProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
