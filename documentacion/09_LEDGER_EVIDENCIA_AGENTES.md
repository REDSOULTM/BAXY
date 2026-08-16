# Ledger de evidencia recuperada de agentes

## Regla de uso

Los 322 segmentos recuperados son procedencia, no 322 mediciones
independientes. Este ledger registra las auditorías que pueden cambiar una
decisión de BAXY 1.0. La identidad es el ID de sesión y el SHA-256 del segmento
publicado en `documentacion/agentes/manifest.json`; no se publican rutas ni
contenido privado.

Clasificación:

- **corroborada**: coincide con una fuente primaria o ejecución local;
- **parcial**: parte está demostrada y parte continúa abierta;
- **diseño**: propone un gate, pero no lo ejecutó;
- **histórica**: describía correctamente un commit anterior, no el actual;
- **contradicha**: otra evidencia primaria refuta la conclusión;
- **hipótesis**: requiere medición antes de decidir.

## Auditorías decisivas

| Informe | Sesión / SHA-256 del segmento | Clasificación | Uso permitido en BAXY 1.0 |
|---|---|---|---|
| `audit_soak_vram` | `019f58d3…` / `6a84fab50cb0b132f9ab165e6fa89fb293f105f77fee84cfb36a1200b73a7216` | parcial | Conserva 86.400 s y 285/285 como ejecución, pero el gate formal falló por GPU global/gap; no demuestra ausencia de leak atribuible |
| `audit_local_gemma_profile` | `019f58d4…` / `111d27ed78893d17e84ea2984c99f8ee18d720d17409b3e4ca548a0f9f31fe09` | corroborada | Fija identidad b9959 y contaminación por override STT; prohíbe afirmar GPU física de 4 GB |
| `natural_language_regressions` | `019f5ae3…` / `0b3210f597bfe32ae5ac9cafdea72026bd5d0cc9988568aae178476bffedd773` | histórica | Los 14 fallos/10 aciertos son casos de regresión, no estado del producto nuevo |
| `voice_wake_gap_audit` | `019f5b2e…` / `d38b371ca09fd2217f9a3d8e514020485555cb64123559ed0367d59bcbec88ad` | corroborada | Exige validar wake, barge-in acústico, coherencia hablado/mostrado y wiring de settings |
| `completion_matrix_audit` | `019f5b37…` / `a0fe5d9d2c7a9be9daa0a67ca425a78331423fffd299eaaf3f3d3e71a87bda1e` | parcial | Inventario de huecos; no es attestation final |
| `packaging_release_audit` | `019f5b3d…` / `7841fa4ea461b9d085ecb4a75b0ec6e443d4741e1132e3439365416c0c32fcbb` | corroborada | Impone separar app/datos, runtime autocontenido, pins, instalador, SBOM/legal, uninstall y rollback |
| `physical_voice_validation_design` | `019f5b86…` / `3f357c16d08ff1f283cc2cbdfdb734ab193f920aa9be953819cab4d8def32b31` | diseño | Reutilizar procedimiento; no declarar micrófono ejecutado |
| `privacy_effects_audit` | `019f5bc4…` / `5a14d48a4e02332b7f40de1b7a3fee3c3b6b532e22693a9e82f54e7e12df1711` | histórica/parcial | El bypass default-off quedó obsoleto tras el cutover; riesgos de endpoint remoto, texto plano y legacy siguen vigentes |
| `real_world_acceptance_map` | `019f5bd0…` / `fab93bfdbc84082bcdcfa7ef0cac2b3fada20e150bbb60c8a28d61682ca96df0` | corroborada | Separa routing, fixture y efecto real; las 76 misiones propuestas son semilla, no cobertura total |
| `small_llm_tool_research` | `019f5be4…` / `855f7fdd12a648217f21c31cd2a934ec12fb238ccdbd0d7ff98392b5e4d2a7cb` | hipótesis | Candidatos sólo entran al torneo con licencia, recursos y corte equivalente |
| `steam_productive_composition` | `019f5c02…` / `708c19ca4a9e179e7f586af2747ee3c106de0077d2a35f5d61f6b2ab9b41b3ec` | diseño/parcial | Conserva composición y verificadores; requiere cuenta/cliente autorizados para gate real |
| `agentbench` | `019f5c2d…` / `2adce9c40813bd4544c2ad8d15313ac1a5c929f9c12495cbf0d272a8d176a07d` | hipótesis | Referencia de métricas; no reemplaza corpus histórico ni misiones locales |
| `windows_distribution` | `019f5c42…` / `1bed74ffea49d7725c134ef0b87c903e6dd48f145fa205474633593509482f7b` | hipótesis | Alternativas de instalación deben competir y probarse en Windows limpio |
| `tts_natural_audit` | `019f5c5b…` / `20fc2226537b8d2ccb72743dd9771e196c87b9be5464247cc8d0603d33a54148` | parcial | Criterios de naturalidad/latencia; la voz final necesita escucha humana autorizada |
| `carter_failure_archaeology` | `019f5c89…` / `098566d22f758c56f78045d9419e2e7717ee846d5147b8a3c6f5c0654dd303e0` | corroborada | Dispatch/efecto/intención, stubs, huérfanos, GUI stale y visual diff alimentan regresiones R-001…R-030 |
| `legacy_capabilities` | `019f5c89…` / `b8dcba73e910909e380c1e805057d32f8517a0e9f634fcffac55214de6ecfc09` | corroborada | Reutilizar algoritmos/casos, no el árbol completo; FG, skills, visión y memoria deben rediseñarse |
| `product_attestation` | `019f5cac…` / `f325b35e57b3051608b1a72104d0eec8d3a652ae687b54ab199699fee4bbf876` | diseño/parcial | Attestation debe medir binarios, modelos, catálogo, flags y providers en runtime |
| `tool_v2_mission_matrix` | `019f5d22…` / `90f2176db5ad8525fc7ae3b1456dce0e51f96f58a837bc31f18bed6ceb055a65` | parcial | 107 misiones offline/110 tests son regresión; simulación y gaps no aprueban providers |
| `owned_live_acceptance` | `019f5d5e…` / `f1a44792db2f3c2b508c4a20eeb85c30b9aa1669ecc71d27f4c64f51ade80f29` | diseño | El modo fue implementado, no ejecutado; necesita consentimiento y artefacto final |
| `spotify_live_gate_design` | `019f5f3e…` / `992e0348c89628fe300d4541517e555052748a38ca298c7d1dd1c7cfee83f376` | diseño | Reutilizar identidad, SMTC, replay y cleanup; no afirmar reproducción |
| `phase3_final_diff_audit` | `019f5f8c…` / `307a05e5afa962d2e17c5e767fbc1addc3af62a4a49bfa7a0c7e827436735966` | histórica | El primer P1 Spotify fue corregido en la misma sesión; no es evidencia independiente ni release actual |
| `default_off_audit` | `019f5f96…` / `301acdf80fc3f1341e7a56936c41616c495c53bf70519e3589876c25e970a444` | corroborada/histórica | Conserva perfil estable 94/91 y experimental 95/92 como referencia; pendientes y gates siguen abiertos |

## Contradicciones y límites resueltos

1. **Carter 540/540**: una declaración temprana de 540/540 queda refutada por
   la auditoría primaria de 417/540 reales y 72 falsos positivos automáticos.
2. **Soak aprobado**: 86.400 s de proceso no equivale a gate aprobado cuando el
   criterio formal de GPU/gap falla.
3. **Spotify validado**: preflight `ready` y un gate diseñado no demuestran que
   una pista se reprodujo y verificó.
4. **4 GB**: perfiles proxy ejecutados en otra GPU no son evidencia de hardware
   de 4 GB.
5. **0 P0/P1**: aplica al diff auditado, no a toda la genealogía ni al producto
   nuevo.
6. **Default v2**: el hallazgo de v2 apagado pertenece a un commit anterior al
   cutover `f44f13f`; se conserva la lección de incompatibilidad de perfiles.

## Condición de cierre

Un hallazgo de agente sólo puede cerrar un gate si enlaza una fuente primaria o
una ejecución reproducible del producto nuevo. En ausencia de eso, permanece
como regresión, diseño o hipótesis explícita.
