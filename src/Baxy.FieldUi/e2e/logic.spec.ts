import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { EXTERNAL_ERROR, translatorSaid } from '../src/externalErrors';
import { UPDATE_FAILED } from '../src/updateErrors';
import { num } from '../src/numbers';
import { readdirSync } from 'node:fs';
import { seededRng } from '../src/utils/seededRng';
import { BXM, HUBS, bxMouth, bxRoute } from '../src/components/face/geometry';
import { LIB, NEXT, groupFor } from '../src/components/avatarClips';
import { causeAdvice, causeText, readingText, startedOnlyOnce } from '../src/causes';
import { translator } from '../src/i18n';
import { outcomeOf } from '../src/outcome';
import { what, when } from '../src/routines';
import { sourcesOf, withoutSource } from '../src/sources';

/* «Unitarias · lógica del diseño» of Baxy pruebas.html, against the view's own modules. The causes are said in the
   interface's language (causes.ts takes its translator): these read them in Spanish. */
const es = translator('es');

test('la falta de memoria dice cuánto cuando se sabe, y nada inventado cuando no', () => {
  expect(causeText('ram_insuficiente', es, { need_mb: 641, free_mb: 512 }))
    .toBe('falta memoria RAM libre en el equipo: no cupo un bloque de 0,6 GB y hay 0,5 GB libres');
  expect(causeText('vram_insuficiente', es, { need_mb: 66406 }))
    .toBe('falta memoria libre en la tarjeta gráfica: no cupo un bloque de 64,8 GB');
  expect(causeText('ram_insuficiente', es)).toBe('falta memoria RAM libre en el equipo');
  expect(causeText('modelo_ausente', es, { need_mb: 1 })).toBe('no se encuentra el archivo del modelo');
  expect(causeText('proceso_salio', es)).toBeNull();
});

test('un equipo que lee el modelo demasiado lento lo dice con lo medido y con qué puede hacer', () => {
  expect(causeText('lectura_lenta', es, null, { tokens_per_s: 20, minutes: 41 }))
    .toBe('este equipo lee el modelo demasiado lento: prepararlo tardaría unos 41 min');
  expect(causeText('lectura_lenta', es)).toBe('este equipo lee el modelo demasiado lento');
  expect(causeText('lectura_lenta', es, null, { tokens_per_s: 46, minutes: 437 }))
    .toBe('este equipo lee el modelo demasiado lento: prepararlo tardaría más de 7 h');
  expect(causeAdvice('lectura_lenta', es)).toContain('tarjeta gráfica dedicada con 4 GB');
  expect(causeText('tiempo', es)).toContain('dejó de avanzar');
  expect(causeAdvice('tiempo', es)).toBe('Actualiza el controlador de la tarjeta gráfica y reintenta. BAXY necesita una tarjeta gráfica dedicada con 4 GB de memoria libres o un procesador más rápido.');
  expect(causeAdvice('ram_insuficiente', es)).toBe('Cierra programas que no estés usando para liberar memoria.');
  expect(startedOnlyOnce('lectura_lenta')).toBe(true);
  expect(startedOnlyOnce('ram_insuficiente')).toBe(false);
});

test('el arranque lento dice cuánto lleva con la cuenta del servidor, y nada inventado cuando no la hay', () => {
  expect(readingText({ done: 16500, total: 48500, seconds_left: 660 }, es)).toBe('Preparando el modelo · 34 % · quedan unos 11 min');
  expect(readingText({ done: 48000, total: 48500, seconds_left: 12 }, es)).toBe('Preparando el modelo · 98 % · queda menos de 1 min');
  expect(readingText({ done: 2048, total: 48500 }, es)).toBe('Preparando el modelo · 4 %');
});

test('el cielo es el mismo en cada redibujado y sus valores están entre 0 y 1', () => {
  const a = seededRng(707), b = seededRng(707);
  let same = true, inRange = true;
  for (let i = 0; i < 20_000; i++) {
    const x = a(), y = b();
    if (x !== y) same = false;
    if (x < 0 || x > 1) inRange = false;
  }
  expect(same, 'mismo cielo').toBe(true);
  expect(inRange, 'valores entre 0 y 1').toBe(true);
});

