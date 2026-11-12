import type { Step } from './types';

/* The source that answered a step, as the host credits it (FieldStepProjection.Facts, LIC2): the first of the
   observation's facts, «Fuente: …» or «Source: …» in the interface's language, joined with « · ». The view does not read
   BAXY's words or guess a source: it only takes the host's own credit, to show it on the card's face, since the OSMF's
   Attribution Guidelines (osmfoundation.org/wiki/Licence/Attribution_Guidelines, edited 10-09-2026) want the credit seen
   without interacting with the work and next to it. */

const CREDIT = /^(?:Fuente|Source): (.+)$/;

function facts(obs: string | undefined): string[] {
  return obs ? obs.split(' · ') : [];
}

/** the sources credited by a reply's steps, each once, in their order */
export function sourcesOf(steps: readonly Step[]): string[] {
  const seen: string[] = [];
  for (const s of steps) {
    for (const f of facts(s.obs)) {
      const m = CREDIT.exec(f.trim());
      if (m && !seen.includes(m[1])) seen.push(m[1]);
    }
  }
  return seen;
}

/** a step's observation without the credit the card already shows */
export function withoutSource(obs: string): string {
  return facts(obs).filter((f) => !CREDIT.test(f.trim())).join(' · ');
}
