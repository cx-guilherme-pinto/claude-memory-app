import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { useEffect, useMemo, useState } from 'react';
import { chamar } from './api.js';
import { MOTIVOS, Marca, ROTULOS, TIPOS_MEMORIA, dataCurta } from './tipos.jsx';

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

export default function Painel({ no, vizinhos, onFechar, onAbrir, idEpico }) {
  const memoria = TIPOS_MEMORIA.includes(no.tipo) || !(no.tipo in ROTULOS);
  const [nota, setNota] = useState(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    if (!memoria) return undefined;
    let vivo = true;
    chamar('nota', no.id)
      .then((n) => vivo && setNota(n))
      .catch((e) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, [no.id, memoria]);

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
        setErro(`Ligação sem memória: ${a.textContent}`);
      }
    } else if (/^https?:\/\//i.test(href)) {
      chamar('abrir_url', href).catch((er) => setErro(er.message));
    }
  };

  const abrirFicheiro = () => chamar('abrir_ficheiro', no.id).catch((e) => setErro(e.message));

  return (
    <aside className="painel" aria-label="Detalhes">
      <div className="painel-topo">
        <h2>{no.rotulo}</h2>
        <button className="botao botao-icone" type="button" onClick={onFechar} aria-label="Fechar" title="Fechar (Esc)">
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M2 2 L10 10 M10 2 L2 10" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </button>
      </div>

      <dl className="meta">
        <dt>Tipo</dt>
        <dd>
          <span className="tipo-marca">
            <Marca tipo={no.tipo} />
            {ROTULOS[no.tipo] || no.tipo}
          </span>
        </dd>
        {no.projeto && (
          <>
            <dt>Projeto</dt>
            <dd>{no.projeto}</dd>
          </>
        )}
        {nota?.tarefa && (
          <>
            <dt>Tarefa</dt>
            <dd className="mono">{nota.tarefa}</dd>
          </>
        )}
        {(nota?.epico || (!memoria && no.tipo === 'tarefa' && no.epico)) && (
          <>
            <dt>Épico</dt>
            <dd className="mono">
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
            <dt>Ticket</dt>
            <dd>
              <button className="ligacao-texto" type="button" onClick={() => chamar('abrir_url', nota.url).catch((e) => setErro(e.message))} title={nota.url}>
                {nota.url.replace(/^https?:\/\//, '')}
              </button>
            </dd>
          </>
        )}
        {nota?.etiquetas?.length > 0 && (
          <>
            <dt>Etiquetas</dt>
            <dd>{nota.etiquetas.join(', ')}</dd>
          </>
        )}
        <dt>Data</dt>
        <dd className="num">{dataCurta(nota?.data || no.data)}</dd>
        {nota?.custo_usd != null && (
          <>
            <dt>Custo</dt>
            <dd className="num">US$ {Number(nota.custo_usd).toFixed(2)}</dd>
          </>
        )}
      </dl>

      {memoria && !nota && !erro && <p className="fraco">A carregar…</p>}
      {erro && <p className="erro">{erro}</p>}

      {nota && (
        // eslint-disable-next-line react/no-danger
        <div className="markdown" onClick={clicarCorpo} dangerouslySetInnerHTML={{ __html: html }} />
      )}

      {nota?.ficheiros?.length > 0 && (
        <section className="seccao">
          <h3>Ficheiros</h3>
          <ul className="lista">
            {nota.ficheiros.map((f) => (
              <li key={f} className="mono">
                {f}
              </li>
            ))}
          </ul>
        </section>
      )}

      {nota?.relacionadas?.length > 0 && (
        <section className="seccao">
          <h3>Relacionadas</h3>
          <ul className="lista lista-motivos">
            {nota.relacionadas.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => onAbrir(r.id)} title={r.id}>
                  <Marca tipo={r.tipo} />
                  <span>{r.titulo}</span>
                  <span className="motivo">{motivos(r.motivos)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!memoria && (
        <section className="seccao">
          <h3>Memórias ({vizinhos.length})</h3>
          <ul className="lista">
            {vizinhos.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => onAbrir(r.id)} title={r.id}>
                  <Marca tipo={r.tipo} />
                  <span>{r.rotulo}</span>
                  <span className="motivo num">{dataCurta(r.data)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {nota && (
        <div className="acoes">
          <button className="botao" type="button" onClick={abrirFicheiro}>
            Abrir ficheiro
          </button>
        </div>
      )}
      {nota && <p className="mono fraco">{nota.id}.md</p>}
    </aside>
  );
}
