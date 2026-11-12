import type { Words } from './i18n';

/* Why an update did not happen, by the code the host gives (Baxy.Core BaxyUpdateHandler, Baxy.App UpdatePanel), and what the
   person can do. REV_VISTA V-09 (2026-11-09): these came out raw, «No pude: baxy_update_source_unknown». A table of its own,
   so that Versión's own words (UpdateSection.tsx, which APP1 is changing) and these merge cleanly; e2e/logic.spec.ts checks that
   every failure code of the host has its words here or there. */
export const UPDATE_FAILED: Record<string, Words> = {
  baxy_update_download_failed: {
    es: 'La descarga del instalador se cortó; BAXY sigue como estaba. Vuelve a pulsar «Buscar actualizaciones» cuando tengas conexión',
    en: 'The installer’s download was cut off; BAXY stays as it was. Press “Check for updates” again once you’re online',
  },
  // UPD1 (REV10 m2): the disk filled up while the installer came; what came was deleted.
  baxy_update_disk_full: {
    es: 'El disco se llenó mientras bajaba el instalador: borré lo que había bajado y BAXY sigue como estaba. Libera espacio y vuelve a pulsar «Buscar actualizaciones»',
    en: 'The disk filled up while I was downloading the installer: I deleted what I had downloaded and BAXY stays as it was. Free some space and press “Check for updates” again',
  },
  baxy_update_installer_missing: {
    es: 'La versión nueva no trae instalador para Windows; BAXY sigue como estaba. Vuelve a buscar más tarde',
    en: 'The new version has no Windows installer; BAXY stays as it was. Check again later',
  },
  // FIR1: missing signature, a signature that isn't BAXY's or an old one under a newer version: the same for the person.
  baxy_update_not_signed: {
    es: 'No pude comprobar que la versión publicada venga firmada por quien hace BAXY, así que no instalé nada: BAXY sigue como estaba',
    en: 'I couldn’t confirm the published version is signed by BAXY’s maker, so I installed nothing: BAXY stays as it was',
  },
  baxy_update_installer_not_started: {
    es: 'Bajé el instalador y Windows no lo abrió; BAXY sigue como estaba. Vuelve a intentarlo, o baja la versión nueva de la página de BAXY en GitHub',
    en: 'I downloaded the installer and Windows didn’t open it; BAXY stays as it was. Try again, or download the new version from BAXY’s GitHub page',
  },
  baxy_update_source_unknown: {
    es: 'Esta copia de BAXY no sabe dónde se publicó, así que no puede buscar versiones nuevas: bájala de donde la conseguiste',
    en: 'This copy of BAXY doesn’t know where it was published, so it can’t look for new versions: get it again where you got it',
  },
  baxy_update_store_not_opened: {
    es: 'Windows no abrió la tienda: ábrela tú y actualiza BAXY desde tu biblioteca',
    en: 'Windows didn’t open the store: open it yourself and update BAXY from your library',
  },
  baxy_update_by_itch_app: {
    es: 'Esta copia la actualiza la app de itch.io: ábrela y actualiza BAXY desde tu biblioteca. Si la bajaste de la página sin la app, baja ahí la versión nueva',
    en: 'This copy is updated by the itch.io app: open it and update BAXY from your library. If you downloaded it from the page without the app, get the new version there',
  },
  update_outcome_unknown: {
    es: 'El motor de BAXY dejó de contestar: no sé si el instalador llegó a abrirse. Si BAXY no se cierra en un minuto, vuelve a pulsar «Buscar actualizaciones»',
    en: 'BAXY’s engine stopped answering: I don’t know whether the installer opened. If BAXY doesn’t close within a minute, press “Check for updates” again',
  },
};
