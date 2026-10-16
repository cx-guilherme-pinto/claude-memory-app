// Tipos de nó, rótulos e formas. As cores vêm dos tokens CSS --tipo-*.

export const TIPOS_MEMORIA = ['licao', 'fazer', 'nao_fazer', 'historico'];
export const TIPOS_CONTEXTO = ['projeto', 'tarefa', 'ficheiro'];
export const TODOS_TIPOS = [...TIPOS_MEMORIA, ...TIPOS_CONTEXTO];

export const ROTULOS = {
  licao: 'Lição',
  fazer: 'Fazer',
  nao_fazer: 'Não fazer',
  historico: 'Histórico',
  projeto: 'Projeto',
  tarefa: 'Tarefa',
  ficheiro: 'Ficheiro',
};

// Forma: identidade nunca só pela cor.
export const FORMAS = {
  licao: 'circulo',
  fazer: 'circulo',
  nao_fazer: 'circulo',
  historico: 'circulo',
  projeto: 'quadrado',
  tarefa: 'losango',
  ficheiro: 'triangulo',
};

export const MOTIVOS = {
  ligacao: 'ligação',
  tarefa: 'mesma tarefa',
  projeto: 'mesmo projeto',
  ficheiro: 'ficheiro partilhado',
};

export function lerCores() {
  const estilo = getComputedStyle(document.documentElement);
  const cores = {};
  for (const tipo of TODOS_TIPOS) cores[tipo] = estilo.getPropertyValue(`--tipo-${tipo}`).trim();
  for (const papel of ['bg', 'surface', 'ink', 'muted', 'accent']) cores[papel] = estilo.getPropertyValue(`--${papel}`).trim();
  return cores;
}

export function desenharForma(ctx, forma, x, y, r) {
  ctx.beginPath();
  if (forma === 'quadrado') {
    ctx.rect(x - r, y - r, r * 2, r * 2);
  } else if (forma === 'losango') {
    ctx.moveTo(x, y - r * 1.25);
    ctx.lineTo(x + r * 1.25, y);
    ctx.lineTo(x, y + r * 1.25);
    ctx.lineTo(x - r * 1.25, y);
    ctx.closePath();
  } else if (forma === 'triangulo') {
    ctx.moveTo(x, y - r * 1.2);
    ctx.lineTo(x + r * 1.1, y + r * 0.8);
    ctx.lineTo(x - r * 1.1, y + r * 0.8);
    ctx.closePath();
  } else {
    ctx.arc(x, y, r, 0, Math.PI * 2);
  }
}

export function Marca({ tipo, tamanho = 12 }) {
  const r = tamanho / 2 - 1.5;
  const c = tamanho / 2;
  const forma = FORMAS[tipo] || 'circulo';
  const cor = `var(--tipo-${tipo}, var(--muted))`;
  let desenho;
  if (forma === 'quadrado') desenho = <rect x={c - r} y={c - r} width={r * 2} height={r * 2} fill={cor} />;
  else if (forma === 'losango')
    desenho = <polygon points={`${c},${c - r * 1.2} ${c + r * 1.2},${c} ${c},${c + r * 1.2} ${c - r * 1.2},${c}`} fill={cor} />;
  else if (forma === 'triangulo')
    desenho = <polygon points={`${c},${c - r * 1.15} ${c + r * 1.1},${c + r * 0.85} ${c - r * 1.1},${c + r * 0.85}`} fill={cor} />;
  else desenho = <circle cx={c} cy={c} r={r} fill={cor} />;
  return (
    <svg width={tamanho} height={tamanho} viewBox={`0 0 ${tamanho} ${tamanho}`} aria-hidden="true">
      {desenho}
    </svg>
  );
}

export function dataCurta(iso) {
  if (!iso) return '';
  return iso.slice(0, 10);
}
