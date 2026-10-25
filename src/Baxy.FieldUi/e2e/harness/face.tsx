import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { Face } from '../../src/components/face/Face';
import { Cosmos } from '../../src/components/Cosmos';
import '../../src/styles/base.css';
import '../../src/styles/baxy.css';
import '../../src/styles/v4.css';

/* The drawn face and the starfield on their own for the tests (e2e/avatar-canvas.spec.ts), in a 600 × 500 box. */

const root = createRoot(document.getElementById('root')!);
flushSync(() => root.render(<>
  <Cosmos state="idle" focusX={0.5} light={false} />
  <Face state="idle" expr="neutral" talking={false} journey={null} hold={false} light={false} net={false} />
</>));
