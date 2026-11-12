import { expect, test, type Page } from '@playwright/test';
import { spawn } from 'node:child_process';
import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { attach, ready, spanish, type App } from './app';

/* The avatar's mouth against the sound the speakers really play (owner, 2026-10-21: «que el avatar hable y que se
   sincronice con lo que realmente está hablando; si se corta antes la animación de habla, no está funcionando bien»).
   scripts/tools/loopcap records BAXY's own sound by WASAPI process loopback (the path comes in BAXY_LOOPCAP, set by
   scripts/test_field_ui.ps1) while the page samples, every frame, the status, the clip and the mouth it draws. Both use
   the wall clock. It must work with or without other sound on the PC (owner, 2026-10-21): while it measures, a tone
   with noise plays from another process, and the measure is still BAXY's alone. The thresholds hold the measurements
   of 2026-10-21 with room: the voice never sounds without the synced mouth, the mouth closes with the voice and not
   before, and it moves with the loudness. */

const LOOPCAP = process.env.BAXY_LOOPCAP ?? '';
let app: App;
let page: Page;
let restoreLang: () => Promise<void>;
test.setTimeout(240_000);
test.beforeAll(async () => {
  app = await attach();
  page = app.page;
  await ready(page);
  restoreLang = await spanish(page);
  await page.waitForFunction(async () => (await (await fetch('/agent/status')).json()).ready === true, undefined, { timeout: 180_000, polling: 1000 });
});
test.afterAll(async () => { await restoreLang?.(); await app.browser.close(); });

interface Ui { t: number; lab: string; g: string; lip: boolean; mouth: number; drawn: number }

// Other sound on the PC while measuring: 45 s of a 440 Hz tone with noise, played by another process.
function noise(): () => void {
  const rate = 22050, n = rate * 45, data = Buffer.alloc(44 + n * 2);
  data.write('RIFF', 0); data.writeUInt32LE(36 + n * 2, 4); data.write('WAVEfmt ', 8); data.writeUInt32LE(16, 16);
  data.writeUInt16LE(1, 20); data.writeUInt16LE(1, 22); data.writeUInt32LE(rate, 24); data.writeUInt32LE(rate * 2, 28);
  data.writeUInt16LE(2, 32); data.writeUInt16LE(16, 34); data.write('data', 36); data.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) data.writeInt16LE(Math.round(32767 * Math.max(-1, Math.min(1, 0.12 * Math.sin((2 * Math.PI * 440 * i) / rate) + 0.04 * (Math.random() * 2 - 1)))), 44 + i * 2);
  const wav = join(tmpdir(), `baxy-lipsync-noise-${Date.now()}.wav`);
  writeFileSync(wav, data);
  const player = spawn('powershell', ['-NoProfile', '-Command', `(New-Object Media.SoundPlayer '${wav}').PlaySync()`], { stdio: 'ignore' });
  return () => { player.kill(); rmSync(wav, { force: true }); };
}

async function record(secs: number, drive: () => Promise<number | void>): Promise<{ audio: [number, number][]; ui: Ui[]; mark: number; start: number }> {
  const out = join(tmpdir(), `baxy-lipsync-${Date.now()}.csv`);
  const stopNoise = noise();
  const cap = spawn(LOOPCAP, [String(secs), out, 'Baxy'], { stdio: 'ignore' });
  const done = new Promise<void>((resolve) => cap.on('exit', () => resolve()));
  await page.waitForTimeout(1500);
  const start = Date.now();
  await page.evaluate(() => {
    const w = window as unknown as { __lip: unknown[]; __lipR: number };
    w.__lip = [];
    let n = 0;
    const tick = () => {
      const av = document.querySelector<HTMLElement>('.bx-avid'), v = document.querySelector<HTMLVideoElement>('.bx-avid video.on');
      const lip = !!av?.classList.contains('lip');
      // every 6th frame while the hole is open: how opaque the composed mouth is at the mouth's centre (0 = an empty
      // box where the mouth was)
      let drawn = -1;
      if (lip && n++ % 6 === 0) {
        const c = document.querySelector<HTMLCanvasElement>('.bx-lip'), d = c?.getContext('2d')?.getImageData(Math.round(c.width / 2), Math.round(c.height / 2), 1, 1).data;
        if (d) drawn = d[3];
      }
      w.__lip.push([Date.now(), (document.querySelector('.bx-statel')?.textContent ?? '').replace('bypass', '').trim(), v?.dataset.g ?? '', lip, av?.dataset.mouth ? +av.dataset.mouth : -1, drawn]);
      w.__lipR = requestAnimationFrame(tick);
    };
    tick();
  });
  const mark = (await drive()) ?? 0;
  const rows = await page.evaluate(() => { const w = window as unknown as { __lip: [number, string, string, boolean, number, number][]; __lipR: number }; cancelAnimationFrame(w.__lipR); return w.__lip; });
  await done;
  stopNoise();
  const audio = existsSync(out)
    ? readFileSync(out, 'utf8').split('\n').filter((l) => l && !l.startsWith('#') && l.split(',').length === 2).map((l) => l.split(',').map(Number) as [number, number])
    : [];
  rmSync(out, { force: true });
  return { audio: audio.filter(([t]) => t >= start), ui: rows.map(([t, lab, g, lip, mouth, drawn]) => ({ t, lab, g, lip, mouth, drawn })), mark, start };
}

