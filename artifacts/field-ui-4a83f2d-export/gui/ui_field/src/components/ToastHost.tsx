/* Bottom-right toast stack. Rendered once near the root; reacts to
 * pushToast() calls anywhere in the tree via the global event bus. */

import { useToasts } from '../hooks/useToast';
import { Icon } from './Icon';

export function ToastHost() {
  const { toasts, dismiss } = useToasts();
  if (toasts.length === 0) return null;
  return (
    <div className="toast-host" aria-live="polite" aria-atomic="false">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.kind}`} role="status">
          <span className="toast-msg">{t.msg}</span>
          <button
            type="button"
            className="toast-x"
            onClick={() => dismiss(t.id)}
            aria-label="dismiss"
          >
            <Icon name="x" size={10} />
          </button>
        </div>
      ))}
    </div>
  );
}
