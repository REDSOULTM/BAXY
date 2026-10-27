---
paths:
  - "src/baxy_mind/**/*.py"
  - "tests/**/*.py"
  - "scripts/**/*.py"
  - "main.py"
---

# Python en BAXY

<!-- Adaptado de rules/python/*.md de everything-claude-code (MIT) 25278e7d7; lo que choca con AGENTS.md se quitó. -->

- Python 3.12 (`ruff.toml`: `target-version = "py312"`, lint sólo `F`). No se añaden black, isort, mypy ni
  bandit: no son parte del repo.
- Anotaciones de tipo en las firmas públicas; `dataclass(frozen=True)` o `NamedTuple` para datos que no
  deben mutar.
- En la mente, **stdout es el protocolo** con la App (`src/baxy_mind/protocol.py`, una línea JSON por
  mensaje): nada de `print()`; los diagnósticos van a stderr, como ya hace `src/baxy_mind/__main__.py`.
- Nada de `except: pass` ni de un fallback que devuelva éxito: un fallo acaba en un estado terminal honesto.
- `with` para ficheros y recursos; `subprocess` con lista de argumentos, nunca una cadena con texto de la
  persona dentro.
- Pruebas: pytest, `tests/test_*.py`, con el Python del runtime (skill `verificar`), siempre `-q`.
