---
paths:
  - "src/Baxy.FieldUi/src/**/*.ts"
  - "src/Baxy.FieldUi/src/**/*.tsx"
  - "src/Baxy.FieldUi/e2e/**/*.ts"
---

# FieldUi (React + TS) en BAXY

- Vite + React 19 + TS dentro del shell de escritorio (WebView2). BAXY no es una aplicación web: la vista
  se verifica ejecutando el producto y con `scripts/test_field_ui.ps1`, nunca con una BAXY de otra sesión.
- Componentes de función; hooks sólo en el nivel superior, con dependencias completas
  (`eslint-plugin-react-hooks` ya está configurado). No dupliques estado que se puede derivar.
- Accesibilidad central: HTML semántico, teclado y foco gestionados, nada alcanzable sólo con el ratón. El
  modo accesible cambia la presentación, no las capacidades.
- Validación: `eslint . --max-warnings 0` y `tsc --noEmit` con `tsconfig.app.json` y `tsconfig.node.json`
  (skill `verificar`). Nada de `@ts-ignore` ni `eslint-disable` para pasar.
- No abras `src/Baxy.FieldUi/dist/` entero; no regeneres `dist/` sin que el cambio lo pida.
