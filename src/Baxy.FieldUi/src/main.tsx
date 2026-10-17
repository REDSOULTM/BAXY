import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
// the three families, packaged locally so BAXY never reaches Google Fonts.
import './styles/fonts.css';
// the design's cascade, in its order: styles.css → baxy.css → v4.css (v4 wins), then the shell's own additions.
import './styles/base.css';
import './styles/baxy.css';
import './styles/v4.css';
import './styles/shell.css';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
