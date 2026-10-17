import { Component } from 'react';
import { chamar } from './api.js';
import { t } from './i18n.jsx';

// Um erro ao desenhar (ex.: a parte do painel que só se carrega quando é precisa, com o servidor já parado)
// deixava a página toda em branco. Mostra a mensagem no lugar do que falhou.
export default class Falha extends Component {
  constructor(props) {
    super(props);
    this.state = { erro: null };
  }

  static getDerivedStateFromError(erro) {
    return { erro };
  }

  componentDidCatch() {
    // Se o servidor parou, este pedido falha e a página mostra "a Agent Memory foi fechada".
    chamar('batimento').catch(() => {});
  }

  render() {
    const { erro } = this.state;
    if (!erro) return this.props.children;
    const texto = String((erro && erro.message) || erro);
    // Chrome, Safari e Firefox dizem de maneiras diferentes que o ficheiro já não veio do servidor.
    const semServidor = /dynamically imported module|module script failed|error loading dynamically|Failed to fetch|Load failed/i.test(texto);
    return (
      <div className={this.props.className || 'vazio'} role="alert">
        <p className="vazio-titulo">{semServidor ? t('sessao.fechada.titulo') : t('erro.abrir')}</p>
        <p>{semServidor ? t('sessao.fechada') : texto}</p>
      </div>
    );
  }
}
