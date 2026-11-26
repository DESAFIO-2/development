import { Text, type TextProps } from 'react-native';

type Variant =
  | 'label-sm'
  | 'label-md'
  | 'label-lg'
  | 'body-sm'
  | 'body-md'
  | 'body-lg'
  | 'title-md'
  | 'title-lg'
  | 'headline-sm'
  | 'headline-md'
  | 'headline-lg-mobile'
  | 'display-lg-mobile';

type Weight = 'regular' | 'medium' | 'semibold' | 'bold';

// Strings literais para o Tailwind/NativeWind conseguir gerar as classes.
const SIZE: Record<Variant, string> = {
  'label-sm': 'text-label-sm',
  'label-md': 'text-label-md',
  'label-lg': 'text-label-lg',
  'body-sm': 'text-body-sm',
  'body-md': 'text-body-md',
  'body-lg': 'text-body-lg',
  'title-md': 'text-title-md',
  'title-lg': 'text-title-lg',
  'headline-sm': 'text-headline-sm',
  'headline-md': 'text-headline-md',
  'headline-lg-mobile': 'text-headline-lg-mobile',
  'display-lg-mobile': 'text-display-lg-mobile',
};

const SANS: Record<Weight, string> = {
  regular: 'font-sans',
  medium: 'font-sans-medium',
  semibold: 'font-sans-semibold',
  bold: 'font-sans-bold',
};

const SERIF: Record<Weight, string> = {
  regular: 'font-serif',
  medium: 'font-serif-medium',
  semibold: 'font-serif-semibold',
  bold: 'font-serif-semibold',
};

// Pesos padrão de cada variante, como no design system dos HTMLs.
const DEFAULT_WEIGHT: Record<Variant, Weight> = {
  'label-sm': 'bold',
  'label-md': 'semibold',
  'label-lg': 'semibold',
  'body-sm': 'regular',
  'body-md': 'regular',
  'body-lg': 'regular',
  'title-md': 'semibold',
  'title-lg': 'semibold',
  'headline-sm': 'semibold',
  'headline-md': 'medium',
  'headline-lg-mobile': 'medium',
  'display-lg-mobile': 'regular',
};

export type TxtProps = TextProps & {
  v?: Variant;
  w?: Weight;
  /** Força Newsreader (serifada). Por padrão, headline/display já usam. */
  serif?: boolean;
  upper?: boolean;
  className?: string;
};

// Classes `text-*` que não são cor (tamanho da escala e alinhamento).
const TEXT_NAO_COR = new Set([
  ...Object.values(SIZE),
  ...['xs', 'sm', 'base', 'lg', 'xl', '2xl', '3xl', '4xl', '5xl', '6xl', '7xl', '8xl', '9xl'].map((s) => `text-${s}`),
  ...['left', 'center', 'right', 'justify', 'start', 'end'].map((a) => `text-${a}`),
]);

/** Indica se o className já define uma cor de texto (ex.: `text-primary`, `text-white/70`). */
export function temCorDeTexto(className: string): boolean {
  return className.split(/\s+/).some((c) => {
    const base = c.slice(c.lastIndexOf(':') + 1).replace(/^!/, '');
    return base.startsWith('text-') && !TEXT_NAO_COR.has(base);
  });
}

export function Txt({ v = 'body-md', w, serif, upper, className = '', children, ...rest }: TxtProps) {
  const isSerif = serif ?? (v.startsWith('headline') || v.startsWith('display'));
  const weight = w ?? DEFAULT_WEIGHT[v];
  const family = isSerif ? SERIF[weight] : SANS[weight];
  // A cor padrão só entra quando o texto não traz a sua: com as duas classes,
  // a ordem do CSS gerado decide qual vence e a cor pedida podia sumir.
  const corPadrao = temCorDeTexto(className) ? '' : 'text-on-surface';
  return (
    <Text
      {...rest}
      className={`${SIZE[v]} ${family} ${upper ? 'uppercase' : ''} ${corPadrao} ${className}`}>
      {children}
    </Text>
  );
}
