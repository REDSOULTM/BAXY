import { useEffect, useRef } from 'react';
import type { BaxyState } from '../types';
import { LIB, MOUTH_BOX, MOUTH_LEVELS, NEXT, SLEEP_END, clip, groupFor, mouthLevel, type Group } from './avatarClips';
import { lipAt } from '../lip';
import { cutMouths } from './mouths';
import { LipMouth, type MouthBlend } from './mouthBlend';

/* BAXY's avatar in video (design v5, app.jsx BxAvatarVid): a library of Higgsfield clips in public/clips. Every clip
   starts and ends on the same master frame (the «dormido» ones on the sleep frame), so any clip can follow any other
   with a hard cut; «dormirse» and «despertar» bridge the two poses. The state picks the group; a clip ends into a random
   variant of the group, never one of the last two. An urgent state cuts the clip with a 0.35 s fade; idle variants wait
   for the clip to end. A clip is swapped in only once it has a frame (at most 2.5 s; the old one stays meanwhile); only
   the current clip, «reposo» and the likely next one are preloaded; a clip with no frame for 4 s is loaded again. While
   there is no frame the parent draws the whole face in code (onReady false): BAXY is never blank.
   While BAXY's voice sounds, the clip's own mouth is covered and a mouth chosen by the voice's loudness at that instant
   is drawn in its place (lip.ts, avatarClips.ts MOUTH_*): the mouth moves with what is heard, never with the clip. */

interface Clip extends HTMLVideoElement { _t?: number }

