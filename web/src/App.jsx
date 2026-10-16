import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { chamar, manterVivo } from './api.js';
import NovaMemoria from './NovaMemoria.jsx';
import Procura from './Procura.jsx';
import { FORMAS, Marca, ROTULOS, TIPOS_MEMORIA, TODOS_TIPOS, dataCurta, desenharForma, lerCores } from './tipos.jsx';

// O painel traz o marked e o DOMPurify: só carrega quando é preciso.
const Painel = lazy(() => import('./Painel.jsx'));

const PERIODOS = [
  ['tudo', 'Todo o período'],
  ['7', 'Últimos 7 dias'],
  ['30', 'Últimos 30 dias'],
  ['90', 'Últimos 90 dias'],
  ['365', 'Último ano'],
];
const DISTANCIA = { ligacao: 28, tarefa: 36, epico: 60, subtarefa: 40, projeto: 70, ficheiro: 46 };
const FORCA = { ligacao: 0.9, tarefa: 0.6, epico: 0.2, subtarefa: 0.5, projeto: 0.15, ficheiro: 0.25 };
const LARGURA = { ligacao: 1.6, tarefa: 0.9, epico: 0.6, subtarefa: 1.2, projeto: 0.5, ficheiro: 0.5 };
const DURACAO_REPRODUCAO = 6000;
const semMovimento = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function comAlfa(cor, alfa) {
  const m = /^#([0-9a-f]{6})$/i.exec(cor || '');
  if (!m) return cor;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
}

function raio(no) {
  const g = Math.sqrt(no.grau || 0);
  if (no.tipo === 'projeto') return Math.min(16, 6 + g * 0.8);
  if (no.tipo === 'epico') return Math.min(13, 5 + g * 0.8);
  if (no.tipo === 'tarefa') return Math.min(10, 4 + g * 0.9);
  if (no.tipo === 'ficheiro') return Math.min(8, 3 + g * 0.8);
  return Math.min(12, 3.5 + g * 1.4);
}

const idDe = (ponta) => (typeof ponta === 'object' ? ponta.id : ponta);

function cortar(texto, n) {
  return texto.length > n ? `${texto.slice(0, n - 1)}…` : texto;
}

