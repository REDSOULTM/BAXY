import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { AvatarVid } from '../../src/components/AvatarVid';
import type { BaxyState } from '../../src/types';
import '../../src/styles/v4.css';

/* AvatarVid on its own for the tests (e2e/avatar-video.spec.ts): window.bxSet changes its state, window.bxReady
   holds what it last said through onReady, window.bxUnmount takes it off the page. */

declare global {
  interface Window { bxSet: (s: BaxyState) => void; bxReady: boolean | null; bxUnmount: () => void }
}
window.bxReady = null;
const onReady = (ok: boolean) => { window.bxReady = ok; };
const root = createRoot(document.getElementById('root')!);
window.bxSet = (s) => flushSync(() => root.render(<AvatarVid state={s} expr="neutral" onReady={onReady} />));
window.bxUnmount = () => root.unmount();
window.bxSet('idle');
