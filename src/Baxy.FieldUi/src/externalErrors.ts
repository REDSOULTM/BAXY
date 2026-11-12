import type { T } from './i18n';

/* The translator's failures (external_model.py: «ERROR[kind]: words», its words in Spanish) said in English by their kind, the
   place the model is in and its name. REV_VISTA V-04 (2026-11-09): 7 of the 19 kinds came out in Spanish in an English view, and
   «modelo» said «The company» of Ollama on this PC. Every kind the translator writes has its words here (e2e/logic.spec.ts reads
   them from external_model.py). Spanish is the translator's own line: it names what it knows (the status, the models it has). */

/** the place and the model the failure is about (Settings › Modelo: provider and model) */
export interface Failing {
  provider?: string | null;
  model?: string | null;
}

// Who refuses, as the translator names it (COMPANIES): a company by its name, «Otra» as that API, Ollama or BAXY's server on this PC.
const WHO: Record<string, string> = { anthropic: 'Anthropic', openai: 'OpenAI', google: 'Google', compatible: 'That API', local: 'The local server' };

type Say = (f: { who: string; model: string; local: boolean; provider: string }) => string;

const SAY: Record<string, Say> = {
  clave: ({ who }) => `${who} refused the key: check you copied it whole, or create another one in its console`,
  permiso: ({ who, model }) => `${who} doesn’t let this key use ${model}`,
  modelo: ({ who, model, provider }) => `${provider === 'local' ? 'Ollama' : provider === 'compatible' ? 'That server' : who} doesn’t have the model ${model}: choose another from the list`,
  saldo: ({ who }) => `${who} won’t serve: your account has no credit left or reached its spending limit. Check it in its console`,
  limite: ({ who }) => `${who} is limiting your account’s calls for a moment: wait a minute and ask again`,
  saturado: ({ who }) => `${who} is overloaded right now: try again in a few minutes`,
  caido: ({ who }) => `${who} had a failure on its server: try again later`,
  rechazo: ({ who }) => `${who} answered with an error BAXY doesn’t know: try again, or choose another model`,
  red: ({ who, local }) => local ? `${who} doesn’t answer: check that it’s running` : `There’s no connection with ${who === 'That API' ? 'that API' : who}: check the internet connection`,
  lento: ({ who }) => `${who} didn’t answer in time: ask again`,
  cortado: () => 'The connection with the model was cut: ask again',
  redirige: () => 'That address redirects elsewhere and BAXY doesn’t follow it: type the final one',
  ilegible: ({ who }) => `${who} answered something that couldn’t be read`,
  sdk: () => 'This installation of BAXY is missing Anthropic’s component: update or reinstall BAXY',
  plantilla: ({ who, model }) => `${who} can’t use ${model} with BAXY’s tools: the model’s chat template doesn’t accept the conversation. Choose another model`,
  memoria: ({ model }) => `${model} doesn’t fit in this PC’s memory: choose another model or less context`,
  vram: ({ model }) => `${model} doesn’t fit in the free VRAM with that context: choose less context`,
  carga: ({ model }) => `${model} couldn’t be loaded: try again, or choose another model or less context`,
  corto: ({ model }) => `${model} read only part of what BAXY sends it: it doesn’t fit its context`,
  perfil: ({ model }) => `${model} doesn’t hold the chosen tool profile: choose a smaller profile in Settings → Tools, or another model`,
  nube: ({ model }) => `${model} runs outside this PC, in Ollama’s cloud`,
  ollama: () => 'Ollama doesn’t answer',
};

/** each kind's English words for a model at a place (the e2e test walks them all) */
export const EXTERNAL_ERROR: Record<string, (f: Failing) => string> = Object.fromEntries(Object.entries(SAY).map(([kind, say]) => [kind, (f: Failing) => {
  const provider = f.provider ?? '';
  return say({ who: WHO[provider] ?? 'The API', model: f.model || 'the model', local: provider === 'local', provider });
}]));

/** The translator's words for a failure (ExternalModel.LastError, or the turn's failureWhy with failureKind) in the person's
    language; nothing for the spending cap, which is not a failure of the model. An older log's line with no kind is said in
    English as a failure without its words. */
export function translatorSaid(lastError: string | null | undefined, t: T, failing: Failing): string | undefined {
  if (!lastError || lastError.startsWith('TOPE')) return undefined;
  const kind = /^ERROR\[(\w+)\]/.exec(lastError)?.[1];
  return refusalSaid(kind, lastError.replace(/^ERROR[^:]*:\s*/, ''), t, failing);
}

/** A failure's words by its kind: the translator's Spanish, or this view's English. */
export function refusalSaid(kind: string | null | undefined, said: string, t: T, failing: Failing): string {
  const en = kind && EXTERNAL_ERROR[kind] ? EXTERNAL_ERROR[kind](failing) : 'The model failed: its log says why, in Spanish';
  return t(said, en);
}