export default function App() {
  const grafoRef = useRef(null);
  const procuraRef = useRef(null);
  const prontoEnviado = useRef(false);
  const ajustado = useRef(false);
  const tempos = useRef({});

  const [info, setInfo] = useState(null);
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState('');
  const [cores, setCores] = useState(lerCores);
  const [tamanho, setTamanho] = useState({ w: window.innerWidth, h: window.innerHeight });

  const [projeto, setProjeto] = useState('');
  const [epico, setEpico] = useState('');
  const [tarefa, setTarefa] = useState('');
  const [tiposAtivos, setTiposAtivos] = useState(() => new Set(TODOS_TIPOS));
  const [periodo, setPeriodo] = useState('tudo');
  const [cursor, setCursor] = useState(Infinity);
  const [aReproduzir, setAReproduzir] = useState(false);

  const [texto, setTexto] = useState('');
  const [resultados, setResultados] = useState(null);
  const [grupos, setGrupos] = useState(null);
  const [selecionado, setSelecionado] = useState(null);
  const [sobre, setSobre] = useState(null);
  const [novaAberta, setNovaAberta] = useState(false);
  const [mensagem, setMensagem] = useState('');
  const [aviso, setAviso] = useState(null);

  // ------------------------------------------------------------ carregar
  const carregar = useCallback(async () => {
    const g = await chamar('grafo');
    setDados((anterior) => {
      // Mantém os objetos (e as posições) dos nós que já existiam.
      const antigos = new Map((anterior?.nos || []).map((n) => [n.id, n]));
      const nos = g.nos.map((n) => Object.assign(antigos.get(n.id) || {}, n));
      const ligacoes = g.ligacoes.map((l) => ({ ...l }));
      return { ...g, nos, ligacoes };
    });
    return g;
  }, []);

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const i = await chamar('inicio');
        if (!vivo) return;
        tempos.current.ponte = Math.round(performance.now());
        setInfo(i);
        await carregar();
        tempos.current.grafo = Math.round(performance.now());
        manterVivo();
      } catch (e) {
        setErro(e.message);
        chamar('pronto', { erro: e.message }).catch(() => {});
      }
    })();
    return () => {
      vivo = false;
    };
  }, [carregar]);

  // Aviso de versão nova: em segundo plano, nunca bloqueia.
  useEffect(() => {
    if (!info || info.selftest) return undefined;
    const t = setTimeout(() => {
      chamar('verificar_atualizacao')
        .then((r) => r && r.disponivel && setAviso(r))
        .catch(() => {});
    }, 1500);
    return () => clearTimeout(t);
  }, [info]);

  useEffect(() => {
    const redimensionar = () => setTamanho({ w: window.innerWidth, h: window.innerHeight });
    const tema = window.matchMedia('(prefers-color-scheme: dark)');
    const mudarTema = () => setCores(lerCores());
    window.addEventListener('resize', redimensionar);
    tema.addEventListener('change', mudarTema);
    return () => {
      window.removeEventListener('resize', redimensionar);
      tema.removeEventListener('change', mudarTema);
    };
  }, []);

  // ----------------------------------------------------------- derivados
  const memoriasOrdenadas = useMemo(() => {
    if (!dados) return [];
    return dados.nos.filter((n) => TIPOS_MEMORIA.includes(n.tipo) || !(n.tipo in ROTULOS)).sort((a, b) => (a.data < b.data ? -1 : 1));
  }, [dados]);

  const maxCursor = Math.max(0, memoriasOrdenadas.length - 1);
  const cursorEfetivo = Math.min(cursor, maxCursor);

  const visivel = useMemo(() => {
    if (!dados) return { nodes: [], links: [], memorias: 0 };
    let desde = '';
    if (periodo !== 'tudo') {
      const d = new Date(Date.now() - Number(periodo) * 86400000);
      desde = d.toISOString().slice(0, 10);
    }
    const ate = memoriasOrdenadas[cursorEfetivo]?.data ?? '';
    const ids = new Set();
    for (const n of memoriasOrdenadas) {
      if (n.data > ate) break;
      if (!tiposAtivos.has(n.tipo) && n.tipo in ROTULOS) continue;
      if (projeto && n.projeto !== projeto) continue;
      if (epico && n.epico !== epico && n.tarefa !== epico) continue;
      if (tarefa && n.tarefa !== tarefa) continue;
      if (desde && n.data.slice(0, 10) < desde) continue;
      ids.add(n.id);
    }
    const memorias = ids.size;
    const contexto = new Map(dados.nos.filter((n) => !ids.has(n.id) && !TIPOS_MEMORIA.includes(n.tipo)).map((n) => [n.id, n]));
    const links = [];
    for (const l of dados.ligacoes) {
      const a = idDe(l.source);
      const b = idDe(l.target);
      if (!ids.has(a)) continue;
      if (ids.has(b)) {
        links.push(l);
        continue;
      }
      const c = contexto.get(b);
      if (c && tiposAtivos.has(c.tipo)) {
        ids.add(b);
        links.push(l);
      }
    }
    // Tarefa → épico: só quando os dois nós já estão visíveis.
    for (const l of dados.ligacoes) {
      if (l.tipo === 'subtarefa' && ids.has(idDe(l.source)) && ids.has(idDe(l.target))) links.push(l);
    }
    const nodes = dados.nos.filter((n) => ids.has(n.id));
    return { nodes, links, memorias };
  }, [dados, memoriasOrdenadas, cursorEfetivo, tiposAtivos, projeto, epico, tarefa, periodo]);

  // Tarefas da lista: só as do épico escolhido.
  const tarefasDoFiltro = useMemo(() => {
    const todas = dados?.tarefas || [];
    return epico ? todas.filter((t) => t.epico === epico || t.chave === epico) : todas;
  }, [dados, epico]);

  const contagemPorTipo = useMemo(() => {
    const c = {};
    for (const n of visivel.nodes) c[n.tipo] = (c[n.tipo] || 0) + 1;
    return c;
  }, [visivel]);

  const grafoDados = useMemo(() => ({ nodes: visivel.nodes, links: visivel.links }), [visivel]);

  // ------------------------------------------------------------- forças
  useEffect(() => {
    const fg = grafoRef.current;
    if (!fg || !dados) return;
    fg.d3Force('link')
      ?.distance((l) => DISTANCIA[l.tipo] ?? 50)
      .strength((l) => FORCA[l.tipo] ?? 0.3);
    fg.d3Force('charge')?.strength(-55).distanceMax(360);
  }, [dados]);

  // ----------------------------------------------------- linha temporal
  useEffect(() => {
    if (!aReproduzir) return undefined;
    const total = memoriasOrdenadas.length;
    if (total < 2) {
      setAReproduzir(false);
      return undefined;
    }
    const inicio = performance.now();
    let pedido;
    const passo = (agora) => {
      const i = Math.min(total - 1, Math.floor(((agora - inicio) / DURACAO_REPRODUCAO) * total));
      setCursor(i);
      if (i >= total - 1) {
        setAReproduzir(false);
        setCursor(Infinity);
        return;
      }
      pedido = requestAnimationFrame(passo);
    };
    pedido = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(pedido);
  }, [aReproduzir, memoriasOrdenadas]);

  // ------------------------------------------------------------- procura
  useEffect(() => {
    const t = texto.trim();
    if (!t) {
      setResultados(null);
      setGrupos(null);
      return undefined;
    }
    let vivo = true;
    const espera = setTimeout(() => {
      chamar('procurar', t)
        .then((g) => {
          if (!vivo) return;
          setGrupos(g);
          // Destaca as memórias encontradas, os projetos/tickets e as memórias deles.
          setResultados(new Set([...g.ids, ...g.nos]));
        })
        .catch((e) => vivo && setMensagem(e.message));
    }, 160);
    return () => {
      vivo = false;
      clearTimeout(espera);
    };
  }, [texto, dados]);

  const correspondencias = useMemo(() => {
    if (!resultados) return [];
    return visivel.nodes.filter((n) => resultados.has(n.id));
  }, [resultados, visivel]);

  useEffect(() => {
    if (!mensagem) return undefined;
    const t = setTimeout(() => setMensagem(''), 5000);
    return () => clearTimeout(t);
  }, [mensagem]);

  // ------------------------------------------------------------- teclado
  useEffect(() => {
    const tecla = (e) => {
      const emCampo = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
      if (e.key === '/' && !emCampo && !novaAberta) {
        e.preventDefault();
        procuraRef.current?.focus();
      } else if (e.key === 'Escape' && !novaAberta) {
        if (emCampo && texto) setTexto('');
        else setSelecionado(null);
      }
    };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [novaAberta, texto]);

  // -------------------------------------------------------------- ações
  const focar = useCallback((no) => {
    if (!no) return;
    setSelecionado(no.id);
    const centrar = (tentativas) => {
      const fg = grafoRef.current;
      if (fg && Number.isFinite(no.x)) fg.centerAt(no.x, no.y, semMovimento() ? 0 : 400);
      else if (tentativas > 0) setTimeout(() => centrar(tentativas - 1), 250);
    };
    centrar(4);
  }, []);

  const abrirRef = useCallback(
    (id) => {
      const no = dados?.nos.find((n) => n.id === id);
      if (!no) {
        setSelecionado(id);
        return;
      }
      // Se o nó está escondido pelos filtros, limpa-os para o mostrar.
      if (!visivel.nodes.includes(no)) {
        setProjeto('');
        setEpico('');
        setTarefa('');
        setPeriodo('tudo');
        setTiposAtivos(new Set(TODOS_TIPOS));
        setCursor(Infinity);
        setAReproduzir(false);
      }
      focar(no);
    },
    [dados, focar, visivel],
  );

  const guardada = useCallback(
    async (r) => {
      setNovaAberta(false);
      setMensagem(r.redigidos ? `Memória guardada. ${r.redigidos} segredo(s) redigido(s).` : 'Memória guardada.');
      setCursor(Infinity);
      await carregar();
      setSelecionado(r.id);
    },
    [carregar],
  );

  const alternarTipo = (tipo) => {
    setTiposAtivos((atual) => {
      const novo = new Set(atual);
      if (novo.has(tipo)) novo.delete(tipo);
      else novo.add(tipo);
      return novo;
    });
  };

  // ------------------------------------------------------------ desenho
  const desenharNo = useCallback(
    (no, ctx, escala) => {
      const r = raio(no);
      const forma = FORMAS[no.tipo] || 'circulo';
      const corresponde = resultados ? resultados.has(no.id) : false;
      const apagado = resultados && !corresponde;
      const ativo = no.id === selecionado;
      ctx.globalAlpha = apagado ? 0.14 : 1;
      desenharForma(ctx, forma, no.x, no.y, r);
      ctx.fillStyle = cores[no.tipo] || cores.muted;
      ctx.fill();
      ctx.lineWidth = 1.5 / escala;
      ctx.strokeStyle = cores.bg;
      ctx.stroke();
      if (ativo || corresponde) {
        desenharForma(ctx, forma, no.x, no.y, r + 3 / escala);
        ctx.lineWidth = 2 / escala;
        ctx.strokeStyle = ativo ? cores.accent : cores.ink;
        ctx.stroke();
      }
      const mostrar = ativo || corresponde || no.id === sobre || no.tipo === 'projeto' || escala > 2.4;
      if (mostrar && !apagado) {
        const tamanhoLetra = Math.max(11 / escala, 1.5);
        ctx.font = `${no.tipo === 'projeto' ? 600 : 400} ${tamanhoLetra}px ${getComputedStyle(document.body).fontFamily}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const rotulo = cortar(no.rotulo || no.id, 42);
        const y = no.y + r + 3 / escala;
        ctx.lineJoin = 'round';
        ctx.lineWidth = 3 / escala;
        ctx.strokeStyle = cores.bg;
        ctx.strokeText(rotulo, no.x, y);
        ctx.fillStyle = cores.ink;
        ctx.fillText(rotulo, no.x, y);
      }
      ctx.globalAlpha = 1;
    },
    [cores, resultados, selecionado, sobre],
  );

  const areaNo = useCallback((no, cor, ctx) => {
    desenharForma(ctx, FORMAS[no.tipo] || 'circulo', no.x, no.y, raio(no) + 3);
    ctx.fillStyle = cor;
    ctx.fill();
  }, []);

  const corLigacao = useCallback(
    (l) => {
      const base = l.tipo === 'ligacao' ? 0.75 : 0.32;
      return comAlfa(cores.muted, resultados ? base * 0.35 : base);
    },
    [cores, resultados],
  );

  const quandoDesenhado = useCallback(() => {
    if (prontoEnviado.current || !dados) return;
    prontoEnviado.current = true;
    chamar('pronto', { ...tempos.current, ms: Math.round(performance.now()), nos: grafoDados.nodes.length }).catch(() => {});
  }, [dados, grafoDados]);

  // Sem memórias o grafo não desenha nada: avisa o selftest na mesma.
  useEffect(() => {
    if (dados && dados.nos.length === 0 && !prontoEnviado.current) {
      prontoEnviado.current = true;
      requestAnimationFrame(() => chamar('pronto', { ms: Math.round(performance.now()), nos: 0 }).catch(() => {}));
    }
  }, [dados]);

  const noSelecionado = selecionado ? dados?.nos.find((n) => n.id === selecionado) : null;
  const vizinhos = useMemo(() => {
    if (!noSelecionado || !dados) return [];
    const ids = new Set();
    for (const l of dados.ligacoes) {
      const a = idDe(l.source);
      const b = idDe(l.target);
      if (a === noSelecionado.id) ids.add(b);
      if (b === noSelecionado.id) ids.add(a);
    }
    return dados.nos.filter((n) => ids.has(n.id) && TIPOS_MEMORIA.includes(n.tipo)).sort((a, b) => (a.data < b.data ? 1 : -1));
  }, [noSelecionado, dados]);

  const larguraGrafo = selecionado && tamanho.w > 760 ? tamanho.w - Math.min(400, tamanho.w) : tamanho.w;
  const dataCursor = memoriasOrdenadas[cursorEfetivo]?.data;

  return (
    <div className="app">
      <div className="tela">
        {dados && (
          <ForceGraph2D
            ref={grafoRef}
            graphData={grafoDados}
            width={larguraGrafo}
            height={tamanho.h}
            backgroundColor={cores.bg}
            nodeLabel={() => ''}
            nodeCanvasObject={desenharNo}
            nodePointerAreaPaint={areaNo}
            linkColor={corLigacao}
            linkWidth={(l) => LARGURA[l.tipo] ?? 0.5}
            cooldownTime={8000}
            d3VelocityDecay={0.35}
            onNodeClick={focar}
            onNodeHover={(n) => setSobre(n ? n.id : null)}
            onBackgroundClick={() => setSelecionado(null)}
            onRenderFramePost={quandoDesenhado}
            onEngineStop={() => {
              if (!ajustado.current && grafoDados.nodes.length) {
                ajustado.current = true;
                grafoRef.current?.zoomToFit(semMovimento() ? 0 : 400, 60);
              }
            }}
          />
        )}
      </div>

      {dados && dados.total === 0 && (
        <div className="vazio">
          <div>
            <p>Ainda não há memórias.</p>
            <p className="pequeno">Usa “Nova memória” ou deixa o Claude Code guardar lições.</p>
          </div>
        </div>
      )}
      {erro && (
        <div className="vazio">
          <div>
            <p>Não foi possível carregar as memórias.</p>
            <p className="pequeno">{erro}</p>
          </div>
        </div>
      )}

      <div className="barra" style={{ right: selecionado && tamanho.w > 760 ? 412 : 12 }}>
        <Procura entradaRef={procuraRef} texto={texto} onTexto={setTexto} grupos={grupos} onEscolher={abrirRef} />
        {resultados && (
          <span className="contagem pequeno num" aria-live="polite">
            {correspondencias.length} {correspondencias.length === 1 ? 'nó destacado' : 'nós destacados'}
          </span>
        )}
        <select className="seletor" aria-label="Projeto" value={projeto} onChange={(e) => setProjeto(e.target.value)}>
          <option value="">Todos os projetos</option>
          {(dados?.projetos || []).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        {(dados?.epicos || []).length > 0 && (
          <select
            className="seletor"
            aria-label="Épico"
            value={epico}
            onChange={(e) => {
              setEpico(e.target.value);
              setTarefa('');
            }}
          >
            <option value="">Todos os épicos</option>
            {dados.epicos.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        )}
        {tarefasDoFiltro.length > 0 && (
          <select className="seletor" aria-label="Tarefa" value={tarefa} onChange={(e) => setTarefa(e.target.value)}>
            <option value="">Todas as tarefas</option>
            {tarefasDoFiltro.map((t) => (
              <option key={t.chave} value={t.chave}>
                {t.chave}
              </option>
            ))}
          </select>
        )}
        <select className="seletor" aria-label="Período" value={periodo} onChange={(e) => setPeriodo(e.target.value)}>
          {PERIODOS.map(([v, t]) => (
            <option key={v} value={v}>
              {t}
            </option>
          ))}
        </select>
        {mensagem && <span className="contagem pequeno">{mensagem}</span>}
        <span className="espaco" />
        <button className="botao botao-principal" type="button" onClick={() => setNovaAberta(true)}>
          Nova memória
        </button>
      </div>

      {dados && (
        <div className="legenda" role="group" aria-label="Tipos">
          {TODOS_TIPOS.map((tipo) => (
            <button key={tipo} type="button" aria-pressed={tiposAtivos.has(tipo)} onClick={() => alternarTipo(tipo)}>
              <Marca tipo={tipo} />
              <span>{ROTULOS[tipo]}</span>
              <span className="num fraco">{contagemPorTipo[tipo] || 0}</span>
            </button>
          ))}
        </div>
      )}

      {dados && memoriasOrdenadas.length > 1 && !(selecionado && tamanho.w <= 760) && (
        <div className="tempo" style={{ right: selecionado && tamanho.w > 760 ? 412 : 12 }}>
          <button
            className="botao botao-icone"
            type="button"
            aria-label={aReproduzir ? 'Parar' : 'Ver o grafo a crescer'}
            title={aReproduzir ? 'Parar' : 'Ver o grafo a crescer'}
            onClick={() => {
              if (!aReproduzir) setCursor(0);
              setAReproduzir(!aReproduzir);
            }}
          >
            {aReproduzir ? (
              <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                <rect x="2" y="2" width="3" height="8" fill="currentColor" />
                <rect x="7" y="2" width="3" height="8" fill="currentColor" />
              </svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                <polygon points="3,2 10,6 3,10" fill="currentColor" />
              </svg>
            )}
          </button>
          <input
            type="range"
            min={0}
            max={maxCursor}
            value={cursorEfetivo}
            aria-label="Linha temporal"
            onChange={(e) => {
              setAReproduzir(false);
              const v = Number(e.target.value);
              setCursor(v >= maxCursor ? Infinity : v);
            }}
          />
          <span className="data pequeno num">{dataCurta(dataCursor)}</span>
          <span className="pequeno num fraco">{visivel.memorias}</span>
        </div>
      )}

      {aviso && !selecionado && (
        <div className="aviso-versao" role="status">
          Versão {String(aviso.ultima || '').replace(/^v/, '')} disponível. Atualiza com <span className="mono">memoria update</span>
        </div>
      )}

      {noSelecionado && (
        <Suspense fallback={<aside className="painel" aria-busy="true" />}>
          <Painel
            key={noSelecionado.id}
            no={noSelecionado}
            vizinhos={vizinhos}
            onFechar={() => setSelecionado(null)}
            onAbrir={abrirRef}
            idEpico={(chave) => dados?.nos.find((n) => n.tipo === 'epico' && n.epico === chave)?.id}
          />
        </Suspense>
      )}

      {novaAberta && (
        <NovaMemoria
          projetos={dados?.projetos || []}
          epicos={dados?.epicos || []}
          memorias={memoriasOrdenadas}
          projetoAtual={projeto}
          onCancelar={() => setNovaAberta(false)}
          onGuardada={guardada}
        />
      )}
    </div>
  );
}