export function AvatarVid({ state, expr, onReady }: { state: BaxyState; expr: string; onReady: (ok: boolean) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const want = useRef<Group>('reposo');
  const ready = useRef(onReady);
  const api = useRef<{ nudge: () => void } | null>(null);
  useEffect(() => {
    want.current = groupFor(state, expr);
    ready.current = onReady;
  });

  useEffect(() => {
    const el = wrap.current!;
    let dead = false, front: Clip | null = null, cur: Group | null = null, pose: 'M' | 'S' = 'M';
    const hist: Partial<Record<Group, number[]>> = {};
    const warm: Partial<Record<Group, Clip>> = {};
    let pending: { v: Clip } | null = null;

    const pick = (g: Group) => {
      const n = LIB[g], h = hist[g] ?? [];
      let k: number, tries = 0;
      do { k = 1 + Math.floor(Math.random() * n); } while (n > 1 && h.includes(k) && tries++ < 12);
      hist[g] = [k, ...h].slice(0, Math.min(2, n - 1));
      return k;
    };
    const make = (g: Group): Clip => {
      const v = document.createElement('video') as Clip;
      v.muted = true; v.playsInline = true; v.preload = 'auto'; v.controls = false; v.tabIndex = -1;
      v.disablePictureInPicture = true; v.disableRemotePlayback = true;
      v.setAttribute('playsinline', ''); v.setAttribute('disablepictureinpicture', '');
      v.setAttribute('controlslist', 'nodownload noplaybackrate noremoteplayback nofullscreen');
      v.setAttribute('aria-hidden', 'true');
      v.src = clip(g, pick(g));
      v.dataset.g = g;
      v.addEventListener('ended', () => { if (v === front) advance(false); });
      v.addEventListener('error', () => { if (v === front) window.setTimeout(() => advance(false), 1000); });
      el.appendChild(v);
      v.load();
      return v;
    };
    // a clip taken off the page lets go of its file: a detached video keeps its player and its frames until collected
    const drop = (v: Clip) => { v.pause(); v.removeAttribute('src'); v.load(); v.remove(); };
    const take = (g: Group) => { const v = warm[g] ?? make(g); delete warm[g]; return v; };
    const refill = (g: Group) => { if (!dead && !warm[g]) warm[g] = make(g); };
    const target = (): Group => {
      const g = want.current;
      if (pose === 'S' && g !== 'dormido') return 'despertar';
      if (pose === 'M' && g === 'dormido') return 'dormirse';
      return g;
    };
    const swap = (v: Clip, g: Group, fade: boolean) => {
      const old = front;
      try { v.currentTime = 0; } catch { /* not seekable yet */ }
      void v.play().catch(() => {});
      el.classList.toggle('fade', fade);
      v.classList.add('on');
      if (old) old.classList.remove('on');
      front = v; v._t = performance.now(); cur = g; pose = SLEEP_END[g] ? 'S' : 'M';
      if (old) window.setTimeout(() => drop(old), fade ? 380 : 80);
      // keep only the current clip, «reposo» and the likely next one warm
      for (const k of Object.keys(warm) as Group[]) {
        if (k !== g && k !== 'reposo' && !NEXT[g].includes(k)) {
          const w = warm[k]!; delete warm[k];
          drop(w);
        }
      }
      refill(g); refill('reposo'); NEXT[g].forEach(refill);
    };
    const show = (g: Group, fade: boolean) => {
      const v = take(g);
      if (v.readyState < 2 && front) {
        // the current clip stays on screen until the next one has a frame (at most 2.5 s)
        if (pending && pending.v !== v) drop(pending.v);
        const go = () => { if (dead || !pending || pending.v !== v) return; pending = null; swap(v, g, fade); };
        pending = { v };
        v.addEventListener('loadeddata', go, { once: true });
        window.setTimeout(go, 2500);
        return;
      }
      swap(v, g, fade);
    };
    const advance = (fade: boolean) => { if (!dead) show(target(), fade); };
    api.current = {
      nudge: () => {
        if (dead || !front) return;
        const g = target();
        if (g === cur) return;
        // a calm change (reposo ↔ contento) waits for the clip to end; anything else cuts with a fade
        if ((cur === 'reposo' || cur === 'contento') && (g === 'reposo' || g === 'contento')) return;
        show(g, true);
      },
    };
    let lastOk: boolean | null = null;
    const watchReady = window.setInterval(() => {
      const ok = !!front && front.readyState >= 2;
      if (ok !== lastOk) { lastOk = ok; el.classList.toggle('nf', !ok); ready.current(ok); }
    }, 300);
    const watchdog = window.setInterval(() => {
      if (!dead && front && front.readyState < 2 && !pending && performance.now() - (front._t ?? 0) > 4000) {
        front._t = performance.now();
        const src = front.src; front.src = src; front.load(); void front.play().catch(() => {});
      }
    }, 1500);
    // a window that comes back from the tray or from minimized may find its clip paused: play it again
    const onVis = () => { if (!document.hidden && front && front.paused && !front.ended) void front.play().catch(() => {}); };
    document.addEventListener('visibilitychange', onVis);
    // lip-sync: a canvas over the mouth area where the mouth the voice asks for is composed into the live frame
    const { x: MX, y: MY, w: MW, h: MH } = MOUTH_BOX;
    const lip = document.createElement('canvas');
    lip.className = 'bx-lip'; lip.width = MW; lip.height = MH;
    el.appendChild(lip);
    const lctx = lip.getContext('2d')!;
    const grab = document.createElement('canvas'); grab.width = MW; grab.height = MH;
    const gctx = grab.getContext('2d', { willReadFrequently: true })!;
    let blend: MouthBlend | null = null;
    // cut once the first clip plays, so the start never waits for it; a cut that could not decode every mouth is tried
    // again later (meanwhile the clip keeps its own mouth)
    let cutting = 0, cuts = 0;
    const cutLater = (ms: number) => {
      cutting = window.setTimeout(() => {
        void cutMouths(() => dead).then((b) => {
          if (dead) return;
          blend = b;
          if (b) el.style.setProperty('--lip-hole', 'url(' + b.holeImage() + ')');
          else if (++cuts < 5) cutLater(15_000);
        });
      }, ms);
    };
    cutLater(1500);
    const lipMouth = new LipMouth(MOUTH_LEVELS);
    let lipOn = false, raf = 0;
    const mouth = () => {
      raf = requestAnimationFrame(mouth);
      const L = lipAt(), t = performance.now();
      // only with one clip on screen: during a 0.35 s cut two heads mix (a thinking clip moves its head) and no mouth
      // fits both; meanwhile the speaking clip's own mouth shows
      let shown = 0;
      el.querySelectorAll('video').forEach((v) => { if (+getComputedStyle(v).opacity > 0.01) shown++; });
      // and on a speaking clip: the area replaced is built from its mouths (a resting clip's smile is wider)
      const on = L.known && L.active && !!blend && cur === 'hablando' && !!front && front.readyState >= 2 && shown === 1
        && +getComputedStyle(front).opacity > 0.99;
      if (on !== lipOn) { lipOn = on; el.classList.toggle('lip', on); if (!on) { lctx.clearRect(0, 0, MW, MH); lipMouth.off(); delete el.dataset.mouth; } }
      if (!on) return;
      // composed about 30 times a second, from the frame on screen (mouthBlend.ts LipMouth)
      const m = lipMouth.at(mouthLevel(L.level), t);
      if (m < 0) return;
      gctx.drawImage(front!, MX, MY, MW, MH, 0, 0, MW, MH);
      lctx.putImageData(blend!.compose(gctx.getImageData(0, 0, MW, MH).data, m), 0, 0);
      el.dataset.mouth = String(lipMouth.level);
    };
    raf = requestAnimationFrame(mouth);
    advance(false);
    return () => {
      dead = true;
      cancelAnimationFrame(raf); window.clearTimeout(cutting);
      document.removeEventListener('visibilitychange', onVis);
      window.clearInterval(watchReady); window.clearInterval(watchdog);
      el.querySelectorAll<Clip>('video').forEach(drop);
      ready.current(false);
    };
  }, []);

  useEffect(() => {
    // the state class is set here and not in className: a re-render must never put back «nf» (no frame) or drop
    // «fade», which the player owns; otherwise the video stays hidden while the face draws only the network
    const el = wrap.current!;
    [...el.classList].forEach((c) => { if (c.startsWith('s-') && c !== 's-' + state) el.classList.remove(c); });
    el.classList.add('s-' + state);
    api.current?.nudge();
  }, [state, expr]);
  return <div ref={wrap} className="bx-avid nf" aria-hidden="true"></div>;
}
