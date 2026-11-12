import { num } from './numbers';

// Every size the view says, in one unit: 2³⁰ bytes, written «GB» as Windows writes it (and as nvidia-smi's MiB add up). A
// weight, a download, free disk and the card are then the same number (VIVO1 F7, 2026-11-09: the same card read «6,3 GB»
// in 10⁹ and «5,9 GB» in 2³⁰ in one tab). Windows' own formatter, StrFormatByteSizeW (shlwapi), counts 1024 to the KB
// (https://learn.microsoft.com/windows/win32/api/shlwapi/nf-shlwapi-strformatbytesizew: 1340 bytes → «1.30 KB»); on this
// PC it wrote 4 700 000 000 bytes as «4.37 GB» and 6 GiB as «6.00 GB» (measured 2026-11-09).
export const GIB = 2 ** 30;

export function size(bytes: number, locale: string, digits = 1): string {
  return num(bytes / GIB, locale, digits) + ' GB';
}
