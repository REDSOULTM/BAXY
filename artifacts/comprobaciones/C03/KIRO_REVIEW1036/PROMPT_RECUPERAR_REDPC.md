# Prompt para Codex en el PC donde trabajó Kiro

Recupera el relevo privado de BAXY C03 que dejó Kiro en REDPC. Sólo prepara el
traslado; no continúes el goal, no ejecutes pruebas ni producto y no cambies código,
rama o créditos. El Codex del portátil está continuando el trabajo en paralelo.

Proyecto esperado: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Rama publicada: `codex/kiro-goal-c03`; último commit de Kiro
`3a73819215ed483e3f7d3a5b36ef85bad43dfad2`. No confundas esta carpeta con BAXY a secas.

Crea un ZIP fuera del repositorio con:

1. `%LOCALAPPDATA%\BAXY\C03-survey-requirements336-private\requirements.jsonl`,
   conservando sus bytes originales.
2. Las carpetas privadas de SYSTEM1028, APPS1029, REPAIR1030–1033, CLOCK1034 y
   READS1035: paneles, sellos, capturas completas, terminales, recibos, candidatos
   y journals. Localiza sus rutas exactas en los PLAN, PREREG, EXIT y runners
   versionados; no presupongas que todas siguen el mismo nombre.
3. Prioridad máxima: READS1035, ejecutada con 12 terminales pero sin adjudicar.
   Incluye `C:\Users\usuario\AppData\Local\BAXY\C03-reads1035-profile\journal\missions.jsonl`
   y las capturas que vinculan cada caso con su respuesta y hechos observados.
4. Un manifiesto con rutas originales, tamaño y SHA256 de cada archivo; indica
   expresamente cualquier material ausente. Si una carpeta tiene secretos o
   credenciales ajenos a la evidencia, no los incluyas; documenta la exclusión.

El registro publicado por Kiro era 154 covered / 588 open / 0 not_applicable,
SHA256 `58986cb8b2b42a6d70f6648ea0e66b9a7b7e948b784963316683fb6b3f8671f7`.
Comprueba el archivo encontrado; no lo modifiques para hacerlo coincidir. Si sólo
puedes recuperar un archivo, entrega primero ese requirements.jsonl con su SHA.

Devuelve la ruta absoluta del ZIP, su SHA256 y los faltantes. No subas estos datos
privados a GitHub ni a servicios externos. El dueño trasladará el archivo entre
sus equipos. No apliques nada de este ZIP sobre la copia del portátil.
