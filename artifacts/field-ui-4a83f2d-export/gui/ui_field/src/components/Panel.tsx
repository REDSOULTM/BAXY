import type { PropsWithChildren } from 'react';
import { Icon } from './Icon';

interface Props {
  title: string;
  onClose: () => void;
  /** custom width override. defaults to the prototype's 480px from .panel. */
  width?: number;
  /** extra class on the inner panel (e.g. "settings-panel" to swap width/height). */
  className?: string;
}

export function Panel({ title, onClose, width, className, children }: PropsWithChildren<Props>) {
  const inner = `panel${className ? ` ${className}` : ''}`;
  return (
    <div className="panel-shroud" onClick={onClose} role="presentation">
      <div
        className={inner}
        style={width ? { width } : undefined}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="panel-head">
          <span className="panel-title">{title}</span>
          <button className="ibtn" onClick={onClose} data-tip="close" aria-label="close">
            <Icon name="x" />
          </button>
        </div>
        <div className="panel-body">{children}</div>
      </div>
    </div>
  );
}
