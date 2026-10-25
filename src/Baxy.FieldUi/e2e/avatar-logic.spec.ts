import { expect, test } from '@playwright/test';
import { MOUTHS, MOUTH_LEVELS } from '../src/components/avatarClips';
import { LipMouth } from '../src/components/mouthBlend';
import { BXM, bxRoute, bxSegment } from '../src/components/face/geometry';

/* The avatar's own logic against the view's modules, with no app: the lip-sync's choice of mouth and the walk of the
   face's network. */

test('la boca que vuelve tras un corte breve se compone en ese mismo fotograma, y es una boca que existe', () => {
  // the voice turns the composed mouth on and off (a 0.35 s cut, a pause): the hole opens again in the video at once,
  // so the mouth must be composed in that frame, even when the last one was composed or changed a moment ago
  const lip = new LipMouth(MOUTH_LEVELS), n = MOUTHS.flat().length, bad: string[] = [];
  const at = (k: number, t: number) => lip.at(k, t);
  at(2, 1000);
  at(4, 1060); // a new level: it holds from 1060
  lip.off(); // a frame without the composed mouth
  for (const [k, t] of [[4, 1076], [4, 1095], [1, 1130]] as const) {
    const m = at(k, t);
    if (!(Number.isInteger(m) && m >= 0 && m < n)) bad.push(t + ' ms → ' + m);
    if (t === 1076) lip.off(); // and off again right away, then on at 1095
  }
  expect(bad, 'una boca en cada fotograma en que el hueco vuelve a abrirse').toEqual([]);
});

test('mientras suena, la boca se compone unas 30 veces por segundo y cada boca dura al menos 50 ms', () => {
  const lip = new LipMouth(MOUTH_LEVELS), n = MOUTHS.flat().length;
  let composed = 0, changes = 0, last = -1, lastChange = -1e9, short = 0;
  for (let t = 5000; t <= 7000; t += 1000 / 60) {
    const m = lip.at(Math.floor(t / 37) % MOUTH_LEVELS.length, t);
    if (m < 0) continue;
    expect(m >= 0 && m < n).toBe(true);
    composed++;
    if (lip.level !== last) { if (t - lastChange < 50) short++; last = lip.level; lastChange = t; changes++; }
  }
  expect(composed, 'unas 30 composiciones por segundo').toBeGreaterThanOrEqual(55);
  expect(composed).toBeLessThanOrEqual(62);
  expect(changes, 'la boca cambia con la voz').toBeGreaterThan(10);
  expect(short, 'ninguna boca dura menos de 50 ms').toBe(0);
});

test('el recorrido que entra o sale de la web va por la red, sin saltar en línea recta por la cara', () => {
  // the antenna's bulb («web») hangs from «mente» only: a turn that searched the internet and then opened an app, or
  // answered (store.ts appends «verificar»), walks back down through «mente»
  const broken: string[] = [];
  for (const hubs of [['mente', 'web', 'verificar'], ['mente', 'web', 'apps'], ['mente', 'apps', 'web'], ['mente', 'archivos', 'web', 'musica']]) {
    for (let k = 0; k < 20; k++) {
      const r = bxRoute(hubs);
      const jumps = r.filter((n, i) => i > 0 && !BXM.adj[r[i - 1]].includes(n)).length;
      const ends = hubs.every((h) => r.includes(BXM.hub[h])) && r[r.length - 1] === BXM.hub[hubs[hubs.length - 1]];
      if (jumps || !ends) { broken.push(hubs.join('→') + ': ' + jumps + ' saltos'); break; }
    }
  }
  expect(broken).toEqual([]);
});

test('cuando el recorrido del turno se reescribe, la cara camina el tramo nuevo hasta su final', () => {
  // store.ts moves «verificar» to the end each time the reply's words change: after a confirmation the path
  // [mente, archivos, verificar, archivos] becomes [mente, archivos, archivos, verificar], of the same length
  const cases: [string[], string[], string[] | null][] = [
    [['mente'], ['mente', 'web'], ['mente', 'web']],
    [['mente', 'web'], ['mente', 'web', 'verificar'], ['web', 'verificar']],
    [['mente', 'archivos', 'verificar', 'archivos'], ['mente', 'archivos', 'archivos', 'verificar'], ['archivos', 'verificar']],
    [['mente', 'apps', 'verificar'], ['mente', 'apps', 'verificar'], null],
  ];
  const wrong = cases.filter(([seen, path, want]) => JSON.stringify(bxSegment(seen, path)) !== JSON.stringify(want))
    .map(([seen, path, want]) => seen.join('→') + ' ⇒ ' + path.join('→') + ': ' + JSON.stringify(bxSegment(seen, path)) + ', no ' + JSON.stringify(want));
  expect(wrong).toEqual([]);
});
