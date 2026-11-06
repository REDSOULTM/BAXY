import { createContext, useContext } from 'react';

/* The interface's own words in Spanish or English. Only what the view itself writes changes: BAXY's replies are the
   model's and come in the language the person used. The language follows Windows (WebView2 takes the system's display
   language as navigator.language) unless the person picks one in Settings. The choice is the host's (GET /settings/general), which resolves it and titles
   the steps in it; systemLang() is only the first paint's guess. */

export type Lang = 'es' | 'en';
export type LangChoice = 'auto' | Lang;
/** a text in both languages; the Spanish one is the original */
export type Words = { es: string; en: string };

export function systemLang(): Lang {
  try {
    return (navigator.language || 'es').toLowerCase().startsWith('es') ? 'es' : 'en';
  } catch {
    return 'es';
  }
}

/** `locale` is what numbers, dates and times are formatted with (toLocaleString and the like) */
export type T = ((es: string, en: string) => string) & { lang: Lang; locale: 'es-CL' | 'en-US'; w: (words: Words) => string };

export function translator(lang: Lang): T {
  const t = ((es: string, en: string) => (lang === 'en' ? en : es)) as T;
  t.lang = lang;
  t.locale = lang === 'en' ? 'en-US' : 'es-CL';
  t.w = (words) => words[lang];
  return t;
}

export const LangContext = createContext<T>(translator('es'));

/** the view's words in the language in use: t('En espera', 'Idle') */
export function useT(): T {
  return useContext(LangContext);
}
