---
name: prueba-en-vivo
description: Lista de seguridad para cualquier prueba de BAXY que maneje el escritorio real (e2e, bancos, casos en vivo, demo) en el PC o el notebook - antes, durante y después. Úsala antes de lanzar BAXY para probar, de correr scripts/renew_check.ps1 o scripts/test_field_ui.ps1, o de probar un caso real.
---

# Probar BAXY en vivo sin romper nada

Sale de incidentes reales: una prueba hizo que BAXY deshabilitara 256 servicios por msconfig, otras dejaron
juegos abiertos, decenas de ventanas o cuatro llama-server en la GPU, y matar procesos por nombre cerró VS Code.

## Antes

1. **Dónde.** El notebook está dedicado al desarrollo: se puede manejar su escritorio. El PC lo usa el dueño:
   no se maneja su escritorio mientras lo usa (si juega, se espera).
2. **Nada más en marcha.** Un solo `Baxy.exe` por máquina; si hay otra BAXY o una prueba de otra sesión, no
   se lanza nada (en el notebook, una prueba en curso deja su carpeta de uso sin el último `*.done`).
   ```powershell
   Get-CimInstance Win32_Process -Filter "Name='Baxy.exe' OR Name='baxy-core.exe' OR Name='llama-server.exe'" |
     Select-Object ProcessId, Name, CommandLine
   ```
3. **GPU libre:** `nvidia-smi`. Como mucho tres `llama-server` a la vez.
4. **Escritorio limpio:** `scripts\renew\notebook\frente_ahora.ps1` (sale con 1 si el frente lo tiene una
   ventana invisible o GameInputSvc: así una prueba de escritorio no vale).
5. Las acciones peligrosas se prueban sobre blancos seguros y contactos de prueba, nunca sobre cuentas o
   conversaciones reales del dueño. Nada se compra ni se instala.

## Durante

- Un caso cada vez cuando se busca un fallo; nada de tandas de horas para confirmar un arreglo.
- Lo largo va en segundo plano (`run_in_background`); un `&` al final lo manda a la nada.
- No se edita un script que un proceso en marcha puede estar leyendo: se escribe una copia nueva.
- Los procesos que abre un banco mueren con él (`scripts/renew/limpieza.py`).

## Después

1. Cierra **por PID** todo lo que la prueba abrió: juegos, apps, ventanas, `python`, `llama-server`. Lista
   primero y mata en otro comando, para que el filtro no coincida con la propia shell. Nunca
   `Stop-Process -Name` ni `taskkill /IM` (la guarda lo deniega).
2. Si se paró una tarea de fondo o un Monitor, busca sus `bash.exe` hijos que siguen vivos y mátalos por PID.
3. Comprueba que nada tocó el sistema:
   ```powershell
   Get-WinEvent -FilterHashtable @{LogName='System'; Id=7040; StartTime=(Get-Date).AddHours(-3)} -ErrorAction SilentlyContinue
   (Get-Item 'HKLM:\SOFTWARE\Microsoft\Shared Tools\MSConfig\services' -ErrorAction SilentlyContinue).ValueCount
   ```
4. GPU otra vez libre (`nvidia-smi`) y la BAXY del dueño, si estaba abierta, como estaba.
5. El resultado se juzga por el estado real (captura, UIA, el journal), no por lo que BAXY dice.
