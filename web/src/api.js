// Ponte para o Python.
// Janela nativa: window.pywebview.api (js_api do pywebview).
// Browser: POST /api/<metodo> com o token de sessão do fragmento do URL (#t=...).

const parametros = new URLSearchParams(window.location.hash.slice(1));
const token = parametros.get('t');

export const modo = token ? 'browser' : 'janela';

function esperarPywebview(limiteMs) {
  return new Promise((resolver, rejeitar) => {
    const pronta = () => window.pywebview && window.pywebview.api && typeof window.pywebview.api.inicio === 'function';
    if (pronta()) return resolver();
    const fim = setTimeout(() => rejeitar(new Error('A ponte da janela não respondeu.')), limiteMs);
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

const ponte = token ? Promise.resolve() : esperarPywebview(15000);

async function viaHttp(metodo, args) {
  const resposta = await fetch(`/api/${metodo}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Memoria-Token': token },
    body: JSON.stringify({ args }),
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || `Erro ${resposta.status}`);
  return dados.resultado;
}

export async function chamar(metodo, ...args) {
  if (token) return viaHttp(metodo, args);
  await ponte;
  try {
    return await window.pywebview.api[metodo](...args);
  } catch (erro) {
    throw new Error((erro && erro.message) || String(erro));
  }
}

// No browser, o servidor termina se a página deixar de dar sinal.
export function manterVivo() {
  if (!token) return;
  chamar('batimento').catch(() => {});
  setInterval(() => chamar('batimento').catch(() => {}), 15000);
}
