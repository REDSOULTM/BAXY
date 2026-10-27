---
name: lanzar-baxy
description: Lanza, cierra o relanza BAXY desde un worktree de desarrollo en esta máquina, y comprueba que arrancó de verdad. Úsala cuando el dueño pida abrir, lanzar o reiniciar BAXY, o después de un arreglo que hay que ver funcionando.
---

# Lanzar BAXY desde un worktree

1. **Seguridad primero** (skill `prueba-en-vivo`, «Antes»): un solo `Baxy.exe` por máquina; ninguna prueba de
   otra sesión en marcha. La BAXY instalada del dueño o la de una demo no se cierra sin que él lo pida.
2. **Lanzar:** `scripts\run_renew.cmd` desde la raíz del worktree. Pone el modelo, la voz y la visión de cada
   máquina, cierra la ventana de BAXY de ese mismo worktree, compila si hace falta y arranca. No uses
   `py main.py` a secas: arranca sin las rutas de la mente y la mente queda no disponible.
   ```powershell
   cmd.exe /c scripts\run_renew.cmd
   ```
3. **Relanzar tras un arreglo:** cierra por PID el `Baxy.exe` de este worktree (su `CommandLine` lo dice),
   espera a que salgan `baxy-core.exe` y el `llama-server` que colgaban de él, y vuelve al paso 2.
4. **Comprobar que arrancó:** el proceso vive, la ventana existe y la mente responde. Con el puerto de
   depuración de WebView2 (lo pone `scripts\test_field_ui.ps1`), la vista `https://baxy.local/` aparece en
   `http://127.0.0.1:9333/json/list`. «Lanzado» se dice con esa evidencia, no por haber ejecutado el comando.
5. Si no arranca: el registro de la mente y el de la App, antes de tocar código (skill `systematic-debugging`).
