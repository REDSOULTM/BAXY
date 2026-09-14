# FILES1425 — tanda abortada por la raíz, sin adjudicación formal

Fecha: 2026-09-14T15:28:21.053649+00:00. Escritor raíz Fable. Candidato: HEAD ed16761804e7d015e359d9997a2835e11517db65 con BUILD1425 (C03-repairs1425-build). Material sellado C03-files1425-proposal (SEAL cb1f0d1a66f4ae69…), candidato 52f2f6f29ab75903…, preparación 7b808aa27a7d7368….

**Qué pasó.** Los cuatro primeros casos (H0201, H0264, H0329, H0698) terminaron `blocked_environment` / `runtime_not_ready` en unos 4 s cada uno, con cero operaciones y cero violaciones: el núcleo (baxy-core) se detuvo en el inicializador estático de `ProductCatalog` («The product operation catalog must have stable unique operation and verifier identities») porque el descriptor nuevo `filesystem.known.list` se insertó después de `filesystem.known.search`, fuera del orden ordinal que el catálogo exige. La App nunca admitió el turno. La raíz detuvo la tanda tras el cuarto caso; los siete restantes (índices 4–10) no se ejecutaron.

**Por qué no hay ROOT_ADJUDICATION.** Al diagnosticar la causa la raíz recompiló el producto antes de adjudicar; las compilaciones no son reproducibles byte a byte y los pins de los binarios del candidato (`baxy-core.dll`, `Baxy.dll`, …) dejaron de coincidir, así que `root_adjudicate_from_decisions.py` rechaza la evidencia (SHA mismatch). Los recibos privados de los cuatro casos (run-00…run-03) quedan intactos en el instrumento. Ningún crédito, ningún cambio del registro (437/742 cubiertos, 305 abiertos). Los nombres de archivos del dueño no llegaron a leerse.

**Casos ejecutados (recibos privados):**

| índice | case_id | exit | violaciones | segundos |
|---:|---|---:|---:|---:|
| 0 | H0201 | 2 | 0 | 3.64 |
| 1 | H0264 | 2 | 0 | 3.53 |
| 2 | H0329 | 2 | 0 | 3.53 |
| 3 | H0698 | 2 | 0 | 3.5 |

**Reparación.** El descriptor se movió antes de `filesystem.known.search` (catálogo en orden ordinal verificado); el núcleo arranca y anuncia `filesystem.known.list` en el hello. Se mide en FILES1427 sobre BUILD1427 con el mismo panel.

**Lección registrada.** No recompilar el producto entre la ejecución y la adjudicación de una tanda: los binarios pinados no se reproducen. Tras tocar el catálogo del Kernel, arrancar `baxy-core.exe` a mano antes de sellar.