async function say(text: string) {
  const input = page.locator('.bx-line > input');
  await input.fill(text);
  await input.press('Enter');
}
const idle = (timeout = 120_000) => page.waitForFunction(() => /^Listo/.test((document.querySelector('.bx-statel')?.textContent ?? '').trim()), undefined, { timeout });

// the sound and the page on one 10 ms grid; loudness in dB under the loudest 10 ms of the recording
function grid(audio: [number, number][], ui: Ui[]) {
  const pk = 20 * Math.log10(Math.max(...audio.map(([, r]) => r)) + 1e-9);
  const t0 = Math.max(audio[0][0], ui[0].t), t1 = Math.min(audio[audio.length - 1][0], ui[ui.length - 1].t);
  const g: { t: number; db: number; u: Ui }[] = [];
  let ai = 0, ui_ = 0;
  for (let t = t0; t < t1; t += 10) {
    while (ai + 1 < audio.length && audio[ai + 1][0] <= t) ai++;
    while (ui_ + 1 < ui.length && ui[ui_ + 1].t <= t) ui_++;
    g.push({ t, db: 20 * Math.log10(audio[ai][1] + 1e-9) - pk, u: ui[ui_] });
  }
  return g;
}

// The ear is off while measuring: with the microphone always on, BAXY answered the room's music in the middle of a
// measurement (2026-10-21) and its second voice was taken for the first. It is put back as it was.
let earWas = '';
test.afterEach(async () => {
  if (earWas === 'wake') await page.evaluate(async () => { await fetch('/voice/start', { method: 'POST' }); });
  earWas = '';
});

test.beforeEach(async () => {
  test.skip(!LOOPCAP || !existsSync(LOOPCAP), 'sin scripts/tools/loopcap (BAXY_LOOPCAP): test_field_ui.ps1 lo compila');
  const general = await page.evaluate(async () => { const r = await fetch('/settings/general'); return r.ok ? r.json() : {}; });
  test.skip(!!(general as { voiceMuted?: boolean }).voiceMuted, 'la voz de BAXY está silenciada en Ajustes');
  await idle();
  earWas = await page.evaluate(async () => (await (await fetch('/voice/status')).json()).mode as string);
  if (earWas !== 'off') await page.evaluate(async () => { await fetch('/voice/stop', { method: 'POST' }); });
});

