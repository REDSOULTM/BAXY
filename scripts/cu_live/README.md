# Arnés en vivo de computer use

Corre misiones reales en la App (`Baxy.exe --conductor`, el mismo turno que la UI) sobre el PC del dueño y deja
evidencia fuera del repo, en `%LOCALAPPDATA%\BAXY\cu-universal-evidencia\v2-<caso>\`. Allí quedan:
- `events.jsonl` (utf-8-sig): pedido y final;
- `trace.jsonl`: etapas `computer_use.*`, con la última corrida al final del archivo;
- `compose_audit.jsonl`: borradores, vetos y hechos;
- `after.png`.

El perfil de prueba es `%LOCALAPPDATA%\BAXY\cu-universal-perfil`. Allí están:
- `journal/missions.jsonl`: cada vista y cada recibo de clic o tecla;
- `computer-use/procedures.v1.json`: lo aprendido. Si un procedimiento quedó mal aprendido, se borra de este archivo.

## Antes de correr

- Compilar en **Release**, porque el conductor usa el layout Release:
  - `dotnet build src/Baxy.App -c Release`
  - `dotnet publish src/Baxy.Core -c Release -r win-x64`. Un cambio en `src/Baxy.Providers.Windows` necesita también este publish de Core.
- No editar `src/` mientras corre un lote: la mente lee `src/` al arrancar cada caso.
- Nunca correr la suite completa ni la compuerta Full en paralelo con un lote, porque deja a la mente sin CPU.

## Uso

```bash
bash scripts/cu_live/batch.sh s01 s03 c5        # casos de cases/<id>.turns, uno por turno de conversación
bash scripts/cu_live/cu_live.sh mi-tag cases/demo.turns 5   # una sesión con varios turnos
py -3.12 scripts/cu_live/sumbench.py scripts/cu_live/logs/../<salida del lote>   # resumen caso | latencias | fin | final
py -3.12 scripts/cu_live/jsteps.py 60           # las últimas 60 operaciones del journal
py -3.12 scripts/cu_live/dialog.py <evidencia>/events.jsonl
```

`batch.sh` cierra sólo los procesos y marcos que abrió cada caso, y vacía los Bloc de notas de prueba por PID exacto.
`close_window.ps1` exige un título de 4 o más caracteres y nunca cierra Visual Studio Code ni Opera.

## Casos

`cases/` guarda los bancos del 2026-10-07:
- `s*`, `c*`, `u*`, `n*`, `e*`, `g*`, `w1`: el banco base;
- `v*`, `x*`, `y*`, `z*`, `a*`, `b*`, `c11`–`c22`, `d*`: los lotes ciegos.

Los resultados de cada uno están en `documentacion/computer-use/MEDICIONES.md`.
