import { t } from './i18n.jsx';

// Ponte para o Python.
// O servidor diz o modo em <meta name="memoria-modo">:
// - "janela": usa window.pywebview.api (js_api do pywebview); se a ponte não
//   aparecer, usa HTTP (o cookie de sessão já foi posto pelo servidor);
// - "browser" (ou sem meta): POST /api/<metodo>, autenticado pelo cookie de sessão.

const meta = document.querySelector('meta[name="memoria-modo"]');
const modoServidor = meta ? meta.getAttribute('content') : 'browser';
// Compatibilidade com URLs antigos (#t=<chave>).
const tokenFragmento = new URLSearchParams(window.location.hash.slice(1)).get('t');

function pywebviewPronto() {
  return Boolean(window.pywebview && window.pywebview.api && typeof window.pywebview.api.inicio === 'function');
}

function esperarPywebview(limiteMs) {
  return new Promise((resolver, rejeitar) => {
    if (pywebviewPronto()) return resolver();
    const fim = setTimeout(() => rejeitar(new Error('sem ponte')), limiteMs);
    window.addEventListener(
      'pywebviewready',
      () => {
        clearTimeout(fim);
        resolver();
      },
      { once: true },
    );
  });
}

async function escolherPonte() {
  if (modoServidor !== 'janela') return 'http';
  try {
    await esperarPywebview(4000);
    return 'pywebview';
  } catch {
    return 'http';
  }
}

const ponte = escolherPonte();

export async function ponteEmUso() {
  return ponte;
}

async function viaHttp(metodo, args) {
  const cabecalhos = { 'Content-Type': 'application/json' };
  if (tokenFragmento) cabecalhos['X-Memoria-Token'] = tokenFragmento;
  const resposta = await fetch(`/api/${metodo}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: cabecalhos,
    body: JSON.stringify({ args }),
  });
  const dados = await resposta.json().catch(() => ({}));
  if (resposta.status === 403) throw new Error(t('sessao.invalida'));
  if (!resposta.ok) throw new Error(dados.erro || `Erro ${resposta.status}`);
  return dados.resultado;
}

export async function chamar(metodo, ...args) {
  if ((await ponte) === 'http') return viaHttp(metodo, args);
  try {
    return await window.pywebview.api[metodo](...args);
  } catch (erro) {
    throw new Error((erro && erro.message) || String(erro));
  }
}

// No browser, o servidor termina se a página deixar de dar sinal.
export async function manterVivo() {
  if ((await ponte) !== 'http') return;
  chamar('batimento').catch(() => {});
  setInterval(() => chamar('batimento').catch(() => {}), 15000);
}
