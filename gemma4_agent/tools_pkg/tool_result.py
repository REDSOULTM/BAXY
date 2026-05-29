"""R4 sprint 2026-05-28: ToolResult dataclass.

Formaliza el patrón ya existente en el repo:
- `ok: bool` — éxito o fallo.
- `error: str` — mensaje (solo cuando `ok=False`).
- `status: str` — discriminador fino: 'ok', 'attempted', 'needs_user',
  'needs_implementation', 'failed'.
- `verified: bool | None` — el resultado fue verificado contra estado
  del SO. `None` = no medible.
- `verified_by: str` — qué tipo de evidencia (uia/screenshot/exitcode/...).
- `caveat: str` — texto de advertencia honesto para el reply.
- `evidence: dict` — payload de telemetría (screenshots, exit codes,
  ProcessNames, etc.).
- `extra: dict` — cualquier campo específico del tool (path, opened,
  ProcessName, ...). Catch-all para no quemar el contrato.

**Migración GRADUAL**: los handlers viejos siguen devolviendo `dict` via
`_ok/_err`. Cuando un handler se actualice, devolverá `ToolResult.ok(...)`
o `ToolResult.err(...)`. Consumers usan `.to_dict()` cuando aún no
tipan; cuando todos consumers tipan, se elimina `.to_dict()`.

Compatibilidad con dicts: `ToolResult.from_dict(d)` para inverso.

## Handlers ya migrados (2026-05-28)

Patrón usado: `_ok_tr/_err_tr` aliases internas que construyen `ToolResult`
y llaman `.to_dict()` para mantener back-compat byte-a-byte. Buscar
"R4 sprint 2026-05-28" en cualquier `domain_tools_*.py`.

- `dependency_tool` (domain_tools_dependency.py)
- `_device_bluetooth_status` (domain_tools_bluetooth.py)
- `source_manager_tool` (domain_tools_source_manager.py)
- `local_search_tool` (domain_tools_local_search.py)
- `notes_tasks_tool` (domain_tools_notes.py)

## Cómo migrar un nuevo handler

```python
# Antes:
def my_tool(args, state):
    if args.get('foo'):
        return _ok(foo=args['foo'], verified=True)
    return _err('missing foo', status='needs_user')

# Después (paso 1 — interop):
def _ok(**kw):
    return ToolResult.ok_result(**kw).to_dict()
def _err(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()

def my_tool(args, state):
    if args.get('foo'):
        return _ok(foo=args['foo'], verified=True)
    return _err('missing foo', status='needs_user')

# Después (paso 2 — full typed, cuando consumers manejen ToolResult):
def my_tool(args, state) -> ToolResult:
    if args.get('foo'):
        return ToolResult.ok_result(foo=args['foo'], verified=True)
    return ToolResult.err('missing foo', status='needs_user')
```
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Resultado tipado de un tool handler.

    Frozen para que sea hashable y los tests puedan comparar resultados.
    Use `ToolResult.ok_result(**fields)` o `ToolResult.err(message, **fields)`.
    (Nota: el constructor de éxito se llama `ok_result` — NO `ok` — porque
    `ok` es el nombre del campo bool de la dataclass).
    """
    ok: bool
    error: str = ""
    status: str = "ok"
    verified: bool | None = None
    verified_by: str = ""
    caveat: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok_result(cls, **extra: Any) -> "ToolResult":
        """Constructor for success. Reserved keys (status, verified, ...)
        go into typed fields; everything else goes into `extra`."""
        return cls._make(ok=True, **extra)

    @classmethod
    def err(cls, message: str, **extra: Any) -> "ToolResult":
        """Constructor for failure."""
        return cls._make(ok=False, error=message, **extra)

    @classmethod
    def _make(cls, *, ok: bool, error: str = "", **kwargs: Any) -> "ToolResult":
        # Separar campos tipados de extras.
        reserved = {"status", "verified", "verified_by", "caveat", "evidence"}
        typed: dict[str, Any] = {}
        rest: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k in reserved:
                typed[k] = v
            else:
                rest[k] = v
        return cls(ok=ok, error=error, extra=rest, **typed)  # type: ignore[arg-type]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ToolResult":
        """Construye desde el dict-shape legacy (`{"ok":..., "error":..., ...}`).
        Sirve para migrar consumers gradualmente."""
        ok = bool(d.get("ok", False))
        error = str(d.get("error") or "")
        return cls._make(ok=ok, error=error, **{k: v for k, v in d.items()
                                                if k not in {"ok", "error"}})

    def to_dict(self) -> dict[str, Any]:
        """Serializa al dict-shape legacy para consumers que aún no tipan.

        Solo incluye campos no-default para minimizar churn vs `_ok/_err`
        existentes (que tampoco emiten None defaults)."""
        out: dict[str, Any] = {"ok": self.ok}
        if self.error:
            out["error"] = self.error
        if self.status != "ok":
            out["status"] = self.status
        if self.verified is not None:
            out["verified"] = self.verified
        if self.verified_by:
            out["verified_by"] = self.verified_by
        if self.caveat:
            out["caveat"] = self.caveat
        if self.evidence:
            out["evidence"] = self.evidence
        out.update(self.extra)
        return out
