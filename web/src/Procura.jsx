import { useEffect, useMemo, useState } from 'react';
import { Marca, ROTULOS } from './tipos.jsx';

// Caixa de procura com resultados agrupados: Memórias, Projetos, Tarefas e épicos.
// Setas para navegar, Enter para focar, Esc para fechar.
export default function Procura({ entradaRef, texto, onTexto, grupos, onEscolher }) {
  const [aberta, setAberta] = useState(false);
  const [ativo, setAtivo] = useState(0);

  const itens = useMemo(() => {
    if (!grupos) return [];
    return [
      ...grupos.memorias.map((m) => ({ id: m.id, grupo: 'memorias', tipo: m.tipo, nome: m.titulo, lado: m.tarefa || m.projeto })),
      ...grupos.projetos.map((p) => ({ id: p.id, grupo: 'projetos', tipo: 'projeto', nome: p.nome, lado: String(p.total) })),
      ...grupos.chaves.map((c) => ({ id: c.id, grupo: 'chaves', tipo: c.tipo, nome: c.chave, lado: `${ROTULOS[c.tipo]} · ${c.total}` })),
    ];
  }, [grupos]);

  useEffect(() => setAtivo(0), [grupos]);

  const escolher = (item) => {
    if (!item) return;
    setAberta(false);
    onEscolher(item.id);
  };

  const tecla = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setAberta(true);
      setAtivo((i) => Math.min(i + 1, itens.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setAtivo((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      escolher(itens[ativo]);
    } else if (e.key === 'Escape' && aberta) {
      e.stopPropagation();
      setAberta(false);
    }
  };

  const mostrar = aberta && texto.trim() && grupos;
  const secao = (grupo, titulo) => {
    const lista = itens.map((item, i) => ({ item, i })).filter(({ item }) => item.grupo === grupo);
    if (!lista.length) return null;
    return (
      <div role="group" aria-labelledby={`grupo-${grupo}`}>
        <h3 id={`grupo-${grupo}`}>{titulo}</h3>
        <ul>
          {lista.map(({ item, i }) => (
            <li
              key={item.id}
              id={`resultado-${i}`}
              role="option"
              aria-selected={i === ativo}
              onMouseEnter={() => setAtivo(i)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => escolher(item)}
            >
              <Marca tipo={item.tipo} />
              <span className="nome">{item.nome}</span>
              <span className="lado num">{item.lado}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className="procura">
      <input
        ref={entradaRef}
        className="campo campo-procura"
        type="search"
        placeholder="Procurar memória ou ticket"
        aria-keyshortcuts="/"
        title="Procurar (tecla /)"
        aria-label="Procurar memórias, projetos, tarefas e épicos"
        role="combobox"
        aria-expanded={Boolean(mostrar)}
        aria-controls="lista-resultados"
        aria-activedescendant={mostrar && itens.length ? `resultado-${ativo}` : undefined}
        aria-autocomplete="list"
        value={texto}
        onChange={(e) => {
          onTexto(e.target.value);
          setAberta(true);
        }}
        onFocus={() => setAberta(true)}
        onBlur={() => setAberta(false)}
        onKeyDown={tecla}
      />
      {mostrar && (
        <div className="resultados" id="lista-resultados" role="listbox" aria-label="Resultados">
          {itens.length === 0 && <p className="vazio-lista">Sem resultados.</p>}
          {secao('memorias', grupos.total_memorias > grupos.memorias.length ? `Memórias (${grupos.total_memorias})` : 'Memórias')}
          {secao('projetos', 'Projetos')}
          {secao('chaves', 'Tarefas e épicos')}
        </div>
      )}
    </div>
  );
}
