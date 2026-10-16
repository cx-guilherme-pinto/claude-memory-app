// Línguas da interface: português, inglês, hindi e hebraico (RTL).
// O servidor diz a língua em <meta name="memoria-lingua"> e já põe lang/dir no <html>;
// o seletor muda-a na hora e o Python guarda a escolha.
import { Fragment } from 'react';
import en from './locales/en.json';
import he from './locales/he.json';
import hi from './locales/hi.json';
import pt from './locales/pt.json';

const CATALOGOS = { pt, en, hi, he };
export const LINGUAS = [
  { codigo: 'pt', nome: 'Português', direcao: 'ltr' },
  { codigo: 'en', nome: 'English', direcao: 'ltr' },
  { codigo: 'hi', nome: 'हिन्दी', direcao: 'ltr' },
  { codigo: 'he', nome: 'עברית', direcao: 'rtl' },
];
const RESERVA = 'en';

export function normalizar(codigo) {
  const base = String(codigo || '')
    .toLowerCase()
    .split(/[-_.@]/)[0];
  const lingua = base === 'iw' ? 'he' : base;
  return lingua in CATALOGOS ? lingua : null;
}

function inicial() {
  const meta = document.querySelector('meta[name="memoria-lingua"]')?.getAttribute('content');
  return normalizar(meta) || (navigator.languages || [navigator.language]).map(normalizar).find(Boolean) || RESERVA;
}

let atual = inicial();

export function lingua() {
  return atual;
}

export function direcao(codigo = atual) {
  return codigo === 'he' ? 'rtl' : 'ltr';
}

export function aplicarLingua(codigo) {
  atual = normalizar(codigo) || RESERVA;
  const raiz = document.documentElement;
  raiz.lang = atual;
  raiz.dir = direcao(atual);
  return atual;
}

function modelo(chave, n) {
  const valor = CATALOGOS[atual][chave] ?? CATALOGOS[RESERVA][chave] ?? CATALOGOS.pt[chave] ?? chave;
  if (valor && typeof valor === 'object') {
    const forma = new Intl.PluralRules(atual).select(Number(n) || 0);
    return valor[forma] ?? valor.other;
  }
  return valor;
}

// t('chave', { n: 3, nome: 'x' }) → texto com os marcadores trocados.
export function t(chave, valores = {}) {
  return modelo(chave, valores.n).replace(/\{(\w+)\}/g, (inteiro, nome) => (nome in valores ? String(valores[nome]) : inteiro));
}

// Como t(), mas os marcadores em `elementos` viram elementos React (ex.: <code>).
// A ordem das palavras muda de língua para língua; o elemento vai para onde a frase o põe.
export function tx(chave, valores = {}, elementos = {}) {
  const partes = modelo(chave, valores.n).split(/(\{\w+\})/);
  return partes.map((parte, i) => {
    const m = /^\{(\w+)\}$/.exec(parte);
    if (m && m[1] in elementos) return <Fragment key={i}>{elementos[m[1]]}</Fragment>;
    if (m && m[1] in valores) return String(valores[m[1]]);
    return parte;
  });
}

// Português à mão (o Intl de cada motor abrevia de maneira diferente: "21/06", "21 jun.").
const MESES_PT = ['jan.', 'fev.', 'mar.', 'abr.', 'maio', 'jun.', 'jul.', 'ago.', 'set.', 'out.', 'nov.', 'dez.'];

// "21 jun." neste ano, "21 jun. 2025" nos outros. Usa a data escrita na nota, sem fuso.
export function dataLonga(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
  if (!m) return '';
  const [ano, mes, dia] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const desteAno = ano === new Date().getFullYear();
  if (atual === 'pt') {
    const texto = `${dia} ${MESES_PT[mes - 1]}`;
    return desteAno ? texto : `${texto} ${ano}`;
  }
  const opcoes = { day: 'numeric', month: 'short', timeZone: 'UTC', ...(desteAno ? {} : { year: 'numeric' }) };
  return new Intl.DateTimeFormat(atual, opcoes).format(new Date(Date.UTC(ano, mes - 1, dia)));
}

export function dolares(valor) {
  return new Intl.NumberFormat(atual, { style: 'currency', currency: 'USD' }).format(Number(valor) || 0);
}