test('hay un camino continuo de la mente a cada familia de la red', () => {
  const broken: string[] = [];
  for (const k of Object.keys(HUBS).filter((h) => h !== 'web' && h !== 'mente')) {
    const r = bxRoute(k === 'voz' ? ['mente', 'verificar', 'voz'] : ['mente', k]);
    const contiguous = r.every((n, i) => i === 0 || BXM.adj[r[i - 1]].includes(n));
    if (r[0] !== BXM.hub.mente || r[r.length - 1] !== BXM.hub[k] || !contiguous) broken.push(k);
  }
  expect(broken).toEqual([]);
});

test('cada expresión produce una boca válida', () => {
  const exprs = ['neutral', 'happy', 'sad', 'serious', 'curious', 'think', 'listen', 'sleep', 'wink', 'hum'];
  for (const e of exprs) {
    const [pts] = bxMouth(e, -1);
    expect(pts.length, e).toBeGreaterThan(0);
    expect(pts.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y)), e).toBe(true);
  }
});

test('design v5: al hablar la boca es una onda de voz salvo contenta; seria en zigzag; en reposo sonrisa abierta', () => {
  const [wave, wc] = bxMouth('neutral', 0.6);
  expect(wc, 'la onda es abierta').toBe(0);
  expect(wave.length).toBe(15);
  const [open, oc] = bxMouth('happy', 0.6);
  expect(oc, 'contenta habla con la boca abierta').toBe(1);
  expect(open.length).toBeGreaterThan(15);
  const [zig, zc] = bxMouth('serious', -1);
  expect(zc).toBe(0);
  expect(zig.every(([, y], i) => Math.abs(y - (0.46 + (i % 2 ? -0.035 : 0.035))) < 1e-9), 'zigzag').toBe(true);
  const [smile, sc] = bxMouth('neutral', -1);
  expect(sc, 'sonrisa abierta').toBe(1);
  expect(smile[0]).toEqual([-0.23, 0.33]);
});

test('design v5: cada estado tiene su grupo de clips y cada grupo existe en la biblioteca', () => {
  const states = ['booting', 'standby', 'idle', 'listening', 'thinking', 'speaking', 'error', 'confirm'] as const;
  const want: Record<string, string> = { booting: 'reposo', standby: 'dormido', idle: 'reposo', listening: 'escuchando', thinking: 'pensando', speaking: 'hablando', error: 'error', confirm: 'reposo' };
  for (const st of states) expect(groupFor(st, 'neutral'), st).toBe(want[st]);
  expect(groupFor('idle', 'happy')).toBe('contento');
  for (const [g, next] of Object.entries(NEXT)) {
    expect(LIB[g as keyof typeof LIB], g).toBeGreaterThan(0);
    for (const n of next) expect(LIB[n], g + '→' + n).toBeGreaterThan(0);
  }
});

test('design v5: cada variante de la biblioteca tiene su clip en public/clips', async () => {
  const { existsSync } = await import('node:fs');
  const missing = Object.entries(LIB).flatMap(([g, n]) => Array.from({ length: n }, (_, i) => `public/clips/${g}-${i + 1}.mp4`)).filter((f) => !existsSync(f));
  expect(missing).toEqual([]);
});

test('lip-sync: la boca sigue a la voz que suena, cruza pausas cortas y se cierra cuando la voz se corta', async () => {
  const { lipAt, lipPush, lipReset } = await import('../src/lip');
  const { mouthLevel, MOUTH_AT, MOUTH_LEVELS } = await import('../src/components/avatarClips');
  lipReset();
  expect(lipAt(0).known, 'sin línea de tiempo: la boca del clip').toBe(false);
  // 1 s of voice (25 steps of 40 ms), then 0.35 s of the take's own pause
  lipPush({ t0: 1000, step: 40, env: [...Array(25).fill(0.8), ...Array(9).fill(0)] }, 1000);
  expect(lipAt(900).active, 'aún no suena').toBe(false);
  expect(lipAt(950).active, 'la boca se adelanta 80 ms').toBe(true);
  expect(lipAt(1500)).toEqual({ level: 0.8, active: true, known: true });
  expect(lipAt(2200).level, 'en la pausa la boca se cierra').toBe(0);
  expect(lipAt(2200).active, 'una pausa corta sigue siendo hablar').toBe(true);
  expect(lipAt(2500).active, 'pasada la pausa, ya no habla').toBe(false);
  // the next take right after: speaking again; a cut ends it at once
  lipPush({ t0: 2360, step: 40, env: Array(50).fill(0.5) }, 2360);
  expect(lipAt(3000)).toEqual({ level: 0.5, active: true, known: true });
  lipPush({ stop: 3100 }, 3100);
  expect(lipAt(3150).level, 'cortada, la boca no se abre').toBe(0);
  expect(lipAt(3600).active, 'cortada, ya no habla').toBe(false);
  // levels to mouths
  expect(MOUTH_LEVELS.length).toBe(MOUTH_AT.length);
  expect([0, 0.1, 0.2, 0.4, 0.55, 0.7, 0.95].map(mouthLevel)).toEqual([0, 0, 1, 2, 3, 4, 5]);
  lipReset();
});

