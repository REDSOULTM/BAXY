# r128 in-scope remaining families (read-only)

Score vigente: 1576/144. Env 220 omitidas. Other-lang 7.

r129 ya cubre (no tocar producto mientras testhost corre):
- implicit_name AskToSave (3): `Yo me llamo red` / `Mi nombre es Albeda…`
- named unknown open asked (2): `abrí la aplicación zzqwx123`
- alarm hora >23 sin ops (2 en none_other): `poné una alarma a las 99`
- bare `Tiempo` (2): r128 dijo `Listo, son las` **sin journal** → fail
  verificación. El dueño ahora es `system.time`.
- app.open_other (8): terminal System32\cmd; prefix 3 (`Steel`/`Ste`);
  `abri photoshop` si el catálogo tiene un hit único.
- `Sí. Abre Steel.` puede seguir fallando: el fullmatch del prefijo no
  traga el `Sí.` — anotar si r129 no lo cubre.

No cubierto por r129 (siguiente familia si el score sigue >0):
- trivia `Listo, el agua es H2O` (conversación, no efecto)
- `Dile a mi amiga…` eco de canal
- ventana más grande con `win_` interno
- `poné chrome a la izquierda` / modo avión robados por media
- `poneme una canción` pide título (bare play; hay test que aclara
  `poné una canción` vs `poné música`)
- `Abrelo` aún pregunta (deíctico ya en árbol; r128 no lo ejecutó)
- none_other ~42: speech, `Hello?` language, sandbox file, `¿Quién es de
  verdad?`

No convertir env ni de/fr/it/pt a pass.
