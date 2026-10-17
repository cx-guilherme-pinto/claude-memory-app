import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import Falha from './Falha.jsx';
import './styles.css';

createRoot(document.getElementById('raiz')).render(
  <Falha>
    <App />
  </Falha>,
);
