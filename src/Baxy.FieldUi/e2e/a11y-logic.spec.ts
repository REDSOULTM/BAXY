import { expect, test } from '@playwright/test';
import { wrapTab } from '../src/utils/dialogFocus';
import { liveText } from '../src/live';
import { spoken } from '../src/duration';
import { translator } from '../src/i18n';

/* Final 4, accesibilidad: the view's own pieces, with no app and no browser. A panel keeps Tab inside it, and what is drawn
   for a moment is also said to a screen reader. (A component cannot be rendered here: Playwright's runner turns JSX
   into its own objects.) */

test('Tab da la vuelta dentro del panel y nunca sale a la vista de debajo', () => {
  const dialog = {} as HTMLElement, a = {} as HTMLElement, b = {} as HTMLElement, c = {} as HTMLElement;
  const all = [a, b, c];
  expect(wrapTab(all, c, false, dialog), 'del último al primero').toBe(a);
  expect(wrapTab(all, a, true, dialog), 'Mayús+Tab del primero al último').toBe(c);
  expect(wrapTab(all, dialog, true, dialog), 'Mayús+Tab desde el propio panel al último').toBe(c);
  expect(wrapTab(all, b, false, dialog), 'en medio, Tab es del navegador').toBeNull();
  expect(wrapTab([], dialog, false, dialog), 'sin controles no hay nada que hacer').toBeNull();
});

test('la región viva dice la salida a internet, si no el aviso, si no el fallo', () => {
  expect(liveText('el clima de Lima', { b: 'Voz', t: 'micrófono apagado' }, 'Algo falló')).toBe('Salió a internet: el clima de Lima');
  expect(liveText(null, { b: 'Confirmación', t: 'no se pudo cambiar' }, 'Algo falló')).toBe('Confirmación: no se pudo cambiar');
  expect(liveText(null, null, 'El modelo no respondió')).toBe('El modelo no respondió');
  expect(liveText(null, null, null)).toBe('');
});

test('las palabras de la vista siguen el idioma elegido, y el español queda como estaba', () => {
  const es = translator('es'), en = translator('en');
  expect(liveText('el clima de Lima', null, null, en)).toBe('Went online: el clima de Lima');
  expect(es('En espera', 'Idle')).toBe('En espera');
  expect(en('En espera', 'Idle')).toBe('Idle');
  expect(en.w({ es: 'Esperando tu ok', en: 'Waiting for your OK' })).toBe('Waiting for your OK');
  expect([es.locale, en.locale]).toEqual(['es-CL', 'en-US']);
  expect([spoken(120, es), spoken(60, es), spoken(45, es), spoken(null, es)]).toEqual(['2 minutos', '1 minuto', '45 segundos', '—']);
  expect([spoken(120, en), spoken(60, en), spoken(45, en)]).toEqual(['2 minutes', '1 minute', '45 seconds']);
});
