import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { chamar, manterVivo, ponteEmUso } from './api.js';
import Atividade from './Atividade.jsx';
import NovaMemoria from './NovaMemoria.jsx';
import Procura from './Procura.jsx';
import { LINGUAS, aplicarLingua, lingua, t, tx } from './i18n.jsx';
import { FORMAS, Marca, ROTULOS, TIPOS_MEMORIA, TODOS_TIPOS, dataLonga, desenharForma, lerCores } from './tipos.jsx';

// O painel traz o marked e o DOMPurify: só carrega quando é preciso.
const Painel = lazy(() => import('./Painel.jsx'));

// Os textos de cada período vêm do catálogo: periodo.<valor> e periodo.<valor>.curto.
const PERIODOS = ['tudo', '7', '30', '90', '365'];
const RECENTES = 12;
// Com o painel aberto, o grafo encolhe se sobrar espaço; senão o painel fica por cima.
const LARGURA_PAINEL = 420;
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

function claro(cor) {
  const m = /^#([0-9a-f]{6})$/i.exec(cor || '');
  if (!m) return true;
  const n = parseInt(m[1], 16);
  return ((n >> 16) & 255) * 0.299 + ((n >> 8) & 255) * 0.587 + (n & 255) * 0.114 > 128;
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
  const telaRef = useRef(null);
  const prontoEnviado = useRef(false);
  const ajustado = useRef(false);
  const tempos = useRef({});

  const [info, setInfo] = useState(null);
  const [linguaAtual, setLinguaAtual] = useState(lingua);
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState('');
  const [cores, setCores] = useState(lerCores);
  const [tela, setTela] = useState({ w: 0, h: 0 });

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
  // 'mapa' ou 'atividade' (o que o Claude chamou pelo MCP).
  const [vista, setVista] = useState('mapa');

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
        tempos.current.via = await ponteEmUso();
        document.documentElement.dataset.ponte = tempos.current.via;
        setInfo(i);
        setLinguaAtual(aplicarLingua(i.lingua));
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
    const tema = window.matchMedia('(prefers-color-scheme: dark)');
    const mudarTema = () => setCores(lerCores());
    tema.addEventListener('change', mudarTema);
    // O grafo ocupa a área à direita da coluna: mede-a em vez da janela.
    const observador = new ResizeObserver(([e]) => {
      const { width, height } = e.contentRect;
      setTela({ w: Math.round(width), h: Math.round(height) });
    });
    if (telaRef.current) observador.observe(telaRef.current);
    return () => {
      tema.removeEventListener('change', mudarTema);
      observador.disconnect();
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

  // As memórias mais recentes que os filtros (e a linha temporal) deixam ver.
  const recentes = useMemo(
    () => visivel.nodes.filter((n) => TIPOS_MEMORIA.includes(n.tipo)).sort((a, b) => (a.data < b.data ? 1 : -1)).slice(0, RECENTES),
    [visivel],
  );

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
    setVista('mapa');
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
      setMensagem(r.redigidos ? t('guardada_redigidos', { n: r.redigidos }) : t('guardada'));
      setCursor(Infinity);
      await carregar();
      setSelecionado(r.id);
    },
    [carregar],
  );

  const mudarLingua = (codigo) => {
    setLinguaAtual(aplicarLingua(codigo));
    chamar('definir_lingua', codigo).catch((e) => setMensagem(e.message));
  };

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
      // O amarelo da lição tem pouco contraste no fundo claro: leva contorno.
      if (no.tipo === 'licao' && claro(cores.bg)) {
        desenharForma(ctx, forma, no.x, no.y, Math.max(r * 0.6, r - 0.5 / escala));
        ctx.lineWidth = 1 / escala;
        ctx.strokeStyle = comAlfa(cores.ink, 0.5);
        ctx.stroke();
      }
      if (ativo || corresponde) {
        desenharForma(ctx, forma === 'anel' ? 'circulo' : forma, no.x, no.y, r + 3 / escala);
        ctx.lineWidth = (ativo ? 2.5 : 1.5) / escala;
        ctx.strokeStyle = ativo ? cores.ink : cores.muted;
        ctx.stroke();
      }
      const eProjeto = no.tipo === 'projeto';
      const mostrar = ativo || corresponde || no.id === sobre || eProjeto || escala > 2.4;
      if (mostrar && !apagado) {
        // Os projetos são os marcos do mapa: nome maior e mais forte.
        const tamanhoLetra = Math.max((eProjeto ? 14 : 12) / escala, 1.5);
        ctx.font = `${eProjeto ? 650 : 450} ${tamanhoLetra}px ${getComputedStyle(document.body).fontFamily}`;
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
    const forma = FORMAS[no.tipo] === 'anel' ? 'circulo' : FORMAS[no.tipo] || 'circulo';
    desenharForma(ctx, forma, no.x, no.y, raio(no) + 3);
    ctx.fillStyle = cor;
    ctx.fill();
  }, []);

  const corLigacao = useCallback(
    (l) => {
      // Só as ligações explícitas têm peso; o resto é contexto e fica discreto.
      const base = l.tipo === 'ligacao' ? 0.7 : l.tipo === 'ficheiro' || l.tipo === 'projeto' ? 0.14 : 0.24;
      return comAlfa(cores.muted, resultados ? base * 0.35 : base);
    },
    [cores, resultados],
  );

  const quandoDesenhado = useCallback(() => {
    if (prontoEnviado.current || !dados) return;
    prontoEnviado.current = true;
    document.documentElement.dataset.pronto = String(grafoDados.nodes.length);
    chamar('pronto', { ...tempos.current, ms: Math.round(performance.now()), nos: grafoDados.nodes.length }).catch(() => {});
  }, [dados, grafoDados]);

  // Sem memórias o grafo não desenha nada: avisa o selftest na mesma.
  useEffect(() => {
    if (dados && dados.nos.length === 0 && !prontoEnviado.current) {
      prontoEnviado.current = true;
      document.documentElement.dataset.pronto = '0';
      requestAnimationFrame(() => chamar('pronto', { ...tempos.current, ms: Math.round(performance.now()), nos: 0 }).catch(() => {}));
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

  const encolher = Boolean(selecionado) && tela.w - LARGURA_PAINEL >= 480;
  const larguraGrafo = encolher ? tela.w - LARGURA_PAINEL : tela.w;
  const dataCursor = memoriasOrdenadas[cursorEfetivo]?.data;
  const noPassado = aReproduzir || cursor !== Infinity;

  return (
    <div className="app">
      <aside className="coluna" aria-label="Agent Memory">
        <header className="cabeca">
          <div className="cabeca-topo">
            <h1>Agent Memory</h1>
            <select
              className="seletor seletor-lingua"
              aria-label={t('lingua.rotulo')}
              title={t('lingua.rotulo')}
              value={linguaAtual}
              onChange={(e) => mudarLingua(e.target.value)}
            >
              {LINGUAS.map((l) => (
                <option key={l.codigo} value={l.codigo} lang={l.codigo} dir={l.direcao}>
                  {l.nome}
                </option>
              ))}
            </select>
          </div>
          <p className="resumo">
            {dados
              ? t('app.resumo', {
                  memorias: t('plural.memorias', { n: dados.total }),
                  projetos: t('plural.projetos', { n: dados.projetos.length }),
                })
              : t('app.a_abrir')}
          </p>
        </header>

        <div className="segmentos segmentos-vista" role="group" aria-label={t('vista.grupo')}>
          {['mapa', 'atividade'].map((v) => (
            <button key={v} type="button" aria-pressed={vista === v} onClick={() => setVista(v)}>
              {t(`vista.${v}`)}
            </button>
          ))}
        </div>

        <Procura entradaRef={procuraRef} texto={texto} onTexto={setTexto} grupos={grupos} onEscolher={abrirRef} />
        {resultados && (
          <p className="contagem pequeno num" aria-live="polite">
            {t('plural.nos_destacados', { n: correspondencias.length })}
          </p>
        )}

        <div className="filtros">
          <div className="segmentos" role="group" aria-label={t('periodo.grupo')}>
            {PERIODOS.map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={periodo === v}
                aria-label={t(`periodo.${v}`)}
                title={t(`periodo.${v}`)}
                onClick={() => setPeriodo(v)}
              >
                {t(`periodo.${v}.curto`)}
              </button>
            ))}
          </div>
          <select className="seletor" aria-label={t('meta.projeto')} value={projeto} onChange={(e) => setProjeto(e.target.value)}>
            <option value="">{t('filtro.todos_projetos')}</option>
            {(dados?.projetos || []).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          {(dados?.epicos || []).length > 0 && (
            <select
              className="seletor"
              aria-label={t('meta.epico')}
              value={epico}
              onChange={(e) => {
                setEpico(e.target.value);
                setTarefa('');
              }}
            >
              <option value="">{t('filtro.todos_epicos')}</option>
              {dados.epicos.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          )}
          {tarefasDoFiltro.length > 0 && (
            <select className="seletor" aria-label={t('meta.tarefa')} value={tarefa} onChange={(e) => setTarefa(e.target.value)}>
              <option value="">{t('filtro.todas_tarefas')}</option>
              {tarefasDoFiltro.map((t) => (
                <option key={t.chave} value={t.chave}>
                  {t.chave}
                </option>
              ))}
            </select>
          )}
        </div>

        {dados && (
          <div className="tipos" role="group" aria-label={t('tipos.grupo')}>
            {TODOS_TIPOS.map((tipo) => (
              <button key={tipo} type="button" aria-pressed={tiposAtivos.has(tipo)} onClick={() => alternarTipo(tipo)}>
                <Marca tipo={tipo} />
                <span>{ROTULOS[tipo]}</span>
                <span className="num fraco">{contagemPorTipo[tipo] || 0}</span>
              </button>
            ))}
          </div>
        )}

        {dados && dados.total > 0 && (
          <section className="recentes" aria-labelledby="titulo-recentes">
            <h2 id="titulo-recentes">{noPassado ? t('recentes.ate', { data: dataLonga(dataCursor) }) : t('recentes.titulo')}</h2>
            {recentes.length === 0 ? (
              <p className="fraco">{t('recentes.vazio')}</p>
            ) : (
              <ol>
                {recentes.map((n, i) => (
                  <li key={n.id} style={{ '--i': i }}>
                    <button type="button" aria-current={n.id === selecionado ? 'true' : undefined} onClick={() => focar(n)}>
                      <Marca tipo={n.tipo} />
                      <span className="titulo" dir="auto">
                        {n.rotulo}
                      </span>
                      <span className="linha-meta">{[n.projeto, n.tarefa, dataLonga(n.data)].filter(Boolean).join(' · ')}</span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>
        )}

        <div className="coluna-fim">
          {mensagem && (
            <p className="estado" role="status">
              {mensagem}
            </p>
          )}
          {aviso && (
            <p className="aviso-versao" role="status">
              {tx('aviso.versao', { versao: String(aviso.ultima || '').replace(/^v/, '') }, { comando: <code>memoria update</code> })}
            </p>
          )}
          <button className="botao botao-principal botao-largo" type="button" onClick={() => setNovaAberta(true)}>
            {t('nova.botao')}
          </button>
        </div>
      </aside>

      <main className="area">
        <div className="tela" ref={telaRef}>
          {dados && tela.w > 0 && (
            <ForceGraph2D
              ref={grafoRef}
              graphData={grafoDados}
              width={larguraGrafo}
              height={tela.h}
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
                  grafoRef.current?.zoomToFit(semMovimento() ? 0 : 400, 48);
                }
              }}
            />
          )}

          {dados && dados.total === 0 && (
            <div className="vazio">
              <p className="vazio-titulo">{t('vazio.titulo')}</p>
              <p>{t('vazio.texto', { botao: t('nova.botao') })}</p>
            </div>
          )}
          {erro && (
            <div className="vazio">
              <p className="vazio-titulo">{t('erro.abrir')}</p>
              <p>{erro}</p>
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
                onAlterada={carregar}
                idEpico={(chave) => dados?.nos.find((n) => n.tipo === 'epico' && n.epico === chave)?.id}
              />
            </Suspense>
          )}
        </div>

        {vista === 'atividade' && (
          <Atividade
            onAbrir={(id) => {
              setVista('mapa');
              abrirRef(id);
            }}
          />
        )}

        {dados && memoriasOrdenadas.length > 1 && (
          <div className="tempo">
            <button
              className="botao botao-tempo"
              type="button"
              aria-label={aReproduzir ? t('tempo.parar') : t('tempo.ver_crescer_aria')}
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
              <span>{aReproduzir ? t('tempo.parar') : t('tempo.ver_crescer')}</span>
            </button>
            <input
              type="range"
              min={0}
              max={maxCursor}
              value={cursorEfetivo}
              aria-label={t('tempo.linha')}
              aria-valuetext={dataLonga(dataCursor)}
              onChange={(e) => {
                setAReproduzir(false);
                const v = Number(e.target.value);
                setCursor(v >= maxCursor ? Infinity : v);
              }}
            />
            <span className="data num">{dataLonga(dataCursor)}</span>
            <span className="num fraco">{t('plural.memorias', { n: visivel.memorias })}</span>
          </div>
        )}
      </main>

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
