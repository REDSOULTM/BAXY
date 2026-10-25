import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { Face, type FaceProps } from '../../src/components/face/Face';
import { Cosmos } from '../../src/components/Cosmos';
import '../../src/styles/base.css';
import '../../src/styles/baxy.css';
import '../../src/styles/v4.css';

/* The drawn face and the starfield on their own for the tests (e2e/avatar-canvas.spec.ts), in a 600 × 500 box;
   window.bxFace changes the face's props. */

declare global {
  interface Window { bxFace: (p: Partial<FaceProps>) => void }
}
let props: FaceProps = { state: 'idle', expr: 'neutral', talking: false, journey: null, hold: false, light: false, net: false };
const root = createRoot(document.getElementById('root')!);
window.bxFace = (p) => {
  props = { ...props, ...p };
  flushSync(() => root.render(<>
    <Cosmos state={props.state === 'confirm' ? 'idle' : props.state} focusX={0.5} light={false} />
    <Face {...props} />
  </>));
};
window.bxFace({});
