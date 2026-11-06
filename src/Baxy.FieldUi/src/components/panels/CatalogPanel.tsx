import { useEffect, useState } from 'react';
import { Panel } from '../Panel';
import { Icon } from '../Icon';
import { getJson } from '../../api';
import { useT } from '../../i18n';

/* «Capacidades de BAXY» (design panels4.jsx BxCatalog, «Qué puedo hacer»): the catalog's real operations, grouped by theme, the ones the
   kernel always confirms in normal mode marked with «!» (GET /catalog, from ProductCatalog and RiskPolicy). */

interface CatalogItem { name: string; title: string; confirm: 'always' | 'sometimes' | 'never' }
interface Catalog { total: number; groups: { name: string; items: CatalogItem[] }[] }

export function CatalogPanel({ onClose }: { onClose: () => void }) {
  const t = useT();
  const [q, setQ] = useState('');
  const [cat, setCat] = useState<Catalog | null | undefined>(undefined);
  useEffect(() => { void getJson<Catalog>('/catalog').then(setCat); }, []);
  const needle = q.trim().toLowerCase();
  return (
    <Panel title={t('Capacidades de BAXY', 'What BAXY can do')} onClose={onClose} width={560}>
      <div className="session-search">
        <Icon name="search" size={13} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('Buscar una acción', 'Search for an action')} aria-label={t('Buscar una acción', 'Search for an action')} />
      </div>
      {cat === null ? <div className="bx-mem-empty" role="status">{t('No se pudo leer el catálogo.', 'Couldn’t read the catalog.')}</div> : null}
      <div className="bx-cat">
        {cat?.groups.map((g) => {
          const f = g.items.filter((x) => !needle || x.title.toLowerCase().includes(needle));
          return f.length ? (
            <div key={g.name} className="bx-tg">
              <div className="panel-sec-head">{g.name}<span>{g.items.length}</span></div>
              <div className="bx-tl">
                {f.map((x) => (
                  <span key={x.name} className={x.confirm === 'always' ? 'cf' : ''} title={x.confirm === 'sometimes' ? t('Pide confirmación según lo que pidas', 'Asks for confirmation depending on the request') : undefined}>
                    {x.title}{x.confirm === 'always' ? <i title={t('Pide confirmación', 'Asks for confirmation')}>!</i> : null}
                  </span>
                ))}
              </div>
            </div>
          ) : null;
        })}
      </div>
      <div className="bx-tnote">
        <span className="cf-k">!</span> {t('pide confirmación en modo normal', 'asks for confirmation in normal mode')} · {cat ? cat.total + t(' acciones del catálogo', ' catalog actions') : '—'}{t('. Algunas más preguntan según lo que pidas: enviar, borrar o un comando que cambia algo.', '. A few more ask depending on the request: sending, deleting, or a command that changes something.')}
      </div>
    </Panel>
  );
}
