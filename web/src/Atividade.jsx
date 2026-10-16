import { useEffect, useState } from 'react';
import { chamar } from './api.js';
import { dataLonga, lingua, t } from './i18n.jsx';

// O que o Claude chamou pelo MCP: quatro números e as últimas memórias recordadas.
// Sem separar por sessão nem filtros: é para se ver de relance.
const INTERVALO_MS = 4000;
const LIMITE = 100;

const doisDigitos = (n) => String(n).padStart(2, '0');

function hora(segundos) {
  const d = new Date(segundos * 1000);
  const hoje = new Date().toDateString() === d.toDateString();
  const h = new Intl.DateTimeFormat(lingua(), { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(d);
  if (hoje) return h;
  // Data local (não UTC), no formato que o dataLonga espera.
  return `${dataLonga(`${d.getFullYear()}-${doisDigitos(d.getMonth() + 1)}-${doisDigitos(d.getDate())}`)} ${h}`;
}

function numero(valor, casas = 0) {
  return new Intl.NumberFormat(lingua(), { minimumFractionDigits: casas, maximumFractionDigits: casas }).format(valor || 0);
}

function Numero({ valor, rotulo, nota }) {
  return (
    <div className="numero">
      <span className="numero-valor num">{valor}</span>
      <span className="numero-rotulo">{rotulo}</span>
      {nota && <span className="numero-nota">{nota}</span>}
    </div>
  );
}

export default function Atividade({ onAbrir }) {
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    let vivo = true;
    const ler = () =>
      chamar('atividade', LIMITE)
        .then((d) => {
          if (!vivo) return;
          setDados(d);
          setErro('');
        })
        .catch((e) => vivo && setErro(e.message));
    ler();
    const id = setInterval(ler, INTERVALO_MS);
    return () => {
      vivo = false;
      clearInterval(id);
    };
  }, []);

  return (
    <section className="atividade" aria-labelledby="titulo-atividade">
      <header className="atividade-cabeca">
        <h2 id="titulo-atividade">{t('atividade.titulo')}</h2>
        <p className="fraco pequeno" aria-live="polite">
          {dados?.ultima ? t('atividade.atualizado', { quando: hora(dados.ultima) }) : t('atividade.atualiza')}
        </p>
      </header>

      {erro && <p className="erro">{erro}</p>}

      <div className="numeros">
        <Numero valor={numero(dados?.hoje)} rotulo={t('atividade.hoje')} />
        <Numero valor={numero(dados?.total)} rotulo={t('atividade.total')} />
        <Numero valor={numero(dados?.por_minuto, 1)} rotulo={t('atividade.por_minuto')} nota={t('atividade.por_minuto_nota')} />
        <Numero valor={numero(dados?.distintas)} rotulo={t('atividade.distintas')} nota={t('atividade.distintas_nota')} />
      </div>

      {dados && dados.recordadas.length === 0 ? (
        <div className="atividade-vazio">
          <p className="vazio-titulo">{t('atividade.vazio_titulo')}</p>
          <p>{t('atividade.vazio_texto')}</p>
        </div>
      ) : (
        <>
          <h3 className="atividade-lista-titulo">{t('atividade.lista', { n: LIMITE })}</h3>
          <div className="registo" role="table" aria-label={t('atividade.lista', { n: LIMITE })}>
            <div className="registo-linha registo-cabeca" role="row">
              <span role="columnheader">{t('atividade.col.hora')}</span>
              <span role="columnheader">{t('atividade.col.ferramenta')}</span>
              <span role="columnheader">{t('atividade.col.memoria')}</span>
              <span role="columnheader">{t('meta.projeto')}</span>
              <span role="columnheader">{t('meta.tarefa')}</span>
            </div>
            {(dados?.recordadas || []).map((r, i) => {
              const titulo = r.memoria ? (
                <button type="button" className="ligacao-texto" title={t('atividade.abrir')} onClick={() => onAbrir(r.memoria)}>
                  <span dir="auto">{r.titulo || r.memoria}</span>
                </button>
              ) : (
                <span className="fraco">{t('atividade.sem_resultados')}</span>
              );
              return (
                <div className="registo-linha" role="row" key={`${r.quando}-${i}`}>
                  <span role="cell" className="num fraco">
                    {hora(r.quando)}
                  </span>
                  <span role="cell" title={r.ferramenta}>
                    {t(`ferramenta.${r.ferramenta}`)}
                  </span>
                  <span role="cell" className="registo-memoria">
                    {titulo}
                    {r.texto && r.ferramenta === 'memoria_procurar' && (
                      <span className="fraco pequeno registo-pesquisa" dir="auto">
                        {t('atividade.pesquisa', { texto: r.texto })}
                      </span>
                    )}
                  </span>
                  <span role="cell" dir="auto">
                    {r.projeto}
                  </span>
                  <span role="cell" className="num" dir="ltr">
                    {r.tarefa || r.epico}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
