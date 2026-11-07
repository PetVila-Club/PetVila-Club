import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text as RNText, TextInput, View, type TextProps, type TextInputProps, type ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { SvgXml } from 'react-native-svg';
import { DOG_SVG, LOGO_SVG } from './brandAssets';
import { colors, fonts, radius } from './theme';

export function Logo({ height = 32, color = colors.fucinho }: { height?: number; color?: string }) {
  return <SvgXml xml={LOGO_SVG} height={height} width={height * 3.92} color={color} accessibilityLabel="PetVila Club" />;
}

export function DogArt({ size = 96, color = colors.terra }: { size?: number; color?: string }) {
  return <SvgXml xml={DOG_SVG} height={size} width={size * 0.75} color={color} />;
}

export function Text({ style, variant = 'body', ...props }: TextProps & { variant?: 'body' | 'title' | 'h2' | 'small' | 'eyebrow' | 'price' }) {
  return <RNText {...props} style={[styles.text, styles[variant], style]} />;
}

export function Screen({ children, scroll = true }: { children: ReactNode; scroll?: boolean }) {
  return (
    <SafeAreaView style={styles.screen} edges={['top', 'left', 'right']}>
      {scroll ? <ScrollView contentContainerStyle={styles.content}>{children}</ScrollView> : <View style={styles.content}>{children}</View>}
    </SafeAreaView>
  );
}

export function Card({ children, dark, style }: { children: ReactNode; dark?: boolean; style?: ViewStyle }) {
  return <View style={[styles.card, dark && styles.cardDark, style]}>{children}</View>;
}

export function Button({ title, onPress, variant = 'primary', disabled, busy }: { title: string; onPress: () => void; variant?: 'primary' | 'brand' | 'ghost'; disabled?: boolean; busy?: boolean }) {
  const bg = variant === 'brand' ? colors.patinha : variant === 'ghost' ? 'transparent' : colors.fucinho;
  const fg = variant === 'primary' ? colors.chamego : colors.fucinho;
  return (
    <Pressable accessibilityRole="button" accessibilityState={{ disabled: disabled || busy }} disabled={disabled || busy} onPress={onPress}
      style={({ pressed }) => [styles.button, { backgroundColor: bg, opacity: disabled ? 0.45 : pressed ? 0.85 : 1 }]}>
      {busy ? <ActivityIndicator color={fg} /> : <RNText style={[styles.buttonText, { color: fg }]}>{title}</RNText>}
    </Pressable>
  );
}

export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={{ gap: 6 }}>
      <Text variant="small" style={{ fontFamily: fonts.bold }}>{label}</Text>
      <TextInput placeholderTextColor={colors.inkSoft} {...props} style={styles.input} accessibilityLabel={label} />
    </View>
  );
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'error' | 'ok' | 'warn'; children: ReactNode }) {
  const color = { info: colors.terra, error: colors.danger, ok: colors.ok, warn: colors.warn }[tone];
  return (
    <View style={[styles.notice, { borderColor: color }]} accessibilityRole={tone === 'error' ? 'alert' : undefined}>
      <Text variant="small" style={{ color }}>{children}</Text>
    </View>
  );
}

export function Badge({ label, status }: { label: string; status: string }) {
  const ok = ['active', 'paid', 'delivered', 'shipped', 'CONFIRMED', 'RECEIVED'].includes(status);
  const bad = ['canceled', 'past_due', 'payment_failed', 'OVERDUE'].includes(status);
  const color = ok ? colors.ok : bad ? colors.danger : colors.warn;
  return <Text variant="small" style={[styles.badge, { color, borderColor: color }]}>{label}</Text>;
}

export function Choice({ label, detail, selected, onPress, disabled }: { label: string; detail?: string; selected: boolean; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: selected, disabled }} onPress={onPress} disabled={disabled}
      style={[styles.choice, selected && styles.choiceOn, disabled && { opacity: 0.5 }]}>
      <Text style={{ fontFamily: fonts.bold }}>{label}</Text>
      {detail ? <Text variant="small" style={{ color: colors.inkSoft }}>{detail}</Text> : null}
    </Pressable>
  );
}

export const Loading = () => <ActivityIndicator color={colors.patinha} style={{ margin: 32 }} />;

export const Row = ({ children, style }: { children: ReactNode; style?: ViewStyle }) => (
  <View style={[{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 }, style]}>{children}</View>
);

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.chamego },
  content: { padding: 20, gap: 16, paddingBottom: 48 },
  text: { color: colors.fucinho, fontFamily: fonts.regular, fontSize: 16, lineHeight: 23 },
  body: {},
  title: { fontFamily: fonts.display, fontSize: 36, lineHeight: 36, letterSpacing: -1 },
  h2: { fontFamily: fonts.display, fontSize: 24, lineHeight: 26, letterSpacing: -0.5 },
  small: { fontSize: 14, lineHeight: 20 },
  eyebrow: { fontFamily: fonts.bold, fontSize: 12, letterSpacing: 1.8, textTransform: 'uppercase', color: colors.patinha },
  price: { fontFamily: fonts.display, fontSize: 22 },
  card: { backgroundColor: colors.card, borderRadius: radius.lg, padding: 18, gap: 10, borderWidth: 1, borderColor: colors.line },
  cardDark: { backgroundColor: colors.terra, borderColor: colors.terra },
  button: { minHeight: 50, borderRadius: radius.pill, paddingHorizontal: 22, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: colors.fucinho },
  buttonText: { fontFamily: fonts.bold, fontSize: 16 },
  input: { minHeight: 50, borderRadius: 14, borderWidth: 1.5, borderColor: colors.line, paddingHorizontal: 14, backgroundColor: '#FFF6EB', fontFamily: fonts.regular, fontSize: 16, color: colors.fucinho },
  notice: { borderWidth: 1.5, borderRadius: radius.md, padding: 12 },
  badge: { alignSelf: 'flex-start', borderWidth: 1.5, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 2, fontFamily: fonts.bold, fontSize: 12, textTransform: 'uppercase' },
  choice: { borderWidth: 1.5, borderColor: colors.line, borderRadius: radius.md, padding: 14, gap: 2, backgroundColor: colors.card },
  choiceOn: { borderColor: colors.terra, borderWidth: 2.5, backgroundColor: '#FFF6EB' },
});