test('lip-sync: la boca habla mientras suena la voz, con su volumen, y se cierra con ella', async () => {
  const { audio, ui } = await record(40, async () => {
    await say('dime en tres frases qué es un volcán');
    await page.waitForFunction(() => /^Hablando/.test((document.querySelector('.bx-statel')?.textContent ?? '').trim()), undefined, { timeout: 60_000 });
    await idle(30_000);
    await page.waitForTimeout(1200);
  });
  expect(audio.length, 'se grabó lo que suena').toBeGreaterThan(100);
  const checked = ui.filter((u) => u.lip && u.drawn >= 0), empty = checked.filter((u) => u.drawn < 100);
  expect(checked.length, 'se revisó la boca dibujada').toBeGreaterThan(10);
  expect(empty.length, 'con el hueco abierto siempre hay una boca dibujada (nunca un recuadro vacío)').toBe(0);
  const g = grid(audio, ui);
  const voice = g.filter((s) => s.db > -35);
  expect(voice.length * 10, 'BAXY habló (se oyó su voz)').toBeGreaterThan(2000);
  const vs = voice[0].t, ve = voice[voice.length - 1].t;
  const speaking = g.filter((s) => s.u.lab.startsWith('Hablando')), open = g.filter((s) => s.u.mouth >= 1);
  expect(open.length, 'la boca se abrió con la voz').toBeGreaterThan(0);
  expect(speaking.length, 'la vista dijo «Hablando»').toBeGreaterThan(0);
  const ms = (n: number) => n * 10;
  // the first 450 ms: the cut into the speaking clip (0.35 s), when its own mouth shows; from then on, the synced one
  const noMouth = ms(voice.filter((s) => s.t > vs + 450 && !s.u.lip).length);
  const lipOn = g.find((s) => s.t >= vs - 200 && s.u.lip)?.t ?? Infinity;
  const loud = g.filter((s) => s.db > -12), closedLoud = ms(loud.filter((s) => s.u.mouth === 0).length);
  const openSilent = ms(g.filter((s) => s.t > vs && s.t < ve && s.db < -45 && s.u.mouth >= 2).length);
  // lag between loudness and mouth by cross-correlation (positive: the mouth is late)
  const span = g.filter((s) => s.t >= vs - 300 && s.t <= ve + 300);
  const a = span.map((s) => Math.max(0, Math.min(1, (s.db + 45) / 45))), b = span.map((s) => Math.max(0, s.u.mouth));
  const mean = (x: number[]) => x.reduce((p, q) => p + q, 0) / x.length, ma = mean(a), mb = mean(b);
  const corr = (k: number) => {
    let sab = 0, saa = 0, sbb = 0;
    for (let i = Math.max(0, -k); i < a.length - Math.max(0, k); i++) { const x = a[i] - ma, y = b[i + k] - mb; sab += x * y; saa += x * x; sbb += y * y; }
    return sab / Math.sqrt(saa * sbb || 1);
  };
  let lag = 0;
  for (let k = -30; k <= 30; k++) if (corr(k) > corr(lag)) lag = k;
  const report = `voz ${((ve - vs) / 1000).toFixed(1)} s · boca sincronizada a los ${lipOn - vs} ms · sin boca ${noMouth} ms · boca ${open[0].t - vs} / ${open[open.length - 1].t - ve} ms · «Hablando» ${speaking[0].t - vs} / ${speaking[speaking.length - 1].t - ve} ms · cerrada con voz fuerte ${closedLoud}/${ms(loud.length)} ms · abierta en silencio ${openSilent} ms · desfase ${lag * 10} ms · r ${corr(lag).toFixed(2)}`;
  console.log('lip-sync:', report);
  expect.soft(noMouth, 'la voz nunca suena sin la boca sincronizada · ' + report).toBeLessThanOrEqual(Math.max(100, ms(voice.length) * 0.02));
  expect.soft(lipOn - vs, 'la boca sincronizada entra en cuanto termina el corte al clip de hablar · ' + report).toBeLessThanOrEqual(450);
  expect.soft(open[open.length - 1].t - ve, 'la boca no se cierra antes que la voz · ' + report).toBeGreaterThanOrEqual(-150);
  expect.soft(open[open.length - 1].t - ve, 'la boca se cierra cuando la voz termina · ' + report).toBeLessThanOrEqual(200);
  expect.soft(speaking[speaking.length - 1].t - ve, '«Hablando» no termina antes que la voz · ' + report).toBeGreaterThanOrEqual(-100);
  expect.soft(speaking[speaking.length - 1].t - ve, '«Hablando» termina poco después de la voz · ' + report).toBeLessThanOrEqual(900);
  expect.soft(closedLoud, 'con la voz fuerte la boca está abierta · ' + report).toBeLessThanOrEqual(Math.max(100, ms(loud.length) * 0.03));
  expect.soft(openSilent, 'en silencio la boca no queda abierta · ' + report).toBeLessThanOrEqual(300);
  expect.soft(Math.abs(lag * 10), 'boca y voz van juntas · ' + report).toBeLessThanOrEqual(60);
  expect.soft(corr(lag), 'la boca se abre con el volumen · ' + report).toBeGreaterThanOrEqual(0.6);
});

test('lip-sync: si la voz se corta, la boca se cierra con ella', async () => {
  const { audio, ui, mark } = await record(30, async () => {
    await say('cuéntame en seis frases la historia de la imprenta');
    await page.waitForFunction(() => document.querySelector('.bx-avid')?.classList.contains('lip'), undefined, { timeout: 60_000 });
    await page.waitForTimeout(3500);
    const at = Date.now();
    await say('ok, para');
    await page.waitForTimeout(5000);
    await idle(60_000);
    return at;
  });
  const pk = 20 * Math.log10(Math.max(...audio.map(([, r]) => r)) + 1e-9);
  let heard = mark, quiet = 0;
  for (const [t, r] of audio) {
    if (t <= mark) continue;
    if (20 * Math.log10(r + 1e-9) - pk > -40) heard = t;
    else if (t - heard > 300) { quiet = heard; break; }
  }
  expect(quiet, 'la voz se cortó al escribir').toBeGreaterThan(0);
  // up to the reply to «ok, para», whose own voice opens the mouth again (it starts 1.2 s after the cut on one
  // build, under 1.5 s on another: the window ends 100 ms before the next sound, and 1.5 s after the cut at most)
  const next = audio.find(([t, r]) => t > quiet + 300 && 20 * Math.log10(r + 1e-9) - pk > -40)?.[0] ?? Infinity;
  const until = Math.min(quiet + 1500, next - 100);
  const lastOpen = Math.max(...ui.filter((u) => u.t > mark && u.t < until && u.mouth >= 1).map((u) => u.t), mark);
  console.log(`lip-sync corte: la voz calla ${quiet - mark} ms tras escribir, la última boca abierta ${lastOpen - mark} ms`);
  expect(lastOpen - quiet, 'la boca se cierra cuando la voz se corta').toBeLessThanOrEqual(200);
});
