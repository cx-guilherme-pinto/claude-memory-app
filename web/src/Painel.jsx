import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { useEffect, useMemo, useState } from 'react';
import { chamar } from './api.js';
import { dolares, t, tx } from './i18n.jsx';
import { MOTIVOS, Marca, ROTULOS, TIPOS_MEMORIA, dataLonga } from './tipos.jsx';

marked.setOptions({ gfm: true, breaks: false });

const LIGACAO = /\[\[([^\[\]\n|]+)(?:\|([^\]\n]*))?\]\]/g;

// [[nome]] passa a ligação interna; o resto é Markdown sanitizado.
function renderizar(corpo) {
  const comLigacoes = (corpo || '').replace(LIGACAO, (_, nome, alias) => {
    const texto = (alias || nome).trim().replace(/[\[\]]/g, '');
    return `[${texto}](#ligacao:${encodeURIComponent(nome.trim())})`;
  });
  const html = marked.parse(comLigacoes, { async: false });
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['style', 'form', 'input', 'button', 'iframe', 'img'],
    FORBID_ATTR: ['style'],
  });
}

function motivos(m) {
  return Object.keys(m || {})
    .map((k) => MOTIVOS[k] || k)
    .join(', ');
}

const ATALHO_GUARDAR = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘S' : 'Ctrl+S';

