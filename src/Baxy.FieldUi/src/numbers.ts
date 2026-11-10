/* Every number the view writes for the person, in the language in use (i18n.ts t.locale): es-CL with a decimal comma and a
   thousands point, en-US the other way round. REV_VISTA V-13 (2026-11-09): the spending and the rail's readings wrote toFixed,
   a decimal point in Spanish too, beside numbers written with toLocaleString. One formatter: Intl.NumberFormat
   (https://developer.mozilla.org/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat), one per locale and digits,
   kept (building one is what costs). e2e/logic.spec.ts fails if another formatter writes a number in src/. */

const made = new Map<string, Intl.NumberFormat>();

/** value with at least `min` and at most `max` decimals (both `min` by default; whole numbers if none) */
export function num(value: number, locale: string, min = 0, max = min): string {
  const key = `${locale}|${min}|${max}`;
  let format = made.get(key);
  if (!format) {
    format = new Intl.NumberFormat(locale, { minimumFractionDigits: min, maximumFractionDigits: max });
    made.set(key, format);
  }
  return format.format(value);
}