test('la red marca aparte una llamada que puede haber corrido («?») de una que falló (✕)', async () => {
  // Renew al máximo (w5): a «maybe» step marked nothing on the network; only «fail» had its ✕.
  const { journeyAtEnd } = await import('../src/store');
  const walk = { turn: 't1', path: ['mente', 'apps', 'ventanas'], fail: null, maybe: null };
  const doubtful = journeyAtEnd(walk, 'maybe', 'ventanas');
  expect(doubtful).toEqual({ ...walk, maybe: 'ventanas' });
  expect(journeyAtEnd(doubtful, 'fail', 'apps')).toEqual({ ...walk, maybe: 'ventanas', fail: 'apps' });
  expect(journeyAtEnd(walk, 'ok', 'apps')).toBe(walk);
  expect(journeyAtEnd(walk, 'skip', 'apps')).toBe(walk);
  expect(journeyAtEnd(null, 'maybe', 'apps')).toBeNull();
});

test('el recorrido de la red sólo crece: lo ya caminado no se reordena ni pierde su último tramo, sin familias repetidas seguidas', async () => {
  // a confirmation: the call, BAXY's words asking, the same family again once approved, the final words
  const { reduce, INITIAL } = await import('../src/store');
  const step = (phase: 'start' | 'end', fam: 'archivos' | 'apps', status: 'run' | 'ok' = 'run') => ({ type: 'step' as const, phase, turn: 't1', id: 's', label: 'Borrar', fam, status });
  const reply = (id: string, text: string) => ({ type: 'item' as const, item: { who: 'baxy' as const, id, text, ts: '', steps: [] } });
  const events = [step('start', 'archivos'), reply('b1', '¿Lo borro?'), step('start', 'archivos'), step('end', 'archivos', 'ok'), reply('b2', 'Listo.'),
    step('start', 'apps'), reply('b3', 'Y abrí el Explorador.')];
  let s = INITIAL;
  const seen: string[][] = [];
  for (const ev of events) { s = reduce(s, ev); if (s.journey) seen.push(s.journey.path); }
  // each path the view receives starts with the one before it (the face walks only what was added)
  for (let i = 1; i < seen.length; i++) expect(seen[i].slice(0, seen[i - 1].length), JSON.stringify(seen[i])).toEqual(seen[i - 1]);
  for (const p of seen) expect(p.filter((n, i) => i > 0 && n === p[i - 1]), JSON.stringify(p)).toEqual([]);
  expect(seen[seen.length - 1]).toEqual(['mente', 'archivos', 'verificar', 'archivos', 'verificar', 'apps', 'verificar']);
});

test('la insignia de un pedido dice cómo terminó sólo con los estados de sus pasos, nunca más de lo comprobado', () => {
  const st = (...xs: string[]) => xs.map((status, i) => ({ id: 's' + i, label: 'p', fam: 'apps' as const, status: status as 'ok' }));
  const kind = (...xs: string[]) => outcomeOf(st(...xs))?.kind ?? null;
  expect(kind()).toBeNull();
  expect(kind('ok', 'run')).toBeNull();
  expect(kind('ok', 'ok')).toBe('ok');
  expect(kind('same')).toBe('same');
  expect(kind('ok', 'same')).toBe('ok');
  expect(kind('read')).toBe('read');
  expect(kind('ok', 'sent')).toBe('sent');
  expect(kind('ok', 'maybe')).toBe('maybe');
  expect(kind('ok', 'fail')).toBe('part');
  expect(kind('fail', 'skip')).toBe('fail');
  expect(kind('ok', 'skip')).toBe('part');
  expect(kind('skip')).toBe('skip');
  expect(outcomeOf([{ id: 'w', label: 'clima', fam: 'web', status: 'read', net: 'la ciudad' }])?.label.es).toBe('Leído de la web');
});

