import { useEffect, useRef, useState } from 'react';
import { chamar } from './api.js';
import { t } from './i18n.jsx';
import { ROTULOS, TIPOS_MEMORIA } from './tipos.jsx';

const lista = (texto) =>
  texto
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

export default function NovaMemoria({ projetos, memorias, epicos, projetoAtual, onCancelar, onGuardada }) {
  const primeiro = useRef(null);
  const [tipo, setTipo] = useState('licao');
  const [titulo, setTitulo] = useState('');
  const [projeto, setProjeto] = useState(projetoAtual || projetos[0] || '');
  const [tarefa, setTarefa] = useState('');
  const [epico, setEpico] = useState('');
  const [url, setUrl] = useState('');
  const [etiquetas, setEtiquetas] = useState('');
  const [texto, setTexto] = useState('');
  const [ligacoes, setLigacoes] = useState('');
  const [aGuardar, setAGuardar] = useState(false);
  const [erro, setErro] = useState('');

  useEffect(() => {
    primeiro.current?.focus();
    const tecla = (e) => e.key === 'Escape' && onCancelar();
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [onCancelar]);

  const guardar = async (e) => {
    e.preventDefault();
    setErro('');
    if (!projeto.trim() || !texto.trim()) {
      setErro(t('nova.preenche'));
      return;
    }
    setAGuardar(true);
    try {
      const r = await chamar('adicionar', {
        tipo,
        titulo: titulo.trim(),
        projeto: projeto.trim(),
        tarefa: tarefa.trim(),
        epico: epico.trim(),
        url: url.trim(),
        etiquetas: lista(etiquetas),
        texto,
        ligacoes: lista(ligacoes),
      });
      onGuardada(r);
    } catch (er) {
      setErro(er.message);
      setAGuardar(false);
    }
  };

  return (
    <div
      className="fundo-dialogo"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancelar();
      }}
    >
      <form className="dialogo" role="dialog" aria-modal="true" aria-labelledby="titulo-nova" onSubmit={guardar}>
        <h2 id="titulo-nova">{t('nova.botao')}</h2>
        <div className="grelha">
          <label className="rotulo">
            {t('meta.tipo')}
            <select ref={primeiro} className="seletor" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              {TIPOS_MEMORIA.map((t) => (
                <option key={t} value={t}>
                  {ROTULOS[t]}
                </option>
              ))}
            </select>
          </label>
          <label className="rotulo">
            {t('meta.projeto')}
            <input className="campo" list="lista-projetos" value={projeto} dir="auto" onChange={(e) => setProjeto(e.target.value)} required />
            <datalist id="lista-projetos">
              {projetos.map((p) => (
                <option key={p} value={p} />
              ))}
            </datalist>
          </label>
          <label className="rotulo inteiro">
            {t('nova.titulo')}
            <input className="campo" value={titulo} dir="auto" onChange={(e) => setTitulo(e.target.value)} maxLength={140} />
          </label>
          <label className="rotulo inteiro">
            {t('nova.texto')}
            <textarea className="campo" value={texto} dir="auto" onChange={(e) => setTexto(e.target.value)} required />
          </label>
          <label className="rotulo">
            {t('nova.tarefa')}
            <input className="campo" value={tarefa} onChange={(e) => setTarefa(e.target.value)} placeholder="ABC-123" dir="ltr" />
          </label>
          <label className="rotulo">
            {t('nova.epico')}
            <input className="campo" list="lista-epicos" value={epico} onChange={(e) => setEpico(e.target.value)} placeholder="ABC-100" dir="ltr" />
            <datalist id="lista-epicos">
              {epicos.map((e) => (
                <option key={e} value={e} />
              ))}
            </datalist>
          </label>
          <label className="rotulo">
            {t('nova.url')}
            <input className="campo" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" dir="ltr" />
          </label>
          <label className="rotulo">
            {t('nova.etiquetas')}
            <input className="campo" value={etiquetas} dir="auto" onChange={(e) => setEtiquetas(e.target.value)} />
          </label>
          <label className="rotulo inteiro">
            {t('nova.ligacoes')}
            <input className="campo" list="lista-memorias" value={ligacoes} dir="auto" onChange={(e) => setLigacoes(e.target.value)} />
            <datalist id="lista-memorias">
              {memorias.slice(-300).map((m) => (
                <option key={m.id} value={m.rotulo} />
              ))}
            </datalist>
          </label>
        </div>
        <p className="pequeno fraco">{t('nova.redacao')}</p>
        {erro && <p className="erro">{erro}</p>}
        <div className="acoes">
          <button className="botao botao-principal" type="submit" disabled={aGuardar}>
            {aGuardar ? t('comum.a_guardar') : t('comum.guardar')}
          </button>
          <button className="botao" type="button" onClick={onCancelar}>
            {t('comum.cancelar')}
          </button>
        </div>
      </form>
    </div>
  );
}
