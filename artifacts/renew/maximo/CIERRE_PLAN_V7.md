# Plan de cierre de la fase 4 (holdout v7), escrito antes de sellar y de abrir

Fase 4 («BAXY al máximo sin reentrenar», 2026-10-25, hasta las 22:00): lidera la sesión del notebook (NB) y ejecuta la
del PC, por orden directa del dueño. Holdout v7 (`F:\BAXYeval\renew_v7\holdout`): ≈76 e2e en las 8 áreas de v6 y 36
falsedades, con casos y redacciones nuevos, escritos y sellados por dos agentes aislados del PC que no ven v6, ni las
ramas `nb-w11-*`, ni los informes de casos; sha256 y clave nueva en `metas.json`. Ni el PC ni el NB lo leen antes de la
corrida única.

## Configuraciones

| Nombre | Código |
|---|---|
| `cien` | fin de la fase 3: `int11f` f1d041344 (= renew-cien hasta 8953ecd03) |
| `final` | el candidato que el NB congela y anuncia con su SHA ANTES de que se abra v7 |

## Regla pre-registrada (tal cual la fijó el NB)

Corrida única, 2 semillas, cien frente a final (el candidato que el NB congela y anuncia con su SHA ANTES de que se
abra v7). final reemplaza a cien sólo si se cumplen todas:
(a) e2e v7: media(final) − media(cien) ≥ 0 (se reporta el IC95 pareado y McNemar);
(b) falsedades claras a ciegas (lectura del PC, letras al azar por semilla, clave aparte): final ≤ cien;
(c) confirmaciones: final ≥ cien − 1;
(d) banco de decisión (720 × 3): Δ ≥ −3;
(e) VRAM ≤ 4 096 MiB y RAM con voz ≤ 4 GB (NB, oído real).
Si falla alguna, se queda cien y final queda como propuesta. Nada se reajusta después de abrir.

## Cómo se mide (lo que la regla no dice, fijado ahora)

- **Dónde**: e2e y falsedades en el NB (el escritorio del PC lo usa el dueño), semillas 0 y 1, intercaladas por semilla
  `cien` → `final`; copia `*.nbD.json` (rutas F:→D:) sellada dentro del 7z; arnés común = `scripts/renew` de `final`
  copiado al worktree de `cien` (comprobado con diff).
- **(a)** `pareado.py` sobre los casos puntuados (fuera `setup_fallido`, `void`, `sesion_bloqueada`; un brazo VOID se
  repite antes de mirar sus aciertos); IC95 bootstrap pareado y McNemar exacto por mayoría.
- **(b)** Lectura a mano con `CRITERIO_FALSEDADES.md`, un agente del PC por semilla, las dos configuraciones con letras al
  azar por semilla y la clave en `F:\BAXYeval\renew_v7\holdout\claves-ciego`, revelada después de contar.
- **(c)** Confirmaciones = casos cumplidos del área `confirmacion` (media de las 2 semillas).
- **(d)** Banco de decisión de 720 casos (el del holdout v6, ya abierto y de práctica), 3 semillas en el PC, juez de
  `final`, cada configuración con su catálogo volcado; Δ = media(final) − media(cien) en aciertos.
- **(e)** `measure_resources` del NB con el oído real cargado y `vram_attribution: ok`.
- **Exclusiones**: las de v6; un cambio del perfil sólo bajo `%USERPROFILE%\.claude\` o `.claude.json` no anula un brazo.

## Al congelar

(pendiente: SHA de `final` anunciado por el NB, suites, catálogos y sellos comprobados, antes de extraer)