test('la fuente que contestó se toma del paso tal como la nombra el host, en español o en inglés, una vez cada una', () => {
  const st = (obs: string) => ({ id: obs, label: 'p', fam: 'web' as const, status: 'read' as const, obs });
  expect(sourcesOf([st('Leído · Fuente: OpenStreetMap'), st('Read · Source: DuckDuckGo'), st('Fuente: OpenStreetMap')])).toEqual(['OpenStreetMap', 'DuckDuckGo']);
  expect(sourcesOf([st('Leído · fuente del dato: 3')])).toEqual([]);
  expect(withoutSource('Leído · Fuente: OpenStreetMap · lugares: 3')).toBe('Leído · lugares: 3');
  expect(withoutSource('Fuente: Wikipedia')).toBe('');
});

// REV_VISTA V-04 (P1, 2026-11-09): in English, 7 of the translator's 19 kinds of failure came out in its Spanish, and the
// «modelo» one said «The company» of Ollama on this PC. The translator gives the kind (ERROR[kind]: its Spanish words); the view
// writes the other language from the kind, the place and the model. Every kind the translator says has its words here, and
// none speaks of a company when the one refusing runs on this PC.
test('cada tipo de fallo del traductor tiene su texto en inglés, y uno local no habla de una empresa', () => {
  const source = readFileSync(new URL('../../baxy_mind/external_model.py', import.meta.url), 'utf8');
  const kinds = [...new Set([...source.matchAll(/Refusal\("(\w+)"/g)].map((m) => m[1]))].sort();
  expect(kinds.length).toBeGreaterThanOrEqual(19);
  expect(Object.keys(EXTERNAL_ERROR).sort()).toEqual(kinds);
  for (const kind of kinds) {
    for (const provider of ['anthropic', 'openai', 'google', 'compatible', 'local']) {
      const words = EXTERNAL_ERROR[kind]({ provider, model: 'lumen:7b' });
      expect(words.length, `${kind} · ${provider}`).toBeGreaterThan(15);
      expect(words, `${kind} · ${provider}`).not.toMatch(/[áéíóúñ¿¡]| del | que | elige | modelo /);
      if (provider === 'local') expect(words, kind).not.toMatch(/compan/i);
    }
  }
  const en = translator('en'), es = translator('es');
  const local = { provider: 'local', model: 'lumen:7b' };
  expect(translatorSaid('ERROR[modelo]: Ollama no tiene el modelo lumen:7b; tiene: brasa:3b', en, local)).toBe('Ollama doesn’t have the model lumen:7b: choose another from the list');
  expect(translatorSaid('ERROR[modelo]: Ollama no tiene el modelo lumen:7b; tiene: brasa:3b', es, local)).toBe('Ollama no tiene el modelo lumen:7b; tiene: brasa:3b');
  // an older log's line with no kind still says something in English, never the Spanish words
  expect(translatorSaid('ERROR: la conexión con la API se cortó (ReadTimeout)', en, local)).not.toMatch(/conexión/);
  expect(translatorSaid('TOPE: 5 USD', en, local)).toBeUndefined();
});

// REV_VISTA V-09 (P2, 2026-11-09): seven update codes came out raw («No pude: baxy_update_source_unknown»). Every failure the
// update handler and the App's panel give has its words in both languages: those Versión says by name, or the table.
test('cada código de fallo de la actualización tiene su texto en español y en inglés, que no es el código', () => {
  const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8');
  const sources = read('../../Baxy.Core/Operations/BaxyUpdateHandler.cs') + read('../../Baxy.App/UpdatePanel.cs');
  const codes = [...new Set([...sources.matchAll(/Failure\("(\w+)"|\(null, "(\w+)"\)|\["error"\] = "(\w+)"/g)].map((m) => m[1] ?? m[2] ?? m[3]))].sort();
  expect(codes.length).toBeGreaterThanOrEqual(12);
  const section = read('../src/components/panels/UpdateSection.tsx');
  const named = new Set([...section.matchAll(/case '(\w+)'/g)].map((m) => m[1]));
  expect(codes.filter((code) => !named.has(code) && !UPDATE_FAILED[code])).toEqual([]);
  for (const [code, words] of Object.entries(UPDATE_FAILED)) {
    expect(words.es.length, code).toBeGreaterThan(20);
    expect(words.en.length, code).toBeGreaterThan(20);
    expect(words.es + words.en, code).not.toContain(code);
  }
});

// REV_VISTA V-13 (P2, 2026-11-09): the spending and the rail wrote toFixed (a decimal point in Spanish too) beside numbers
// written with toLocaleString. One formatter (numbers.ts, Intl.NumberFormat) writes every number the view shows: a comma in
// Spanish and a point in English; nothing else formats a number for the person (the face's canvas colors are not one).
test('un único formateador de números: coma decimal en español, punto en inglés', () => {
  expect(num(1.5, 'es-CL', 2)).toBe('1,50');
  expect(num(1.5, 'en-US', 2)).toBe('1.50');
  expect(num(28000, 'es-CL')).toBe('28.000');
  expect(num(28000, 'en-US')).toBe('28,000');
  expect(num(11.44, 'es-CL', 0, 1)).toBe('11,4');
  expect(num(12, 'es-CL', 0, 1)).toBe('12');
  const walk = (dir: URL): string[] => readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(new URL(e.name + '/', dir)) : /\.tsx?$/.test(e.name) ? [new URL(e.name, dir).pathname] : []);
  const others = walk(new URL('../src/', import.meta.url))
    .filter((path) => !path.endsWith('/numbers.ts') && !path.includes('/face/'))
    .flatMap((path) => [...readFileSync(decodeURIComponent(path).replace(/^\/([A-Za-z]:)/, '$1'), 'utf8').matchAll(/\.(toLocaleString|toFixed)\(|Intl\.NumberFormat/g)]
      .map((m) => path.split('/src/').pop() + ' ' + m[0]));
  // App.tsx turns the face's rotation into a CSS transform (not a number for the person)
  expect(others.filter((o) => o !== 'App.tsx .toFixed(')).toEqual([]);
});

// RUT6: a routine kept as an order shows the person's own words, never a tool's name; one of steps, as before
test('rutinas: una orden guardada se muestra con las palabras de la persona', () => {
  const en = translator('en'), es = translator('es');
  expect(what(es, [], null, 'cambia a los altavoces Vantor')).toBe('Hace lo que pediste: “cambia a los altavoces Vantor”');
  expect(what(en, [], new Map(), 'pause what is playing')).toBe('Does what you asked: “pause what is playing”');
  expect(what(es, [{ say: 'buen día' }], null)).toBe('Dice: “buen día”');
  expect(what(es, [{ op: 'media.control', title: 'Pausar o seguir' }], null, '')).toBe('Pausar o seguir');
});

// RUT3: how a routine starts, in plain words (RUTINAS.md §1 trigger), against a fixed «now» (2026-11-10, 22:00 local)
test('rutinas: el disparador en llano (palabra, hoy, mañana, otro día, cada día, ciertos días, sin fecha)', () => {
  const en = translator('en'), es = translator('es');
  const now = new Date(2026, 10, 10, 22, 0);
  expect(when(es, { phrase: 'audífonos' }, now)).toBe('Cuando dices “audífonos”');
  expect(when(es, { at: '07:30', repeat: 'once', date: '2026-11-10' }, now)).toBe('Hoy a las 7:30, una vez');
  expect(when(es, { at: '09:00', repeat: 'once', date: '2026-11-11' }, now)).toBe('Mañana a las 9:00, una vez');
  expect(when(en, { at: '09:00', repeat: 'once', date: '2026-11-11' }, now)).toBe('Tomorrow at 9:00, once');
  expect(when(es, { at: '18:15', repeat: 'once', date: '2026-12-24' }, now)).toBe('El 24 de diciembre a las 18:15, una vez');
  expect(when(es, { at: '09:00', repeat: 'once' }, now)).toBe('A las 9:00, una vez');
  expect(when(es, { at: '10:00', repeat: 'daily' }, now)).toBe('Todos los días a las 10:00');
  expect(when(es, { at: '07:00', repeat: 'days', days: ['fri', 'mon', 'wed'] }, now)).toBe('Los lunes, miércoles y viernes a las 7:00');
  expect(when(en, { at: '07:00', repeat: 'days', days: ['sat', 'sun'] }, now)).toBe('On Saturdays and Sundays at 7:00');
  expect(when(es, { at: '07:00', repeat: 'days', days: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] }, now)).toBe('Todos los días a las 7:00');
  // the last day of a month and of a year roll over to the next
  expect(when(es, { at: '08:00', repeat: 'once', date: '2027-01-01' }, new Date(2026, 11, 31, 23, 0))).toBe('Mañana a las 8:00, una vez');
});