export default function Painel({ no, vizinhos, onFechar, onAbrir, idEpico, onAlterada }) {
  const memoria = TIPOS_MEMORIA.includes(no.tipo) || !(no.tipo in ROTULOS);
  const [nota, setNota] = useState(null);
  const [erro, setErro] = useState('');
  // Editor do ficheiro, dentro da app: { texto, original, versao, nome } ou null.
  const [editor, setEditor] = useState(null);
  const [aGuardar, setAGuardar] = useState(false);
  const [estado, setEstado] = useState('');
  const [recarga, setRecarga] = useState(0);

  useEffect(() => {
    if (!memoria) return undefined;
    let vivo = true;
    chamar('nota', no.id)
      .then((n) => vivo && setNota(n))
      .catch((e) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, [no.id, memoria, recarga]);

  useEffect(() => {
    if (!estado) return undefined;
    const t = setTimeout(() => setEstado(''), 4000);
    return () => clearTimeout(t);
  }, [estado]);

  const html = useMemo(() => (nota ? renderizar(nota.corpo) : ''), [nota]);

  const clicarCorpo = async (e) => {
    const a = e.target.closest('a');
    if (!a) return;
    e.preventDefault();
    const href = a.getAttribute('href') || '';
    if (href.startsWith('#ligacao:')) {
      try {
        const alvo = await chamar('nota', decodeURIComponent(href.slice('#ligacao:'.length)));
        onAbrir(alvo.id);
      } catch {
        setErro(t('painel.ligacao_sem_memoria', { nome: a.textContent }));
      }
    } else if (/^https?:\/\//i.test(href)) {
      chamar('abrir_url', href).catch((er) => setErro(er.message));
    }
  };

  const editar = async () => {
    setErro('');
    setEstado('');
    try {
      const f = await chamar('ficheiro', no.id);
      setEditor({ texto: f.texto, original: f.texto, versao: f.versao, nome: f.nome });
    } catch (e) {
      setErro(e.message);
    }
  };

  const alterado = Boolean(editor) && editor.texto !== editor.original;

  const fecharEditor = () => {
    setEditor(null);
    setErro('');
  };

  const guardar = async () => {
    if (!editor || aGuardar) return;
    if (!alterado) {
      fecharEditor();
      return;
    }
    setAGuardar(true);
    setErro('');
    try {
      const r = await chamar('guardar_ficheiro', no.id, editor.texto, editor.versao);
      setEditor(null);
      setEstado(r.redigidos ? t('painel.guardada_redigidos', { n: r.redigidos }) : t('painel.guardada'));
      setRecarga((n) => n + 1);
      onAlterada?.();
    } catch (e) {
      setErro(e.message);
    } finally {
      setAGuardar(false);
    }
  };

  const teclaEditor = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
      e.preventDefault();
      guardar();
    } else if (e.key === 'Escape') {
      // Não fecha o painel por engano; sem alterações, sai do editor.
      e.stopPropagation();
      if (!alterado) fecharEditor();
    }
  };

  return (
    <aside className={editor ? 'painel painel-editar' : 'painel'} aria-label={t('painel.detalhes')}>
      <div className="painel-topo">
        <h2 dir="auto">{no.rotulo}</h2>
        <button className="botao botao-icone" type="button" onClick={onFechar} aria-label={t('painel.fechar')} title={t('painel.fechar_esc')}>
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M2 2 L10 10 M10 2 L2 10" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </button>
      </div>

      {editor ? (
        <form
          className="editor"
          onSubmit={(e) => {
            e.preventDefault();
            guardar();
          }}
        >
          <p className="fraco pequeno">
            {tx('editor.ajuda', {}, { codigo: <code>---</code> })}
          </p>
          <textarea
            className="campo editor-texto"
            value={editor.texto}
            onChange={(e) => setEditor({ ...editor, texto: e.target.value })}
            onKeyDown={teclaEditor}
            spellCheck={false}
            dir="auto"
            aria-label={t('editor.conteudo', { nome: editor.nome })}
            autoFocus
          />
          {erro && (
            <p className="erro" role="alert">
              {erro}
            </p>
          )}
          <div className="acoes">
            <button className="botao botao-principal" type="submit" disabled={aGuardar}>
              {aGuardar ? t('comum.a_guardar') : t('comum.guardar')}
            </button>
            <button className="botao" type="button" onClick={fecharEditor}>
              {t('comum.cancelar')}
            </button>
            <span className="fraco pequeno">{alterado ? t('editor.alteracoes', { atalho: ATALHO_GUARDAR }) : t('editor.sem_alteracoes')}</span>
          </div>
        </form>
      ) : (
        <>
        <dl className="meta">
          <dt>{t('meta.tipo')}</dt>
          <dd>
            <span className="tipo-marca">
              <Marca tipo={no.tipo} />
              {ROTULOS[no.tipo] || no.tipo}
            </span>
          </dd>
          {no.projeto && (
            <>
              <dt>{t('meta.projeto')}</dt>
              <dd>{no.projeto}</dd>
            </>
          )}
          {nota?.tarefa && (
            <>
              <dt>{t('meta.tarefa')}</dt>
              <dd className="num">{nota.tarefa}</dd>
            </>
          )}
          {(nota?.epico || (!memoria && no.tipo === 'tarefa' && no.epico)) && (
            <>
              <dt>{t('meta.epico')}</dt>
              <dd className="num">
                {idEpico(nota?.epico || no.epico) ? (
                  <button className="ligacao-texto" type="button" onClick={() => onAbrir(idEpico(nota?.epico || no.epico))}>
                    {nota?.epico || no.epico}
                  </button>
                ) : (
                  nota?.epico || no.epico
                )}
              </dd>
            </>
          )}
          {nota?.url && (
            <>
              <dt>{t('meta.ticket')}</dt>
              <dd>
                <button className="ligacao-texto" type="button" onClick={() => chamar('abrir_url', nota.url).catch((e) => setErro(e.message))} title={nota.url}>
                  {nota.url.replace(/^https?:\/\//, '')}
                </button>
              </dd>
            </>
          )}
          {nota?.etiquetas?.length > 0 && (
            <>
              <dt>{t('meta.etiquetas')}</dt>
              <dd>{nota.etiquetas.join(', ')}</dd>
            </>
          )}
          <dt>{t('meta.data')}</dt>
          <dd className="num">{dataLonga(nota?.data || no.data)}</dd>
          {nota?.custo_usd != null && (
            <>
              <dt>{t('meta.custo')}</dt>
              <dd className="num">{dolares(nota.custo_usd)}</dd>
            </>
          )}
        </dl>

        {memoria && !nota && !erro && <p className="fraco">{t('comum.a_carregar')}</p>}
        {erro && <p className="erro">{erro}</p>}
        {estado && (
          <p className="estado" role="status">
            {estado}
          </p>
        )}

        {nota && (
          // eslint-disable-next-line react/no-danger
          <div className="markdown" onClick={clicarCorpo} dangerouslySetInnerHTML={{ __html: html }} />
        )}

        {nota?.ficheiros?.length > 0 && (
          <section className="seccao">
            <h3>{t('painel.ficheiros')}</h3>
            <ul className="lista">
              {nota.ficheiros.map((f) => (
                <li key={f}>
                  <code dir="ltr">{f}</code>
                </li>
              ))}
            </ul>
          </section>
        )}

        {nota?.relacionadas?.length > 0 && (
          <section className="seccao">
            <h3>{t('painel.relacionadas')}</h3>
            <ul className="lista lista-motivos">
              {nota.relacionadas.map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => onAbrir(r.id)} title={r.id}>
                    <Marca tipo={r.tipo} />
                    <span dir="auto">{r.titulo}</span>
                    <span className="motivo">{motivos(r.motivos)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {!memoria && (
          <section className="seccao">
            <h3>{t('painel.memorias', { n: vizinhos.length })}</h3>
            <ul className="lista">
              {vizinhos.map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => onAbrir(r.id)} title={r.id}>
                    <Marca tipo={r.tipo} />
                    <span dir="auto">{r.rotulo}</span>
                    <span className="motivo num">{dataLonga(r.data)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {nota && (
          <div className="acoes">
            <button className="botao" type="button" onClick={editar}>
              {t('painel.editar')}
            </button>
            <span className="fraco pequeno">
              <code dir="ltr">{nota.id}.md</code>
            </span>
          </div>
        )}
        </>
      )}
    </aside>
  );
}
