# Aviso de datos: evidencia semántica de turnos

Los archivos públicos de evidencia de turnos se generan de forma reproducible
con `scripts/build_presto_turn_evidence.py`. BAXY conserva las particiones
oficiales: solo `train` participa en la evidencia de ejecución; `validation` y
`test` quedan reservadas para evaluación. Los adaptadores retienen únicamente
el texto, la etiqueta semántica revisada, el idioma/split y la procedencia. No
incorporan contexto, contactos, listas, notas, slots ni identificadores de
trabajadores.

## PRESTO v1

- Proyecto y procedencia:
  <https://github.com/google-research-datasets/presto>
- Licencia de los datos:
  [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
- Cita solicitada por el proyecto:
  Rahul Goel et al. (2023), *PRESTO: A Multilingual Dataset for Parsing
  Realistic Task-Oriented Dialogs*, arXiv:2303.08954,
  <https://doi.org/10.48550/arXiv.2303.08954>.
- Transformación de BAXY: selección de ejemplos independientes `en-US` y
  `es-ES`, proyección revisada de etiquetas a modos/familias que ya existen en
  el catálogo, descarte de contexto y deduplicación conservadora.

## MASSIVE v1.1

- Proyecto y procedencia: <https://github.com/alexa/massive>
- Licencia incluida con los datos:
  [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
- Cita solicitada por el proyecto:
  Jack FitzGerald et al. (2023), *MASSIVE: A 1M-Example Multilingual Natural
  Language Understanding Dataset with 51 Typologically-Diverse Languages*,
  <https://doi.org/10.48550/arXiv.2204.08582>.
- MASSIVE localiza el conjunto inglés de SLURP. Por esa procedencia también se
  reconoce:
  Emanuele Bastianelli, Andrea Vanzo, Pawel Swietojanski y Verena Rieser
  (2020), *SLURP: A Spoken Language Understanding Resource Package*,
  EMNLP 2020, <https://doi.org/10.18653/v1/2020.emnlp-main.588>.
- Transformación de BAXY: selección `en-US`/`es-ES`, conservación de la
  partición original, filtro de calidad de localización, proyección revisada a
  capacidades existentes y eliminación de slots/metadatos no necesarios.

## Evidencia histórica privada

`historical_messages.jsonl` y cualquier corpus runtime que lo combine se
consideran datos privados locales del proyecto. No forman parte de la
atribución CC BY anterior ni deben publicarse como un nuevo dataset. El
manifiesto versionable conserva únicamente conteos, hashes y reglas de
selección; los caches E5 se regeneran bajo `%LOCALAPPDATA%\BAXYRuntime`.

Las modificaciones y selecciones descritas aquí no implican respaldo de BAXY
por parte de Google, Amazon/Alexa, los autores de PRESTO, MASSIVE o SLURP.
