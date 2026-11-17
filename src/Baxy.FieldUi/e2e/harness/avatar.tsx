import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { AvatarVid } from '../../src/components/AvatarVid';
import type { BaxyState } from '../../src/types';
import '../../src/styles/v4.css';

/* AvatarVid on its own for the tests (e2e/avatar-video.spec.ts): window.bxSet changes its state, window.bxReady
   holds what it last said through onReady, window.bxUnmount takes it off the page; ?strict renders it in StrictMode
   (as main.tsx does), whose development build mounts every effect twice; ?first=<state> is the state it mounts with
   (idle when not given); bxSet's second argument is the `still` the view passes (still.ts; derived from the state when
   not given); its third, whether the window is calm (still.ts useCalm). */

declare global {
  interface Window { bxSet: (s: BaxyState, still?: boolean, calm?: boolean) => void; bxReady: boolean | null; bxUnmount: () => void }
}
window.bxReady = null;
const onReady = (ok: boolean) => { window.bxReady = ok; };
const root = createRoot(document.getElementById('root')!), strict = new URLSearchParams(location.search).has('strict');
window.bxSet = (s, still, calm) => flushSync(() => root.render(strict
  ? <StrictMode><AvatarVid state={s} expr="neutral" onReady={onReady} still={still} calm={calm} /></StrictMode>
  : <AvatarVid state={s} expr="neutral" onReady={onReady} still={still} calm={calm} />));
window.bxUnmount = () => root.unmount();
window.bxSet((new URLSearchParams(location.search).get('first') as BaxyState | null) ?? 'idle');
