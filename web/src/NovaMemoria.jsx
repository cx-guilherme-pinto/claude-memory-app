import { useEffect, useRef, useState } from 'react';
import { chamar } from './api.js';
import { ROTULOS, TIPOS_MEMORIA } from './tipos.jsx';

export default function NovaMemoria({ projetos, memorias, projetoAtual, onCancelar, onGuardada }) {
  const primeiro = useRef(null);
  const [tipo, setTipo] = useState('licao');
  const [titulo, setTitulo] = useState('');
  const [projeto, setProjeto] = useState(projetoAtual || projetos[0] || '');
  const [tarefa, setTarefa] = useState('');
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
      setErro('Preenche o projeto e o texto.');
      return;
    }
    setAGuardar(true);
    try {
      const r = await chamar('adicionar', {
        tipo,
        titulo: titulo.trim(),
        projeto: projeto.trim(),
        tarefa: tarefa.trim(),
        texto,
        ligacoes: ligacoes
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
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
        <h2 id="titulo-nova">Nova memória</h2>
        <div className="grelha">
          <label className="rotulo">
            Tipo
            <select ref={primeiro} className="seletor" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              {TIPOS_MEMORIA.map((t) => (
                <option key={t} value={t}>
                  {ROTULOS[t]}
                </option>
              ))}
            </select>
          </label>
          <label className="rotulo">
            Projeto
            <input className="campo" list="lista-projetos" value={projeto} onChange={(e) => setProjeto(e.target.value)} required />
            <datalist id="lista-projetos">
              {projetos.map((p) => (
                <option key={p} value={p} />
              ))}
            </datalist>
          </label>
          <label className="rotulo inteiro">
            Título (opcional: por omissão, a primeira linha do texto)
            <input className="campo" value={titulo} onChange={(e) => setTitulo(e.target.value)} maxLength={140} />
          </label>
          <label className="rotulo inteiro">
            Texto (Markdown; podes ligar com [[nome]])
            <textarea className="campo" value={texto} onChange={(e) => setTexto(e.target.value)} required />
          </label>
          <label className="rotulo">
            Tarefa (opcional)
            <input className="campo mono" value={tarefa} onChange={(e) => setTarefa(e.target.value)} placeholder="ABC-123" />
          </label>
          <label className="rotulo">
            Ligações (separadas por vírgulas)
            <input className="campo" list="lista-memorias" value={ligacoes} onChange={(e) => setLigacoes(e.target.value)} />
            <datalist id="lista-memorias">
              {memorias.slice(-300).map((m) => (
                <option key={m.id} value={m.rotulo} />
              ))}
            </datalist>
          </label>
        </div>
        <p className="pequeno fraco">Tokens, chaves e passwords são redigidos antes de gravar.</p>
        {erro && <p className="erro">{erro}</p>}
        <div className="acoes">
          <button className="botao botao-principal" type="submit" disabled={aGuardar}>
            {aGuardar ? 'A guardar…' : 'Guardar'}
          </button>
          <button className="botao" type="button" onClick={onCancelar}>
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}
