import logoRaw from '../assets/brand/logo-petvila.svg?raw';
import caoRaw from '../assets/brand/cao-petvila.svg?raw';
import caixaRaw from '../assets/brand/caixa-petvila.svg?raw';

function clean(svg: string, label?: string) {
  const base = svg.replace(/\s(role|aria-label)="[^"]*"/g, '');
  return label
    ? base.replace('<svg ', `<svg role="img" aria-label="${label}" focusable="false" `)
    : base.replace('<svg ', '<svg aria-hidden="true" focusable="false" ');
}

const LOGO = clean(logoRaw, 'PetVila Club');
const CAO = clean(caoRaw);
const CAIXA = clean(caixaRaw);

/** Logo oficial (petvila + club.), herda a cor do texto. Nunca redesenhar aqui. */
export function Logo({ height = '2.25rem', tone = 'dark' }: { height?: string; tone?: 'dark' | 'light' | 'brand' }) {
  const color = tone === 'light' ? 'var(--chamego)' : tone === 'brand' ? 'var(--patinha)' : 'var(--fucinho)';
  return <span className="logo" style={{ display: 'inline-flex', height, color, lineHeight: 0 }} dangerouslySetInnerHTML={{ __html: LOGO }} />;
}

export function DogArt({ className = '' }: { className?: string }) {
  return <span className={`art ${className}`} dangerouslySetInnerHTML={{ __html: CAO }} />;
}

export function BoxArt({ className = '' }: { className?: string }) {
  return <span className={`art ${className}`} dangerouslySetInnerHTML={{ __html: CAIXA }} />;
}
