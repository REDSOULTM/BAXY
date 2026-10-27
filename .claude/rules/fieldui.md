---
paths:
  - "src/Baxy.FieldUi/src/**/*.ts"
  - "src/Baxy.FieldUi/src/**/*.tsx"
  - "src/Baxy.FieldUi/e2e/**/*.ts"
---

# FieldUi (React + TS) en BAXY

<!-- Adaptado de rules/react y rules/typescript de everything-claude-code (MIT) 25278e7d7; sin Next.js ni servidor. -->

- Vite + React 19 + TS dentro de WebView2. No hay Next.js, RSC, rutas ni servidor.
- Componentes de función; hooks sólo en el nivel superior, con dependencias completas
  (`eslint-plugin-react-hooks` ya está configurado). No dupliques estado que se puede derivar.
- Accesibilidad central: HTML semántico, teclado y foco gestionados, nada alcanzable sólo con el ratón. El
  modo accesible cambia la presentación, no las capacidades.
- Validación: `eslint . --max-warnings 0` y `tsc --noEmit` con `tsconfig.app.json` y `tsconfig.node.json`
  (skill `verificar`). Nada de `@ts-ignore` ni `eslint-disable` para pasar.
- No abras `src/Baxy.FieldUi/dist/` entero; no regeneres `dist/` sin que el cambio lo pida.
